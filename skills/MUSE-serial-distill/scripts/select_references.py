#!/usr/bin/env python3
"""先按发布 manifest 筛出可见场景元数据，再交模型匹配；不写知识库。"""
import argparse
import json
from pathlib import Path
import re
import sys
import yaml

TITLE = re.compile(r"^(?:#+\s*)?(第[零〇一二两三四五六七八九十百千0-9]+[章回]|Chapter\s+\d+|序章|楔子|引子)(?:\s|[:：、.．]|$)", re.I)


def select(index: list[dict], manifest: dict, published_dir: Path, cutoff: int) -> tuple[list, int]:
    entries = manifest.get("entries") or []
    by_id = {}
    titles: dict[str, list[int]] = {}
    seen_sequences = set()
    for entry in entries:
        seq = entry.get("published_seq")
        if type(seq) is not int or seq < 1 or seq in seen_sequences:
            raise ValueError("manifest published_seq 缺失、非法或重复")
        seen_sequences.add(seq)
        cid = entry.get("chapter_id")
        if not cid or cid in by_id:
            raise ValueError("manifest 章 ID 缺失或重复")
        by_id[cid] = seq
        # 存量索引仅有原章节标题时，在程序内核对标题，不向模型输出后文。
        path = published_dir / entry.get("file", "")
        if path.is_file():
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    match = TITLE.match(line.strip())
                    if match:
                        titles.setdefault(match[1], []).append(seq)
                        break
    if cutoff < 0 or cutoff > max(seen_sequences, default=0):
        raise ValueError("截止序必须位于 manifest 已登记范围内")
    visible, skipped = [], 0
    for item in index:
        source_ids = item.get("source_chapters")
        if source_ids and isinstance(source_ids, list) and all(cid in by_id for cid in source_ids):
            seq = max(by_id[cid] for cid in source_ids)
        else:
            # 仅支持可唯一核对的单章旧标题；跨章或含糊标题等待源索引补齐。
            label = str(item.get("source_chapter", "")).strip()
            matches = titles.get(label, [])
            if source_ids or len(matches) != 1:
                skipped += 1
                continue
            seq = matches[0]
        if seq <= cutoff:
            visible.append({**item, "published_seq": seq})
    return visible, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--through-seq", type=int, required=True)
    args = parser.parse_args()
    try:
        index = json.loads(args.index.read_text(encoding="utf-8"))
        manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(index, list) or not isinstance(manifest, dict):
            raise ValueError("索引须为列表，manifest 须为映射")
        visible, skipped = select(index, manifest, args.manifest.parent, args.through_seq)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        parser.exit(1, f"参考筛选失败: {exc}\n")
    print(json.dumps(visible, ensure_ascii=False, indent=2))
    if skipped:
        print(f"{skipped} 条来源章序无法唯一核实，已略过；未输出其描述。", file=sys.stderr)


if __name__ == "__main__":
    main()
