"""
KB 文风层·作品文风卡蒸馏（prepare/ingest 两段式；本脚本零 LLM 调用）。

语义蒸馏由订阅原生会话（Claude Code subagent / Codex）完成——脚本只做确定性两端：
  --prepare  已有标注与来源 + 装配任务包（全书 style_profile 聚合 + 抽样原文 + 同作者 peer 卡）
  --ingest   校验会话产出的文风卡文件，组装 provenance 后写 style_card.yaml

用法::

    python distill_work_style.py --prepare --novel 神雕 \
        --out tmp/annotation-tasks/style_card.task.json
    # （订阅原生会话读任务包 → 产出文风卡文件，结构见任务包内 output_contract）
    python distill_work_style.py --ingest tmp/annotation-tasks/style_card.out.json

至少需要已有场景画像供聚合；--min-style-profile-count 可由当前任务显式提高，
默认不设额外场景配额。样本数量不能证明全书代表性。同作者其他作品的 style_card 作为共性
参照进任务包（"作者蒸馏"），落 author_cross_ref 字段——不建独立 author 实体。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

try:
    from . import kb_index
except ImportError:
    import kb_index

KB_ROOT = Path(__file__).resolve().parent.parent
CONTAINER_DIRS = ("novels", "dramas")
SAMPLE_SCENES = 3
SAMPLE_CHARS = 2000

DIM_FIELDS_BY_MEDIUM = {
    "novel": ["narration_voice", "diction", "rhetoric_density", "dialogue_mode", "pacing"],
    "drama": ["dialogue_voice", "diction", "rhetoric_density", "stage_direction_style", "pacing"],
}
EXTRA_FIELDS = ["signature_moves", "anti_signature", "author_cross_ref"]
CARD_FIELDS_BY_MEDIUM = {m: dims + EXTRA_FIELDS for m, dims in DIM_FIELDS_BY_MEDIUM.items()}
CARD_FIELDS = CARD_FIELDS_BY_MEDIUM["novel"]
LIST_FIELDS = {
    "signature_moves",
    "anti_signature",
}
RHETORIC_ENUM = {"low", "medium", "high"}

INSTRUCTIONS_BY_MEDIUM = {
    "novel": """基于任务包材料为该作品蒸馏一张全书文风卡，8 个字段：

- narration_voice / diction / rhetoric_density（只能 low/medium/high）/ dialogue_mode / pacing：与场景画像同维同名，但海拔是已读范围的聚合——按证据描述共性与重要差异，保留关系、题材和时点条件；不凭样本数宣称全书一律如此。
- signature_moves：字符串列表——有证据的代表性表达机制及成立条件；无有用条目时可为空。
- anti_signature：字符串列表——会丢失所述表达机制的近边界写法及原因；缺比较依据时可为空，不补造普遍禁令。
- author_cross_ref：若任务包提供了同作者其他作品文风卡，输出一句话共性/差异；未提供则输出空字符串。

samples 是原文预览；text_truncated 为 true 时，source_path 可取得完整场景。按需回读差异与条件，避免以开头代表全场。译文体现原作与翻译的共同选择，只就当前版本说明观察，不凭译文概括作者母语文风。""",
    "drama": """基于任务包材料为该剧作蒸馏一张全剧文风卡，8 个字段：

- dialogue_voice / diction / rhetoric_density（只能 low/medium/high）/ stage_direction_style / pacing：与场景画像同维同名，但海拔是已读范围的聚合——描述共性、媒介约定与场次差异，保留作用条件，不把某场特例概括成全剧定律。
- signature_moves：字符串列表——有证据的代表性表达机制及成立条件；无有用条目时可为空。
- anti_signature：字符串列表——会丢失所述表达机制的近边界写法及原因；缺比较依据时可为空，不补造普遍禁令。
- author_cross_ref：若任务包提供了同作者其他作品文风卡，输出一句话共性/差异；未提供则输出空字符串。

