#!/usr/bin/env python3
"""按原文行号切片；先验证整批范围，避免成功消息掩盖缺失片段。"""
import argparse
import json
from pathlib import Path
import re


def extract(source: Path, output_dir: Path, ranges: list[dict]) -> list[Path]:
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    seen = set()
    for item in ranges:
        sid, start, end = item["scene_id"], item["start"], item["end"]
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in seen:
            raise ValueError(f"场景 ID 非法或重复: {sid!r}")
        seen.add(sid)
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ValueError(f"{sid}: 行号须在 1..{len(lines)} 内: {start}..{end}")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for item in ranges:
        sid, start, end = item["scene_id"], item["start"], item["end"]
        path = output_dir / f"scene_{sid}.md"
        header = f"<!-- {sid} | 来源：{item.get('chapter', '')} | 行范围：{start}-{end} -->\n\n"
        path.write_text(header + "".join(lines[start - 1:end]), encoding="utf-8")
        outputs.append(path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--batch", type=Path)
    parser.add_argument("--scene-id")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--chapter", default="")
    args = parser.parse_args()
    try:
        ranges = json.loads(args.batch.read_text(encoding="utf-8")) if args.batch else [
            {"scene_id": args.scene_id, "start": args.start, "end": args.end, "chapter": args.chapter}
        ]
        if not isinstance(ranges, list) or not ranges:
            raise ValueError("切片清单必须是非空列表")
        outputs = extract(args.source, args.output_dir, ranges)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"切片失败: {exc}\n")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
