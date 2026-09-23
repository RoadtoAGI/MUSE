"""Settings belong to one explicitly bound work; loading them never reads a key."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

import yaml

MODES = ("standard", "jev")
MODEL = "jev-1.13.0"
CONFIG_FILE = Path(".muse/runtime.yaml")


class RuntimeConfigError(ValueError):
    pass


def read_mapping(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise RuntimeConfigError(f"无法读取配置: {path}") from None
    if not isinstance(value, dict):
        raise RuntimeConfigError(f"配置须为 mapping: {path}")
    return value


def infer_work_dir(output_dir: str | Path | None = None) -> Path | None:
    """Only the existing <work>/pipeline/... output contract binds a work."""
    if output_dir is None:
        return None
    output = Path(output_dir).resolve()
    for parent in (output, *output.parents):
        if parent.name == "pipeline":
            return parent.parent
    return None


@dataclass(frozen=True)
class Settings:
    mode: str
    work_dir: Path | None
    source: str

    @property
    def enabled(self) -> bool:
        return self.mode == "jev"

    @property
    def model(self) -> str:
        return MODEL


def resolve_settings(work_dir: str | Path | None = None, *, output_dir=None) -> Settings:
    work = Path(work_dir).resolve() if work_dir is not None else infer_work_dir(output_dir)
    if work is None:
        return Settings("standard", None, "unbound")
    path = work / CONFIG_FILE
    if not path.is_file():
        return Settings("standard", work, "default")
    data = read_mapping(path)
    if set(data) - {"mode"}:
        raise RuntimeConfigError("runtime.yaml 仅支持 mode 字段；密钥使用 MUSE_JEV_API_KEY")
    mode = data.get("mode", "standard")
    if mode not in MODES:
        raise RuntimeConfigError("模式须为 standard 或 jev")
    return Settings(mode, work, str(path))


def set_mode(work_dir: str | Path, mode: str) -> Settings:
    work = Path(work_dir).resolve()
    if not work.is_dir():
        raise RuntimeConfigError("work-dir 必须是已存在的作品目录")
    if mode not in MODES:
        raise RuntimeConfigError("模式须为 standard 或 jev")
    path = work / CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            yaml.safe_dump({"mode": mode}, stream, sort_keys=False)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return resolve_settings(work)


def resolve_key(settings: Settings) -> str:
    if not settings.enabled:
        raise RuntimeConfigError("standard 模式不读取 JEV 密钥")
    value = os.getenv("MUSE_JEV_API_KEY", "").strip()
    if not value:
        raise RuntimeConfigError("JEV 模式需要环境变量 MUSE_JEV_API_KEY")
    return value


def resolve_tuzi_key(settings: Settings) -> str:
    """Read the optional backup only after an official capacity failure."""
    if not settings.enabled:
        raise RuntimeConfigError("standard 模式不读取 JEV 密钥")
    return os.getenv("MUSE_JEV_TUZI_API_KEY", "").strip()


def record_event(settings: Settings, node: str, status: str, **details) -> None:
    """Append sanitized caller metadata; prompts, source text and keys stay out."""
    if settings.work_dir is None:
        return
    event = {**details, "time": datetime.now(timezone.utc).isoformat(), "node": node,
             "status": status, "mode": settings.mode,
             "model_requested": details.get("model_requested", settings.model if settings.enabled else None),
             "work_dir": str(settings.work_dir)}
    path = settings.work_dir / ".muse/jev-events.jsonl"
    try:
        payload = (json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n").encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "ab") as stream:
            stream.write(payload)
    except (OSError, TypeError, ValueError):
        print("[muse LOG_WARNING] 运行记录未写入，检索结果继续交付。", file=sys.stderr)