samples 是预览；text_truncated 为 true 时沿 source_path 回读所需原文。译本的措辞、韵文与舞台指示按当前版本观察，不把翻译或演出本选择一律归给作者。""",
}


class CoverageError(Exception):
    """场景级 style_profile 覆盖不足，不能蒸馏作品卡。"""


def _work_dirs() -> list[Path]:
    dirs: list[Path] = []
    for container in CONTAINER_DIRS:
        root = KB_ROOT / container
        if root.exists():
            dirs.extend(sorted(p for p in root.iterdir() if p.is_dir()))
    return dirs


def _find_work_dir(novel_filter: str) -> Path:
    matches = [p for p in _work_dirs() if novel_filter in p.name and kb_index.index_path_of(p) is not None]
    if not matches:
        raise ValueError(f"未找到作品: {novel_filter}")
    if len(matches) > 1:
        raise ValueError(f"作品过滤不唯一: {novel_filter} -> {', '.join(p.name for p in matches)}")
    return matches[0]


def _sample_entries(entries: list[dict]) -> list[dict]:
    if len(entries) <= SAMPLE_SCENES:
        return entries
    return [entries[0], entries[len(entries) // 2], entries[-1]]


def collect_inputs(novel_filter: str, min_count: int = 1) -> dict:
    work_dir = _find_work_dir(novel_filter)
    index_path = kb_index.index_path_of(work_dir)
    medium = kb_index.medium_of(index_path)
    index = kb_index.load_index(index_path)
    profiles = [
        {
            "scene_id": e.get("scene_id"),
            "description": e.get("description") or e.get("dramatic_purpose") or e.get("title"),
            "style_profile": e.get("style_profile"),
        }
        for e in index
        if e.get("style_profile")
    ]
    if len(profiles) < min_count:
        raise CoverageError(
            f"{work_dir.name} 只有 {len(profiles)} 条 style_profile，低于 {min_count}；"
            "请先运行 annotate_style_profile.py 补足场景级标注。"
        )

    samples = []
    for entry in _sample_entries(index):
        rel_file = entry.get("file")
        if not rel_file:
            continue
        try:
            source_path = (work_dir / rel_file).resolve()
            text = source_path.read_text(encoding="utf-8")
        except OSError:
            continue
        samples.append(
            {
                "scene_id": entry.get("scene_id"),
                "description": entry.get("description") or entry.get("dramatic_purpose") or entry.get("title"),
                "text": text[:SAMPLE_CHARS],
                "source_path": str(source_path),
                "text_truncated": len(text) > SAMPLE_CHARS,
            }
        )

    first = index[0] if index else {}
    author = first.get("author", "")
    peer_cards = []
    for peer_dir in _work_dirs():
        if peer_dir == work_dir:
            continue
        peer_index_path = kb_index.index_path_of(peer_dir)
        peer_card_path = peer_dir / "style_card.yaml"
        if peer_index_path is None or not peer_card_path.exists():
            continue
        if kb_index.medium_of(peer_index_path) != medium:
            continue
        try:
            peer_index = kb_index.load_index(peer_index_path)
            peer_author = (peer_index[0] or {}).get("author") if peer_index else ""
            if author and peer_author == author:
                peer_cards.append(peer_card_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue

    translator = first.get("translator", "")
    meta_path = work_dir / "work-meta.yaml"
    if not translator and meta_path.exists():
        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            translator = meta.get("translator") or ""
        except (OSError, ValueError, yaml.YAMLError):
            pass

    return {
        "work_dir": work_dir,
        "medium": medium,
        "novel": work_dir.name,
        "author": author,
        "lang": first.get("lang") or first.get("language", ""),
        "translator": translator,
        "profiles": profiles,
        "samples": samples,
        "peer_cards": peer_cards,
    }


def parse_card(raw: str, medium: str = "novel") -> dict:
    fields = CARD_FIELDS_BY_MEDIUM[medium]
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if "```" in s[3:] else s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("输出中无 JSON 对象")
    card = json.loads(s[start:end + 1])
    missing = [f for f in fields if f not in card]
    if missing:
        raise ValueError(f"缺字段 {missing}（medium={medium}）")
    for field in LIST_FIELDS:
        if not isinstance(card.get(field), list) or any(not isinstance(item, str) for item in card[field]):
            raise ValueError(f"{field} 必须是字符串列表（可为空）")
    if card["rhetoric_density"] not in RHETORIC_ENUM:
        raise ValueError(f"rhetoric_density 非法值: {card['rhetoric_density']}")
    voice_field = fields[0]
    if not card.get(voice_field):
        raise ValueError(f"{voice_field} 不能为空")
    return {f: card[f] for f in fields}


def assemble_card_yaml(inputs: dict, card: dict, model: str) -> str:
    payload = {
        "novel": inputs["novel"],
        "author": inputs.get("author", ""),
        "lang": inputs.get("lang", ""),
        "translator": inputs.get("translator", ""),
        **card,
        "style_card_by": model,
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def prepare(args: argparse.Namespace) -> int:
    try:
        inputs = collect_inputs(args.novel, args.min_style_profile_count)
    except CoverageError as e:
        print(f"[distill_work_style COVERAGE_ERROR] {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"[distill_work_style INPUT_ERROR] {e}", file=sys.stderr)
        return 2

    out_path = inputs["work_dir"] / "style_card.yaml"
    if out_path.exists() and not args.force:
        print(f"style_card 已存在，跳过: {out_path}（--force 重蒸馏）")
        return 0

    card_fields = CARD_FIELDS_BY_MEDIUM[inputs["medium"]]
    task = {
        "layer": "style_card",
        "novel": inputs["novel"],
        "medium": inputs["medium"],
        "author": inputs.get("author", ""),
        "lang": inputs.get("lang", ""),
        "instructions": INSTRUCTIONS_BY_MEDIUM[inputs["medium"]],
        "output_contract": {
            "说明": "把文风卡写为一个 JSON 文件（UTF-8），结构如下；随后用 --ingest 校验写回",
            "annotated_by": "<执行蒸馏的模型名>",
            "novel": inputs["novel"],
            "card": {f: ("[...]" if f in LIST_FIELDS else "...") for f in card_fields},
        },
        "profiles": inputs["profiles"],
        "samples": inputs["samples"],
        "peer_cards": inputs["peer_cards"],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"任务包已写入: {out}（profiles={len(inputs['profiles'])} peers={len(inputs['peer_cards'])}）")
    return 0


def ingest(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.ingest).read_text(encoding="utf-8"))
    novel = data.get("novel")
    if not novel:
        print("[distill_work_style INGEST_ERROR] 产出文件缺 novel", file=sys.stderr)
        return 2
    try:
        inputs = collect_inputs(novel, min_count=0)
    except ValueError as e:
        print(f"[distill_work_style INPUT_ERROR] {e}", file=sys.stderr)
        return 2
    try:
        card = parse_card(json.dumps(data.get("card") or {}, ensure_ascii=False), inputs["medium"])
    except ValueError as e:
        print(f"[distill_work_style INGEST_ERROR] {e}", file=sys.stderr)
        return 1

    if inputs.get("author") and inputs.get("lang") == "zh" and not inputs.get("translator"):
        print("[distill_work_style WARN] 非中文作者的译者信息若缺失，需人工确认 translator 字段。", file=sys.stderr)

    text = assemble_card_yaml(inputs, card, data.get("annotated_by") or "unknown")
    out_path = inputs["work_dir"] / "style_card.yaml"
    if args.dry_run:
        print(text)
    else:
        tmp = out_path.with_suffix(".yaml.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(out_path)
        print(f"写入: {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="作品级 style_card（prepare/ingest，零 LLM 调用）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="已有标注与来源 + 装配任务包")
    mode.add_argument("--ingest", type=str, metavar="FILE", help="校验并写回文风卡产出文件")
    parser.add_argument("--novel", help="书名子串过滤，必须唯一（prepare）")
    parser.add_argument("--min-style-profile-count", type=int, default=1, help="当前任务明确需要的场景画像数；默认仅要求有输入")
    parser.add_argument("--force", action="store_true", help="已有 style_card 时仍生成任务包（prepare）")
    parser.add_argument("--out", type=str, default="tmp/annotation-tasks/style_card.task.json",
                        help="任务包输出路径（prepare）")
    parser.add_argument("--dry-run", action="store_true", help="ingest 只打印不写回")
    args = parser.parse_args()

    if args.prepare:
        if not args.novel:
            print("[distill_work_style ARG_ERROR] --prepare 需要 --novel", file=sys.stderr)
            return 2
        return prepare(args)
    return ingest(args)


if __name__ == "__main__":
    sys.exit(main())
