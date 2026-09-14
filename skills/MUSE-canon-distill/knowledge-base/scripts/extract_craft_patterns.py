"""
KB 技巧层·手艺 sidecar 提取（prepare/ingest 两段式；本脚本零 LLM 调用）。

把既有 craft_notes/*.md（自由 Markdown 节拍标注）结构化为伴生 .yaml sidecar，
共存不替代。语义提取由订阅原生会话（Claude Code subagent / Codex）完成：
  --prepare  装配任务包（craft_notes 原文 + 字段说明 + 输出契约）
  --ingest   校验会话产出的提取文件，分配 pattern_id 后写伴生 .yaml

用法::

    python extract_craft_patterns.py --prepare --novel 白鹿原 --limit 30 \
        --out tmp/annotation-tasks/craft_patterns.task.json
    # （订阅原生会话读任务包 → 产出提取文件，结构见任务包内 output_contract）
    python extract_craft_patterns.py --ingest tmp/annotation-tasks/craft_patterns.out.json

pattern_id 由脚本顺序分配（{scene_id}-p{n}，不交模型），全局引用 = 书名 + pattern_id。
prepare 默认只处理无伴生 .yaml 的 .md（断点续标）；--force 重提。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

try:
    from . import kb_index
except ImportError:
    import kb_index

KB_ROOT = Path(__file__).resolve().parent.parent
CONTAINER_DIRS = ("novels", "dramas")
DIMENSION_ENUM_BY_MEDIUM = {
    "novel": {"camera", "verb", "omission", "info_density", "overall"},
    "drama": {"monologue", "blocking", "transition", "exchange", "overall"},
}
DIMENSION_ENUM = DIMENSION_ENUM_BY_MEDIUM["novel"]
PATTERN_FIELDS = [
    "beat",
    "dimension",
    "original_move",
    "transfer_rule",
    "quote",
]
OPTIONAL_PATTERN_FIELDS = ("ai_default_failure",)
NARRATIVE_ORGANIZATION_FIELDS = {
    "presentation",
    "transition_anchor",
    "knowledge_change",
    "cross_thread_effect",
    "effect",
    "source_anchor",
}

INSTRUCTIONS_BY_MEDIUM = {
    "novel": """medium=novel 的条目是名著场景的节拍级手艺标注（自由 Markdown）。把每份结构化为三类信息：

- patterns: 对象列表（按原作实际手艺密度选择值得解释的节拍），每对象保留以下内容：
  - beat: 节拍名（沿用原标注）
  - dimension: 只能取 camera / verb / omission / info_density / overall——该条手艺最核心的维度（镜头/动词/省略/信息量/整体特征）
  - original_move: 原作的具体做法与生效条件
  - ai_default_failure: 可选；仅提取原标注有依据的失败对照，不补造模型行为
  - transfer_rule: 迁移规则——说明何时适用、哪些条件必须保留
  - quote: 支撑该条的原句引用，保留理解所需语境
- overall_traits: 字符串列表——原标注中有依据的整体特征；没有则输出空列表
- narrative_organization: 可选对象——原标注「叙事组织」存在时，按需提取 presentation / transition_anchor / knowledge_change / cross_thread_effect / effect / source_anchor；只保留原标注有依据的字段

只提取原标注支持的内容；输出合法 JSON，按 JSON 规则转义引用。""",
    "drama": """medium=drama 的条目是剧作场景的节拍级手艺标注（自由 Markdown）。把每份结构化为三类信息：

- patterns: 对象列表（按原作实际手艺密度选择值得解释的节拍），每对象保留以下内容：
  - beat: 节拍名（沿用原标注）
  - dimension: 只能取 monologue / blocking / transition / exchange / overall——该条手艺最核心的维度（独白旁白/上下场调度/转场/对白攻防/整体特征）
  - original_move: 原剧的具体做法与生效条件
  - ai_default_failure: 可选；仅提取原标注有依据的失败对照，不补造模型行为
  - transfer_rule: 迁移规则——说明何时适用、哪些条件必须保留
  - quote: 支撑该条的台词或舞台指示引用，保留理解所需语境
- overall_traits: 字符串列表——原标注中有依据的整体特征；没有则输出空列表
- narrative_organization: 可选对象——原标注「叙事组织」存在时，按需提取 presentation / transition_anchor / knowledge_change / cross_thread_effect / effect / source_anchor；只保留原标注有依据的字段

