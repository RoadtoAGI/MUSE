"""Work-scoped mode controls; set/status never call JEV or inspect the API key."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
from pathlib import Path
import sys

from . import brainstorm
from .config import CONFIG_FILE, MODES, RuntimeConfigError, resolve_settings, set_mode


def status(work_dir) -> dict:
    settings = resolve_settings(work_dir)
    recent = {}
    events = settings.work_dir / ".muse/jev-events.jsonl"
    try:
        with events.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                    recent[event["node"]] = {key: event[key] for key in ("status", "time", "request_id", "strategy", "provider", "providers", "attempts", "from_provider", "to_provider", "reason") if key in event}
                except (ValueError, KeyError, TypeError):
                    continue
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        print("[muse LOG_WARNING] 无法读取运行记录。", file=sys.stderr)
    return {"mode": settings.mode, "source": settings.source, "work_dir": str(settings.work_dir),
            "config_file": str(settings.work_dir / CONFIG_FILE), "model_requested": settings.model,
            "configured_only": True,
            "adapters": {"scene_retrieval": "score; explicit MMR evaluates only",
                         "inspiration_retrieval": "score; preferred-work evaluates only",
                         "brainstorm": "choice/noul; advice for writing agent and author"},
            "data_transfer": {"provider": "TypeSafe", "provider_priority": ["typesafe", "tuzi"],
                              "fallback_on": ["quota_exhausted", "rate_limited"],
                              "backup_key_env": "MUSE_JEV_TUZI_API_KEY", "enabled": settings.enabled,
                              "fields": ["query", "style/function hints", "must conditions", "permitted candidate text/cards",
                                         "brainstorm goal/context/constraints/feedback/candidates/questions"],
                              "includes_private_material_if_queried": True},
            "recent": recent}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MUSE 作品级 Jev 辅助")
    commands = parser.add_subparsers(dest="command", required=True)
    mode = commands.add_parser("mode", help="设置或查看作品模式")
    actions = mode.add_subparsers(dest="action", required=True)
    setter = actions.add_parser("set")
    setter.add_argument("mode", choices=MODES)
    setter.add_argument("--work-dir", required=True)
    query = actions.add_parser("status")
    query.add_argument("--work-dir", required=True)
    creative = commands.add_parser("brainstorm", help="共同构思的候选评价")
    creative_actions = creative.add_subparsers(dest="action", required=True)
    creative_actions.add_parser("guide", help="查看输入、返回和结果使用指南")
    evaluate = creative_actions.add_parser("evaluate")
    evaluate.add_argument("--work-dir", required=True)
    evaluate.add_argument("--input", required=True, help="本轮候选及上下文 JSON 文件")
    args = parser.parse_args(argv)
    try:
        if args.command == "brainstorm":
            if args.action == "guide":
                print(files("muse_runtime").joinpath("brainstorm-guide.md").read_text(encoding="utf-8"))
                return 0
            if not Path(args.work_dir).is_dir():
                raise RuntimeConfigError("work-dir 必须是已存在的作品目录")
            try:
                payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise RuntimeConfigError("无法读取 brainstorm 输入 JSON 文件") from None
            result = brainstorm.evaluate(resolve_settings(args.work_dir), payload)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["status"] == "error" else 0
        if args.action == "set":
            set_mode(args.work_dir, args.mode)
        print(json.dumps(status(args.work_dir), ensure_ascii=False, indent=2))
        return 0
    except (RuntimeConfigError, ValueError, OSError) as exc:
        message = str(exc) if isinstance(exc, RuntimeConfigError) else type(exc).__name__
        print(f"[muse CONFIG_ERROR] {message}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Preserve exceptions in the library; the CLI must not echo request or key data.
        print(f"[muse RUNTIME_ERROR] {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
