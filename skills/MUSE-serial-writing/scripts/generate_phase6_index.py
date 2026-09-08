#!/usr/bin/env python3
"""按 Phase 5 的呈现顺序生成完整 Phase 6 场景索引。

用法：python3 generate_phase6_index.py <chapter_work_dir>
设计场景即使尚未写出正文也保留在索引中；正文仅提供实际字数。
同 ID 已有的 file_path、summary、beats 等资料继续保留，新增场景使用默认路径。
拼接前由 assemble_story.py 检查正文完整性。
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import yaml

from yaml_resilient import load_yaml_resilient


def count_words(text: str) -> int:
    """中文按字，英文按词。"""
    return len(re.findall(r"[a-zA-Z]+(?:\'[a-zA-Z]+)?", text)) + len(re.findall(r"[一-鿿]", text))


def parse_phase5_scenes(yaml_path: Path) -> list[dict]:
    """读取顶层 scenes 或 sequence_expansions 的呈现顺序及归属字段。"""
    data, report = load_yaml_resilient(yaml_path.read_text(encoding="utf-8"))
    if report.recovered_lines:
        print(f"[WARN] {yaml_path}: scalar recovered at lines {report.recovered_lines}", file=sys.stderr)
    if not isinstance(data, dict):
        raise ValueError(f"{yaml_path} 顶层必须为映射")
    if data.get("scenes") and data.get("sequence_expansions"):
        raise ValueError("Phase 5 应使用一种场景存储形态，不能同时提供两份非空场景列表")
    if data.get("scenes"):
        groups = [{"scenes": data["scenes"]}]
    else:
        groups = data.get("sequence_expansions")
    if not isinstance(groups, list) or not groups:
        raise ValueError("Phase 5 缺非空 scenes 或 sequence_expansions 列表")

    result: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("scenes"), list):
            raise ValueError("Phase 5 每个序列必须含 scenes 列表")
        for scene in group["scenes"]:
            if not isinstance(scene, dict):
                raise ValueError("Phase 5 场景必须为映射")
            sid = scene.get("scene_id")
            if not isinstance(sid, str) or not sid.strip() or Path(sid).name != sid:
                raise ValueError(f"Phase 5 scene_id 无效：{sid!r}")
            if sid in seen:
                raise ValueError(f"Phase 5 scene_id 重复：{sid}")
            seen.add(sid)
            result.append({
                "scene_id": sid,
                "sequence_id": scene.get("sequence_id") or group.get("sequence_id") or group.get("seq_id") or "",
                "arc_id": scene.get("arc_id") or group.get("arc_id") or "",
                "title": scene.get("title") or "",
            })
    if not result:
        raise ValueError("Phase 5 无设计场景")
    return result


def generate(work_dir: Path) -> dict:
    design = parse_phase5_scenes(work_dir / "pipeline" / "phase5_scenes.yaml")
    output_path = work_dir / "pipeline" / "phase6_development.yaml"
    prior = yaml.safe_load(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}
    if not isinstance(prior, dict):
        raise ValueError("已有 Phase 6 索引顶层必须为映射")
    old_entries = prior.get("scenes", [])
    if not isinstance(old_entries, list):
        raise ValueError("已有 Phase 6 scenes 必须为列表")
    by_id: dict[str, dict] = {}
    for entry in old_entries:
        if not isinstance(entry, dict):
            raise ValueError("已有 Phase 6 场景必须为映射")
        sid = entry.get("scene_id") or entry.get("id")
        if not isinstance(sid, str) or not sid or sid in by_id:
            raise ValueError(f"已有 Phase 6 scene_id 缺失或重复：{sid!r}")
        by_id[sid] = entry

    entries = []
    total_words = 0
    scene_root = (work_dir / "pipeline" / "scenes").resolve()
    for info in design:
        sid = info["scene_id"]
        entry = dict(by_id.get(sid, {}))
        entry.update(info)
        file_path = entry.get("file_path") or f"pipeline/scenes/scene_{sid}.md"
        if not isinstance(file_path, str):
            raise ValueError(f"{sid} file_path 必须为字符串")
        path = (work_dir / file_path).resolve()
        if path != (scene_root / f"scene_{sid}.md").resolve():
            raise ValueError(f"{sid} file_path 与本场审阅正文不一致：{file_path}")
        if not path.is_relative_to(work_dir) or not path.is_relative_to(scene_root) or path.suffix.lower() != ".md":
            raise ValueError(f"{sid} file_path 须在本章 pipeline/scenes/ 内：{file_path}")
        if path.exists() and not path.is_file():
            raise ValueError(f"{sid} file_path 不是文件：{file_path}")
        word_count = count_words(path.read_text(encoding="utf-8")) if path.is_file() else 0
        entry.update(file_path=file_path, approximate_words=word_count)
        if "word_count" in entry:
            entry["word_count"] = word_count
        entry.setdefault("summary", "")
        entries.append(entry)
        total_words += word_count
    return {**prior, "scenes": entries, "total_word_count": total_words}


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python3 generate_phase6_index.py <chapter_work_dir>", file=sys.stderr)
        return 1
    work_dir = Path(sys.argv[1]).resolve()
    from extract_scene_card import _verify_prose_risk_contract_used
    _verify_prose_risk_contract_used(work_dir)
    temporary: Path | None = None
    try:
        data = generate(work_dir)
        output_path = work_dir / "pipeline" / "phase6_development.yaml"
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output_path.parent,
            prefix=".phase6-index-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        temporary.replace(output_path)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"[generate_phase6_index ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f"phase6_development.yaml 已更新：{len(data['scenes'])} 个设计场景，{data['total_word_count']} 字词")
    return 0


if __name__ == "__main__":
    sys.exit(main())
