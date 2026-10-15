"""R2 acceptance: failed diary collection must preserve memory and error classes."""
import json
import subprocess

import pytest

from .test_live_staging_acceptance import dump, load, play


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_empty_host_diary_does_not_advance_memory(play, monkeypatch, host):
    """Given an empty host response, When closing, Then fail without publishing diaries."""
    play.setup()
    play.cli("open", "--host", host)
    play.cli("run")

    def empty_response(cmd, **kwargs):
        response = play.host(cmd, **kwargs)
        if host == "claude":
            payload = json.loads(response.stdout)
            payload["result"] = "   "
            response.stdout = json.dumps(payload)
        else:
            events = [json.loads(line) for line in response.stdout.splitlines()]
            for event in events:
                if event.get("type") == "item.completed":
                    event["item"]["text"] = "   "
            response.stdout = "\n".join(json.dumps(event) for event in events)
        return response

    monkeypatch.setattr(subprocess, "run", empty_response)
    result = play.cli("close", code=2)
    assert result["status"] == "open"
    assert set(result["errors"]) == {"a", "b", "c"}
    roster = load(play.stage / "roster.yaml")["characters"]
    for slug in ("a", "b", "c"):
        assert not play.diary(slug).exists()
        assert not any(entry["id"] == "S01" for entry in roster[slug]["entries"])


def test_close_missing_memory_file_is_state_error(play):
    """Given a missing registered diary, When collecting, Then return input/state exit 1."""
    play.setup()
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("close")
    play.setup("S02")
    play.cli("open", scene="S02")
    play.diary("a").unlink()
    roster = load(play.stage / "roster.yaml")
    roster["characters"]["a"]["session"] = None
    dump(play.stage / "roster.yaml", roster)
    result = play.cli("close", scene="S02", code=1)
    assert result["status"] == "open" and "a" in result["errors"]
    assert not play.diary("a", "S02").exists()
