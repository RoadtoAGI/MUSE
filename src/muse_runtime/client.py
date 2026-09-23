"""Typed JEV HTTP client; transport errors never expose server bodies or keys."""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request

from .config import Settings, record_event, resolve_key, resolve_tuzi_key

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
REQUEST_TIMEOUT_SECONDS = 8.0
TUZI_ENDPOINT = "https://api.tu-zi.com/v1/systemone"
TUZI_MODEL = "jev-1.13"
TUZI_MODELS = {"jev-1.13", "jev-1.13.0", "typesafe/jev-1.13-20260917", "typesafe-ai/jev"}
QUOTA_CODES = {"insufficient_quota", "quota_exceeded", "insufficient_credits",
               "credits_exhausted", "insufficient_balance", "billing_hard_limit_reached"}
QUOTA_MESSAGES = ("insufficient credits", "insufficient quota", "quota exceeded",
                  "quota exhausted", "insufficient balance", "credits exhausted",
                  "not enough credits", "out of credits")


class JevError(RuntimeError):
    """A controlled error code, safe to include in local diagnostics."""

    def __init__(self, code, *, attempts=None, capacity_reason=None):
        super().__init__(code)
        self.attempts = attempts or []
        self.capacity_reason = capacity_reason


def _capacity_reason(error: urllib.error.HTTPError) -> str | None:
    # 429 is capacity/rate limiting; do not mislabel it as exhausted credit.
    if error.code == 402:
        return "quota_exhausted"
    if error.code == 429:
        return "rate_limited"
    if error.code not in (400, 403):
        return None
    try:
        body = json.loads(error.read(65536))
    except (ValueError, OSError, UnicodeError):
        return None
    if not isinstance(body, dict):
        return None
    detail = body.get("error", body)
    if isinstance(detail, dict) and any(detail.get(field) in QUOTA_CODES
                                        for field in ("code", "type")
                                        if isinstance(detail.get(field), str)):
        return "quota_exhausted"
    messages = [body.get("detail"), body.get("message")]
    messages.extend([detail.get("message"), detail.get("detail")] if isinstance(detail, dict) else [detail])
    if any(phrase in message.lower() for message in messages if isinstance(message, str)
           for phrase in QUOTA_MESSAGES):
        return "quota_exhausted"
    return None


def _number(value, lower, upper):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and lower <= value <= upper


def validated_answers(body: dict, questions: dict) -> dict:
    if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
        raise JevError("invalid_response")
    answers = {}
    for name, question in questions.items():
        answer = body["answers"].get(name)
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise JevError("invalid_response")
        kind = question["type"]
        if kind == "score":
            if not _number(answer.get("score"), 0, len(question["criteria"]) - 1):
                raise JevError("invalid_score")
            answers[name] = {"type": kind, "score": answer["score"]}
        elif kind == "choice":
            if not isinstance(answer.get("choice"), str) or answer["choice"] not in question["criteria"]:
                raise JevError("invalid_choice")
            answers[name] = {"type": kind, "choice": answer["choice"]}
        elif kind == "noul":
            if not _number(answer.get("noul"), 0, 1):
                raise JevError("invalid_noul")
            answers[name] = {"type": kind, "noul": answer["noul"]}
        else:
            raise JevError("unsupported_question")
        if kind in ("score", "choice"):
            probabilities = answer.get("probabilities")
            expected = set(question["criteria"]) if kind == "choice" else {str(i) for i in range(len(question["criteria"]))}
            if not isinstance(probabilities, dict) or set(probabilities) != expected or not all(_number(p, 0, 1) for p in probabilities.values()):
                raise JevError("invalid_probabilities")
            if not math.isclose(sum(probabilities.values()), 1, abs_tol=.03):
                raise JevError("invalid_probabilities")
            answers[name]["probabilities"] = probabilities
    return answers


class JevClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._key = resolve_key(settings)
        # Shared by a retrieval batch. In-flight official requests may finish;
        # subsequent calls use the backup after capacity failure in this client.
        self._fallback_reason = None
        self._tuzi_key = None

    def _request(self, state, questions, provider, timeout):
        backup = provider == "tuzi"
        model = TUZI_MODEL if backup else self.settings.model
        data = json.dumps({"model": model, "state": state, "questions": questions},
                          ensure_ascii=False).encode()
        if backup and len(data) > 32 * 1024:
            raise JevError("tuzi_payload_too_large")
        request = urllib.request.Request(TUZI_ENDPOINT if backup else ENDPOINT, data=data,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + (self._tuzi_key if backup else self._key)}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                reason = _capacity_reason(exc) if not backup else None
            finally:
                exc.close()
            raise JevError(f"http_{exc.code}", capacity_reason=reason) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise JevError("transport_error") from None
        except (ValueError, UnicodeError):
            raise JevError("invalid_json") from None
        # Tuzi can preserve the upstream response at data.answers.
        if backup and isinstance(body, dict) and "answers" not in body and isinstance(body.get("data"), dict):
            inner = dict(body["data"])
            for field in ("model", "usage"):
                if field not in inner and field in body:
                    inner[field] = body[field]
            body = inner
        answers = validated_answers(body, questions)
        actual_model = body.get("model")
        allowed = TUZI_MODELS if backup else {self.settings.model}
        if actual_model is not None and (not isinstance(actual_model, str) or actual_model not in allowed):
            raise JevError("unexpected_model")
        usage = body.get("usage")
        if usage is None:
            usage = {}
        if not isinstance(usage, dict):
            raise JevError("invalid_usage")
        tokens = {}
        for name in ("input_tokens", "output_tokens"):
            if name in usage:
                value = usage[name]
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise JevError("invalid_usage")
                tokens[name] = value
        return {"answers": answers, "model_requested": model,
                "actual_model": actual_model, "usage": tokens, "provider": provider}

    def evaluate(self, state: dict, questions: dict, *, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict:
        if not _number(timeout, 0, REQUEST_TIMEOUT_SECONDS) or timeout == 0:
            raise JevError("invalid_timeout")
        started = time.monotonic()
        provider = "tuzi" if self._fallback_reason else "typesafe"
        attempts = []
        for attempt_index in range(2):
            remaining = timeout if attempt_index == 0 else timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise JevError("request_timeout", attempts=attempts)
            attempt = {"provider": provider,
                       "model_requested": TUZI_MODEL if provider == "tuzi" else self.settings.model}
            try:
                result = self._request(state, questions, provider, remaining)
            except JevError as exc:
                attempts.append({**attempt, "status": "error", "error": str(exc)})
                if provider == "typesafe" and exc.capacity_reason:
                    backup_key = resolve_tuzi_key(self.settings)
                    if backup_key:
                        self._tuzi_key = backup_key
                        self._fallback_reason = exc.capacity_reason
                        record_event(self.settings, "jev_provider", "fallback",
                                     from_provider="typesafe", to_provider="tuzi",
                                     reason=exc.capacity_reason)
                        provider = "tuzi"
                        continue
                raise JevError(str(exc), attempts=attempts) from None
            attempts.append({**attempt, "status": "evaluated"})
            return {**result, "attempts": attempts,
                    "fallback_reason": self._fallback_reason if provider == "tuzi" else None,
                    "elapsed_seconds": round(time.monotonic() - started, 3)}
        raise JevError("providers_exhausted", attempts=attempts)