只提取原标注支持的内容；输出合法 JSON，按 JSON 规则转义引用。""",
}


def _work_of_notes(md_path: Path) -> Path:
    container, work = md_path.relative_to(KB_ROOT).parts[:2]
    return KB_ROOT / container / work


def _medium_of_notes(md_path: Path) -> str:
    return "drama" if _work_of_notes(md_path).parent.name == "dramas" else "novel"


def _scene_id_from_notes_path(path: Path) -> str:
    for scene_id, notes in kb_index.craft_notes_paths(_work_of_notes(path)).items():
        if notes == path:
            return scene_id
    m = re.match(r"scene_(.+)_beats\.md$", path.name)
    if not m:
        raise ValueError(f"无法从文件名解析 scene_id: {path}")
    return m.group(1)


def collect_todo(
    novel: str | None = None,
    scene_id: str | None = None,
    force: bool = False,
    limit: int = 10,
) -> list[Path]:
    todo: list[Path] = []
    for container in CONTAINER_DIRS:
        root = KB_ROOT / container
        if not root.exists():
            continue
        for work_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            if novel and novel not in work_dir.name:
                continue
            for sid, md_path in sorted(kb_index.craft_notes_paths(work_dir).items()):
                if not md_path.is_file():
                    continue
                if scene_id and sid != scene_id:
                    continue
                if not force and md_path.with_suffix(".yaml").exists():
                    continue
                todo.append(md_path)
                if len(todo) >= limit:
                    return todo
    return todo


def parse_extraction(raw: str, scene_id: str, medium: str = "novel") -> dict:
    enum = DIMENSION_ENUM_BY_MEDIUM[medium]
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if "```" in s[3:] else s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("输出中无 JSON 对象")
    data = json.loads(s[start:end + 1])
    patterns = data.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("patterns 必须是非空列表")

    cleaned = []
    for i, pattern in enumerate(patterns, start=1):
        if not isinstance(pattern, dict):
            raise ValueError("pattern 必须是对象")
        missing = [f for f in PATTERN_FIELDS if not isinstance(pattern.get(f), str) or not pattern[f].strip()]
        if missing:
            raise ValueError(f"pattern 缺字段 {missing}")
        if pattern["dimension"] not in enum:
            raise ValueError(f"dimension 非法值: {pattern['dimension']}（medium={medium}）")
        optional = {}
        for field in OPTIONAL_PATTERN_FIELDS:
            value = pattern.get(field)
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                raise ValueError(f"{field} 必须是字符串")
            optional[field] = value
        cleaned.append(
            {
                "pattern_id": f"{scene_id}-p{i}",
                **{f: pattern[f] for f in PATTERN_FIELDS},
                **optional,
            }
        )
    traits = data.get("overall_traits", [])
    if not isinstance(traits, list) or any(not isinstance(t, str) for t in traits):
        raise ValueError("overall_traits 必须是字符串列表（可为空）")
    organization = data.get("narrative_organization")
    if organization is None:
        clean_organization = None
    elif not isinstance(organization, dict):
        raise ValueError("narrative_organization 必须是对象或 null")
    else:
        unknown = set(organization) - NARRATIVE_ORGANIZATION_FIELDS
        if unknown:
            raise ValueError(f"narrative_organization 含未知字段: {sorted(unknown)}")
        clean_organization = {}
        for key, value in organization.items():
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                raise ValueError(f"narrative_organization.{key} 必须是字符串")
            clean_organization[key] = value.strip()
        if not clean_organization:
            clean_organization = None
    return {
        "patterns": cleaned,
        "overall_traits": traits,
        "narrative_organization": clean_organization,
    }


def write_sidecar(path: Path, scene_id: str, source_notes: str, data: dict) -> None:
    payload = {
        "scene_id": scene_id,
        "source_notes": source_notes,
        "patterns": data["patterns"],
        "overall_traits": data.get("overall_traits", []),
    }
    if data.get("narrative_organization"):
        payload["narrative_organization"] = data["narrative_organization"]
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(path)


def _find_notes_path(novel: str, scene_id: str) -> Path | None:
    for container in CONTAINER_DIRS:
        p = kb_index.craft_notes_paths(KB_ROOT / container / novel).get(scene_id)
        if p is not None and p.is_file():
            return p
    return None


def prepare(args: argparse.Namespace) -> int:
    todo = collect_todo(args.novel, args.scene_id, args.force, args.limit)
    if not todo:
        print("无待提取 craft_notes（已全提取或过滤为空）")
        return 0
    items = []
    mediums: set[str] = set()
    for md_path in todo:
        medium = _medium_of_notes(md_path)
        mediums.add(medium)
        items.append(
            {
                "novel": _work_of_notes(md_path).name,
                "medium": medium,
                "scene_id": _scene_id_from_notes_path(md_path),
                "notes_text": md_path.read_text(encoding="utf-8"),
            }
        )
    task = {
        "layer": "craft_patterns",
        "instructions": {m: INSTRUCTIONS_BY_MEDIUM[m] for m in sorted(mediums)},
        "output_contract": {
            "说明": "把提取产物写为一个 JSON 文件（UTF-8），结构如下；随后用 --ingest 校验写回。"
                  "pattern_id 由脚本分配，不要自行编号；dimension 枚举按该条目的 medium 取对应 instructions",
            "extractions": [
                {
                    "novel": "<与任务包一致>",
                    "scene_id": "<与任务包一致，原样照抄禁止改写格式>",
                    "patterns": [{f: "..." for f in PATTERN_FIELDS}],
                    "overall_traits": ["..."],
                    "narrative_organization": {
                        "presentation": "...",
                        "transition_anchor": "...",
                        "knowledge_change": "...",
                        "cross_thread_effect": "...",
                        "effect": "...",
                        "source_anchor": "...",
                    },
                }
            ],
        },
        "items": items,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"任务包已写入: {out}（{len(items)} 份）")
    return 0


def ingest(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.ingest).read_text(encoding="utf-8"))
    items = data.get("extractions") or []
    if not items:
        print("[extract_craft_patterns INGEST_ERROR] 产出文件无 extractions", file=sys.stderr)
        return 2
    accepted = rejected = 0
    for item in items:
        novel, sid = item.get("novel"), item.get("scene_id")
        md_path = _find_notes_path(novel, sid) if novel and sid else None
        if md_path is None:
            print(f"  ✗ {novel}·{sid}: 找不到对应 craft_notes md", file=sys.stderr)
            rejected += 1
            continue
        try:
            payload = parse_extraction(
                json.dumps(
                    {
                        "patterns": item.get("patterns"),
                        "overall_traits": item.get("overall_traits", []),
                        "narrative_organization": item.get("narrative_organization"),
                    },
                    ensure_ascii=False,
                ),
                sid,
                _medium_of_notes(md_path),
            )
        except ValueError as e:
            print(f"  ✗ {novel}·{sid}: {e}", file=sys.stderr)
            rejected += 1
            continue
        if not args.dry_run:
            write_sidecar(md_path.with_suffix(".yaml"), sid, md_path.name, payload)
        accepted += 1
        print(f"  ✓ {novel}·{sid}（{len(payload['patterns'])} patterns）")
    print(f"接受 {accepted} / 拒收 {rejected}{'（dry-run 未写回）' if args.dry_run else ''}")
    return 0 if rejected == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="手艺 sidecar 提取（prepare/ingest，零 LLM 调用）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="装配任务包")
    mode.add_argument("--ingest", type=str, metavar="FILE", help="校验并写回提取产出文件")
    parser.add_argument("--novel", default=None, help="书名子串过滤（prepare）")
    parser.add_argument("--scene-id", default=None, help="精确场景 ID（prepare）")
    parser.add_argument("--limit", type=int, default=10, help="任务包最多份数（prepare）")
    parser.add_argument("--force", action="store_true", help="已有 sidecar 也重提（prepare）")
    parser.add_argument("--out", type=str, default="tmp/annotation-tasks/craft_patterns.task.json",
                        help="任务包输出路径（prepare）")
    parser.add_argument("--dry-run", action="store_true", help="ingest 只校验不写回")
    args = parser.parse_args()

    if args.prepare:
        return prepare(args)
    return ingest(args)


if __name__ == "__main__":
    sys.exit(main())
