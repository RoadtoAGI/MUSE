#!/usr/bin/env python3
"""
generate_phase6_index.py - 生成 phase6_development.yaml 骨架

从 phase5_scenes.yaml 提取设计字段（scene_id, arc_id, sequence_id, title），
从 scenes/*.md 统计实际字数，合并输出骨架 YAML。
orchestrator 只需补 summary 和 beats。

用法：
    python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_phase6_index.py <work_dir>

输出：
    <work_dir>/pipeline/phase6_development.yaml
"""

import re
import sys
from pathlib import Path

import yaml

from yaml_resilient import load_yaml_resilient


def count_words(text: str) -> int:
    """中英文混合字数统计：中文按字，英文按词。"""
    # 英文单词
    english = re.findall(r"[a-zA-Z]+(?:\'[a-zA-Z]+)?", text)
    # 中文字符
    chinese = re.findall(r"[一-鿿]", text)
    return len(english) + len(chinese)


def parse_phase5_scenes(yaml_path: Path) -> list[dict]:
    """按 Phase 5 的呈现顺序读取场景设计，保留所属序列。"""
    data, report = load_yaml_resilient(yaml_path.read_text(encoding="utf-8"))
    data = data or {}
    if report.recovered_lines:
        sys.stderr.write(
            f"[WARN] {yaml_path}: auto-recovered broken double-quoted scalars "
            f"at line(s) {report.recovered_lines} (promoted to block scalar).\n"
        )

    scenes = []
    seen = set()
    for seq in data.get("sequence_expansions") or []:
        seq_id = seq.get("seq_id") or seq.get("sequence_id")
        seq_arc_id = seq.get("arc_id")
        for scene in seq.get("scenes") or []:
            sid = scene.get("scene_id")
            if not isinstance(sid, str) or not sid.strip():
                raise ValueError("Every Phase 5 scene requires a non-empty scene_id")
            if sid in seen:
                raise ValueError(f"Duplicate scene_id in Phase 5: {sid}")
            seen.add(sid)
            scenes.append({
                "scene_id": str(sid),
                # scene 自带 sequence_id 优先，否则继承自所属 sequence_expansions 项
                "sequence_id": str(scene.get("seq_id") or scene.get("sequence_id") or seq_id or ""),
                "arc_id": str(scene.get("arc_id") or seq_arc_id or ""),
                "title": str(scene.get("title") or ""),
            })

    return scenes


def main():
    if len(sys.argv) != 2:
        print("用法：python generate_phase6_index.py <work_dir>", file=sys.stderr)
        sys.exit(1)

    work_dir = Path(sys.argv[1]).resolve()
    phase5_path = work_dir / "pipeline" / "phase5_scenes.yaml"
    scenes_dir = work_dir / "pipeline" / "scenes"
    output_path = work_dir / "pipeline" / "phase6_development.yaml"

    # Phase 5 是场景集合与呈现顺序的权威；目录中的其他正文不进入索引。
    design = parse_phase5_scenes(phase5_path)
    if not design:
        raise ValueError(f"No scenes found in {phase5_path}")
    previous = yaml.safe_load(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}
    previous = previous or {}
    previous_by_id = {
        entry["scene_id"]: entry for entry in previous.get("scenes", [])
        if isinstance(entry, dict) and entry.get("scene_id")
    }
    entries = []
    total_words = 0
    for info in design:
        sid = info["scene_id"]
        path = scenes_dir / f"scene_{sid}.md"
        wc = count_words(path.read_text(encoding="utf-8")) if path.exists() else 0
        total_words += wc
        entry = {
            **info,
            "file_path": f"pipeline/scenes/scene_{sid}.md",
            "summary": previous_by_id.get(sid, {}).get("summary", ""),
            "approximate_words": wc,
        }
        if "beats" in previous_by_id.get(sid, {}):
            entry["beats"] = previous_by_id[sid]["beats"]
        entries.append(entry)

    output_path.write_text(
        yaml.safe_dump({"scenes": entries, "total_word_count": total_words},
                       allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"✓ phase6_development.yaml 已更新：{len(entries)} 个场景，{total_words} 词")
    print(f"  路径：{output_path}")


if __name__ == "__main__":
    main()
