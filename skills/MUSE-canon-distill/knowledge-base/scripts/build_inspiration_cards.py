"""
KB 灵感层建卡（prepare/ingest 两段式；本脚本零 LLM 调用）。

逐书提名可迁移戏剧范式 → 跨书聚类为 inspiration cards。语义工作（提名/聚类）
由订阅原生会话（Claude Code subagent / Codex）完成，脚本只做确定性两端：

  --stage nominate --prepare [--novel X] [--force] [--out DIR]
      每书一个任务包 {书名}.task.json（逆向设计文档 + 场景清单 + 手艺特征）
  --stage nominate --ingest FILE
      校验提名文件（含佐证 scene_id 存在性 + exact join）→ _nominations/{书名}.json
  --stage cluster --prepare [--out PATH]
      聚合全部提名 + 每书 scene_id 清单 → 聚类任务包
  --stage cluster --ingest FILE [--replace]
      校验卡片（schema / card_id / 佐证存在性 + exact join）→ 写卡 + 重建索引
  --from-nominations
      等价 --stage cluster（重入语义，配 --prepare / --ingest 使用）
  --stage index
      仅重建 index.md + _backlinks.json（卡文件为源）

产物：inspiration/{card_id}.yaml + index.md（人读）+ _backlinks.json（机读反查，
kb_query 灵感 lite 消费）。_nominations/ 是中间产物不是消费面。
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
INSPIRATION_DIR = KB_ROOT / "inspiration"
CONTAINER_DIRS = ("novels", "dramas")
CARD_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEQ_ID_RE = re.compile(r"^(?:ins|card)-\d+$")  # 顺序编号不是语义 slug，拒收
LEGACY_NEGATIVE_PREFIXES = ("不要照抄", "不要照搬", "不要复制", "不要")

CARD_FIELDS = [
    "card_id",
    "pattern_name",
    "dramatic_function",
    "applicability",
    "reuse_candidates",
    "tags",
    "source_scenes",
]
# phase_affinity 可选；存在时归一为 0-5 整数列表

NOMINATION_FIELDS = [
    "pattern_name",
    "dramatic_function",
    "applicability",
    "reuse_candidates",
    "tags",
    "evidence_scenes",
]

# Optional on stored cards; prepare asks new analyses to provide both fields.
ANALYSIS_FIELDS = ("mechanism", "source_analyses")

NOMINATE_INSTRUCTIONS = """从该作品的逆向设计文档、场景清单和手艺特征中，提名有原作证据的可迁移构思机制。范围包括思想认识、人物关系、规则、情节和阅读经验。原作没有相应机制时不凑数。
先沿任务包 source_root 与场景 file 回读决定机制成立的原文，按需补读铺垫和后果。摘要与模型记忆提供线索；原作事实、分析解释、作者自述各有归属。每条保留以下信息：

- pattern_name: 能辨认机制的范式中文名
- dramatic_function: 它解决什么叙事或思想问题，改变什么理解或经验（检索摘要）
- applicability: 适用条件 + 失效边界（检索摘要，详细条件进入 source_analyses）
- reuse_candidates: 字符串列表——可直接复用或复制的本书表层元素候选
- tags: 字符串列表——能区分机制的中文检索词
- evidence_scenes: 对象列表 [{"scene_id": "...", "note": "一句话佐证"}]；note 说明相关尺度的状态变化、相邻节拍关系或阅读结果，按原作实际机制取舍；
  scene_id 必须从场景清单原样照抄。可附 line_start / line_end（场景文件内从 1 开始的闭区间），定位核心、铺垫或兑现；不填时回读完整场景。
- mechanism: 可在新作品重建的关系、因果或感知结构；说明共同条件，保留有解释力的具体关系
- source_analyses: 按原作实例写列表，每项含 novel（本书目录名）、creative_move（具体创意及其作用）、narrative_reason（文本事实如何支持对效果的解释）、transfer_conditions（迁移条件与容易失效处）、source_scene_ids（引用本条 evidence_scenes 的 scene_id 列表）。narrative_reason 中的 motivation 指叙事理由；作者本人动机只在有来源时另写 author_motivation: {claim, source}。
- phase_affinity: 可选，整数列表 0-5——主要被哪些设计 phase 消费（构想0/世界1/人物2/脊椎3/结构4/编排5）

思想分析追踪认识如何由具体经验形成、复杂化或保持多义；选择和冲突按作品需要分析。重复、留白、静态人物也可产生有效机制。source_analyses 保留足够语境，不用主题标签替代成立过程。

字段值内禁止英文双引号，引用字词用「」。"""

CLUSTER_INSTRUCTIONS = """把 nominations 中关系机制及成立条件相容的范式跨书合并，产出最终灵感卡列表。
共同戏剧功能用于归类和检索；只有可重建的关系、因果或感知结构相同才合卡。功能相同而机制不同的实例分别保留，单书机制也可成卡。
合并时保留逐作品 source_analyses、完整来源索引与条件差异；旧提名缺详细分析时沿原作补读后再加工，无法核实时保留原摘要并明确缺口。每卡保留以下信息：

- card_id: 语义化 ASCII kebab-case 英文 slug（如 mentor-death-delayed-reveal），
  全列表唯一；禁止顺序编号（ins-001 之类会被拒收）
- pattern_name / dramatic_function / applicability / reuse_candidates / tags:
  语义同提名；摘要描述共享作用，具体条件保留在逐作品分析中
- mechanism / source_analyses: 语义同提名，source_scene_ids 引用本卡对应 novel 的 source_scenes；作者自述的 claim/source 原样保留
- phase_affinity: 可选，整数列表 0-5
- source_scenes: 对象列表 [{"novel": "...", "scene_id": "...", "note": "..."}]——
  合并自各书 evidence_scenes；novel 与 scene_id 必须原样照抄提名与任务包内
  scene_id 清单，禁止改写格式（不准把 scene_01 规范化成 S01）；原有 line_start / line_end 随来源保留

字段值内禁止英文双引号，引用字词用「」。"""


# ---------------------------------------------------------------------------
# 共享：目录遍历 / 索引映射 / scene_id 归一
# ---------------------------------------------------------------------------
def _work_dirs() -> list[Path]:
    dirs: list[Path] = []
    for container in CONTAINER_DIRS:
        root = KB_ROOT / container
        if root.exists():
            dirs.extend(sorted(p for p in root.iterdir() if p.is_dir()))
    return dirs


def load_idx_map() -> dict[str, set[str]]:
    """{作品名: 该作品全部 scene_id} —— 佐证存在性校验的权威（novels + dramas）。"""
    idx_map: dict[str, set[str]] = {}
    for work_dir in _work_dirs():
        index_path = kb_index.index_path_of(work_dir)
        if index_path is None:
            continue
        try:
            entries = kb_index.load_index(index_path)
            idx_map[work_dir.name] = {e.get("scene_id") for e in entries if e.get("scene_id")}
        except (OSError, ValueError):
            continue
    return idx_map


def normalize_scene_id(novel: str, scene_id: str, idx_map: dict[str, set[str]]) -> str | None:
    """按 scene index 做 exact join；未原样命中时返回 None。"""
    ids = idx_map.get(novel)
    if not ids:
        return None
    return scene_id if scene_id in ids else None


def _normalize_phase_affinity(phases) -> list[int]:
    normalized: list[int] = []
    for phase in phases or []:
        if isinstance(phase, int):
            value = phase
        elif isinstance(phase, str) and phase.strip().isdigit():
            value = int(phase.strip())
        else:
            raise ValueError(f"phase_affinity 非法: {phases}")
        if value not in {0, 1, 2, 3, 4, 5}:
            raise ValueError(f"phase_affinity 非法: {phases}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def _validate_reuse_candidates(candidates) -> None:
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("reuse_candidates 必须是非空列表")
    if not all(isinstance(item, str) and item.strip() for item in candidates):
        raise ValueError("reuse_candidates 元素必须是非空字符串")
    for item in candidates:
        normalized = item.strip()
        prefix = next(
            (value for value in LEGACY_NEGATIVE_PREFIXES if normalized.startswith(value)),
            None,
        )
        if prefix:
            raise ValueError(f"reuse_candidates 含废弃否定前缀: {prefix}")


# ---------------------------------------------------------------------------
# 校验 / 写卡 / 索引
# ---------------------------------------------------------------------------
def _source_window(scene: dict) -> dict:
    """Keep optional scene-local line locators without guessing missing bounds."""
    keys = ("line_start", "line_end")
    if not any(key in scene for key in keys):
        return {}
    start, end = (scene.get(key) for key in keys)
    if (type(start) is not int or type(end) is not int
            or start < 1 or end < start):
        raise ValueError("原文 line_start/line_end 必须是从 1 开始的有效闭区间")
    return dict(zip(keys, (start, end)))


def _source_analyses(data: dict, scenes: list[dict]) -> dict:
    """Validate optional enrichment once at ingest; legacy summaries stay readable."""
    if not any(key in data for key in ANALYSIS_FIELDS):
        return {}
    mechanism = data.get("mechanism")
    analyses = data.get("source_analyses")
    if not isinstance(mechanism, str) or not mechanism.strip():
        raise ValueError("mechanism 必须是非空字符串")
    if not isinstance(analyses, list) or not analyses:
        raise ValueError("source_analyses 必须是非空列表")
    available = {(s["novel"], s["scene_id"]) for s in scenes}
    kept = []
    for analysis in analyses:
        if not isinstance(analysis, dict):
            raise ValueError("source_analyses 条目必须是对象")
        fields = ("novel", "creative_move", "narrative_reason", "transfer_conditions")
        if any(not isinstance(analysis.get(f), str) or not analysis[f].strip() for f in fields):
            raise ValueError("source_analyses 缺 novel/creative_move/narrative_reason/transfer_conditions")
        ids = analysis.get("source_scene_ids")
        if (not isinstance(ids, list) or not ids
                or any(not isinstance(sid, str) or (analysis["novel"], sid) not in available for sid in ids)):
            raise ValueError("source_analyses 的 source_scene_ids 必须引用本卡已保留的同作品佐证")
        clean = {f: analysis[f] for f in fields}
        clean["source_scene_ids"] = ids
        if "author_motivation" in analysis:
            author = analysis["author_motivation"]
            if (not isinstance(author, dict) or any(
                    not isinstance(author.get(f), str) or not author[f].strip()
                    for f in ("claim", "source"))):
                raise ValueError("author_motivation 必须同时提供 claim 与 source")
            clean["author_motivation"] = {f: author[f] for f in ("claim", "source")}
        kept.append(clean)
    return {"mechanism": mechanism, "source_analyses": kept}


def validate_card(card: dict, idx_map: dict[str, set[str]]) -> dict:
    """schema + card_id 形态 + 佐证存在性（含形态归一）。返回清洗后的卡。"""
    legacy_field = "do_" + "not_copy"
    if legacy_field in card:
        raise ValueError(f"{legacy_field} 已废弃，请使用 reuse_candidates")
    missing = [f for f in CARD_FIELDS if f not in card or card[f] in ("", None)]
    if missing:
        raise ValueError(f"缺字段 {missing}")
    card_id = str(card["card_id"])
    if not CARD_ID_RE.match(card_id):
        raise ValueError(f"card_id 非 ascii kebab: {card_id}")
    if SEQ_ID_RE.match(card_id):
        raise ValueError(f"card_id 是顺序编号而非语义 slug: {card_id}")
    if not isinstance(card["tags"], list) or not card["tags"]:
        raise ValueError("tags 必须是非空列表")
    _validate_reuse_candidates(card["reuse_candidates"])

    scenes = card["source_scenes"]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("source_scenes 必须是非空列表")
    kept = []
    for scene in scenes:
        novel, sid = scene.get("novel"), scene.get("scene_id")
        if not novel or not sid or not scene.get("note"):
            raise ValueError("source_scenes 条目缺 novel/scene_id/note")
        real = normalize_scene_id(novel, sid, idx_map)
        if real is None:
            print(f"[build_inspiration_cards WARN] {card_id}: 佐证不存在已剔除 {novel}|{sid}",
                  file=sys.stderr)
            continue
        kept.append({"novel": novel, "scene_id": real, "note": scene["note"],
                     **_source_window(scene)})
    if not kept:
        raise ValueError("source_scenes 全部佐证不存在")

    clean = {f: card[f] for f in CARD_FIELDS}
    clean["source_scenes"] = kept
    clean.update(_source_analyses(card, kept))
    if card.get("phase_affinity"):
        clean["phase_affinity"] = _normalize_phase_affinity(card["phase_affinity"])
    return clean


def write_card(insp_dir: Path, clean: dict) -> Path:
    insp_dir.mkdir(parents=True, exist_ok=True)
    out_path = insp_dir / f"{clean['card_id']}.yaml"
    tmp = out_path.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(clean, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(out_path)
    return out_path


def _iter_card_paths(insp_dir: Path) -> list[Path]:
    if not insp_dir.exists():
        return []
    return sorted(p for p in insp_dir.glob("*.yaml") if not p.name.startswith("_"))


def rebuild_index(insp_dir: Path) -> dict[str, list[str]]:
    """从卡文件重建 index.md（人读）+ _backlinks.json（机读反查）。纯文件操作。"""
    insp_dir.mkdir(parents=True, exist_ok=True)
    cards = []
    backlinks: dict[str, list[str]] = {}
    for path in _iter_card_paths(insp_dir):
        card = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not card.get("card_id"):
            continue
        cards.append(card)
        for scene in card.get("source_scenes") or []:
            key = f"{scene.get('novel')}|{scene.get('scene_id')}"
            backlinks.setdefault(key, []).append(card["card_id"])

    lines = ["# 灵感卡索引", ""]
    lines.append("| card_id | pattern_name | phase_affinity | tags | 佐证书数 |")
    lines.append("|---|---|---|---|---|")
    for card in cards:
        novels = {s.get("novel") for s in card.get("source_scenes") or []}
        lines.append(
            f"| {card['card_id']} | {card.get('pattern_name', '')} | "
            f"{','.join(map(str, card.get('phase_affinity') or []))} | "
            f"{','.join(card.get('tags') or [])} | {len(novels)} |"
        )
    lines.append("")
    lines.append("## 场景 → 卡片（反查附录）")
    lines.append("")
    for key in sorted(backlinks):
        lines.append(f"- {key}: {', '.join(sorted(backlinks[key]))}")

    (insp_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (insp_dir / "_backlinks.json").write_text(
        json.dumps(backlinks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return backlinks


# ---------------------------------------------------------------------------
# 任务包材料装配（纯文件读取）
# ---------------------------------------------------------------------------
def _project_phase(path: Path, data: dict) -> dict:
    """按 Phase 投影当前消费者需要的结构证据，避免头部截断丢失末段字段。"""
    name = path.name
    meta = data.get("analysis_meta") or {}
    medium = meta.get("source_medium") if isinstance(meta, dict) else None
    if medium in {
        "stage_play", "screenplay", "teleplay", "radio_play",
        "musical_libretto", "opera_libretto", "traditional_opera",
    } or "dramas" in path.parts or name in {
        "phase1_world_stage.yaml", "phase2_roles.yaml",
        "phase3_dramatic_spine.yaml", "phase4_act_sequence.yaml",
        "phase5_scene_table.yaml",
    }:
        # 戏剧的幕场、上下场与声音信息共同解释机制，保留原对象及来源。
        return dict(data)
    if "phase0" in name:
        keys = ("premise", "core_value", "controlling_idea", "genre", "originality_statement")
    elif "phase1" in name:
        keys = ("setting", "world_rules", "genre_conventions", "generative_driver")
    elif "phase2" in name:
        keys = ("cast_overview", "contrast_axes", "relationships")
    elif "phase3" in name:
        keys = ("spine_mode", "spine_statement", "reader_spine", "arcs", "story_climax_design")
    elif "phase4" in name:
        keys = (
            "arc_expansions",
            "causal_chain",
            "arc_progression",
            "narrative_threads",
            "thread_intersections",
        )
    elif "phase5" in name:
        scene_keys = (
            "scene_id",
            "arc_id",
            "location",
            "time",
            "participants",
            "pov",
            "scene_tasks",
            "conflict",
            "value_start",
            "value_end",
            "handoff",
            "beat_direction",
            "source_chapter",
            "narrative_evidence",
        )

        def project_scenes(raw_scenes) -> list[dict]:
            scenes = []
            for scene in raw_scenes or []:
                if not isinstance(scene, dict):
                    continue
                projected = {key: scene[key] for key in scene_keys if key in scene}
                if projected:
                    scenes.append(projected)
            return scenes

        projected_sequences = []
        for expansion in data.get("sequence_expansions") or []:
            if not isinstance(expansion, dict):
                continue
            projected_sequences.append({
                "seq_id": expansion.get("seq_id"),
                "scenes": project_scenes(expansion.get("scenes")),
            })
        projected = {
            key: data[key] for key in ("tension_curve", "causal_chain") if key in data
        }
        if projected_sequences:
            projected["sequence_expansions"] = projected_sequences
        elif "scenes" in data:
            # 集合型存量资产把场景直接放在 Phase 5 顶层；保留原有分篇边界。
            legacy_scenes = project_scenes(data.get("scenes"))
            if legacy_scenes:
                projected["scenes"] = legacy_scenes
        return projected
    else:
        keys = tuple(data.keys())
    return {key: data[key] for key in keys if key in data}


def _read_phase_summary(work_dir: Path) -> str:
    chunks = []
    pipeline_dir = work_dir / "pipeline"
    paths = [
        *pipeline_dir.glob("phase*.yaml"),
        *pipeline_dir.glob("*/phase*.yaml"),
    ]
    for path in sorted(paths, key=lambda item: item.relative_to(pipeline_dir).as_posix()):
        label = path.relative_to(pipeline_dir).as_posix()
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError as exc:
            print(
                f"[build_inspiration_cards WARN] {path}: YAML 解析失败，使用 raw text: {exc}",
                file=sys.stderr,
            )
            chunks.append(f"## {label}\n{raw}")
            continue
        if not isinstance(data, dict):
            print(
                f"[build_inspiration_cards WARN] {path}: 顶层不是对象，使用 raw text",
                file=sys.stderr,
            )
            chunks.append(f"## {label}\n{raw}")
            continue
        projected = _project_phase(path, data)
        if not projected:
            continue
        chunks.append(
            f"## {label}\n{yaml.safe_dump(projected, allow_unicode=True, sort_keys=False)}"
        )
    return "\n\n".join(chunks) or "(none)"


def _read_scene_list(work_dir: Path) -> str:
    index_path = kb_index.index_path_of(work_dir)
    if index_path is None:
        return "(none)"
    try:
        index = kb_index.load_index(index_path)
    except (OSError, ValueError):
        return "(none)"
    rows = [
        {
            "scene_id": e.get("scene_id"),
            "description": e.get("description") or e.get("dramatic_purpose") or e.get("title"),
            "tags": e.get("tags") or e.get("few_shot_tags") or e.get("subtext"),
            "pov": e.get("pov"),
            "source_chapter": e.get("source_chapter"),
            "file": e.get("file"),
        }
        for e in index
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2)


def _read_craft_traits(work_dir: Path) -> str:
    traits = []
    notes_dir = work_dir / "craft_notes"
    structured_stems: set[str] = set()
    for sidecar in sorted(notes_dir.glob("scene_*_beats.yaml")) if notes_dir.exists() else []:
        try:
            data = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        payload = {
            "scene_id": data.get("scene_id"),
            "overall_traits": data.get("overall_traits") or [],
            "narrative_organization": data.get("narrative_organization") or {},
        }
        if work_dir.parent.name == "dramas":
            payload = data
        if payload.get("patterns") or payload.get("overall_traits") or payload.get("narrative_organization"):
            structured_stems.add(sidecar.stem)
            traits.append(
                f"### {sidecar.name}\n"
                + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
            )
    for md in sorted(notes_dir.glob("scene_*_beats.md")) if notes_dir.exists() else []:
        if md.stem in structured_stems:
            continue
        text = md.read_text(encoding="utf-8")
        marker = "## 整体手艺特征"
        if work_dir.parent.name != "dramas" and marker in text:
            text = text.split(marker, 1)[1]
        if text.strip():
            traits.append(f"### {md.name}\n{text}")
    return "\n\n".join(traits) or "(none)"


# ---------------------------------------------------------------------------
# nominate
# ---------------------------------------------------------------------------
def prepare_nominate(novel: str | None, force: bool, out_dir: str) -> int:
    nom_dir = INSPIRATION_DIR / "_nominations"
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    count = 0
    for work_dir in _work_dirs():
        if novel and novel not in work_dir.name:
            continue
        if kb_index.index_path_of(work_dir) is None:
            continue
        if (nom_dir / f"{work_dir.name}.json").exists() and not force:
            continue
        task = {
            "layer": "inspiration_nominate",
            "novel": work_dir.name,
            "instructions": NOMINATE_INSTRUCTIONS,
            "source_root": str(work_dir.resolve()),
            "analysis_files": [str(p.resolve()) for p in sorted(work_dir.glob("*.md"))
                               if p.name != "full_text.md"],
            "output_contract": {
                "说明": "把提名写为一个 JSON 文件（UTF-8），结构如下；随后用 "
                      "--stage nominate --ingest 校验写回",
                "novel": work_dir.name,
                "nominations": [{
                    **{f: ("[...]" if f in ("reuse_candidates", "tags", "evidence_scenes")
                           else "...") for f in NOMINATION_FIELDS},
                    "mechanism": "可重建的关系", "source_analyses": [{
                    "novel": work_dir.name, "creative_move": "创意及作用",
                    "narrative_reason": "有原文依据的叙事理由",
                    "transfer_conditions": "成立条件及迁移边界",
                    "source_scene_ids": ["原样 scene_id"],
                }]}],
            },
            "phases": _read_phase_summary(work_dir),
            "scenes": _read_scene_list(work_dir),
            "craft_traits": _read_craft_traits(work_dir),
        }
        out_path = out_root / f"{work_dir.name}.task.json"
        out_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"任务包: {out_path}")
        count += 1
    print(f"task_files={count}")
    return 0 if count else 2


def ingest_nominate(file: str) -> int:
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    novel = data.get("novel")
    nominations = data.get("nominations") or []
    if not novel or not nominations:
        print("[build_inspiration_cards INGEST_ERROR] 产出文件缺 novel 或 nominations", file=sys.stderr)
        return 2
    idx_map = load_idx_map()
    if novel not in idx_map:
        print(f"[build_inspiration_cards INGEST_ERROR] 未知书目: {novel}", file=sys.stderr)
        return 2
    accepted, rejected = [], 0
    for nom in nominations:
        legacy_field = "do_" + "not_copy"
        if legacy_field in nom:
            print(f"  ✗ 提名含废弃字段 {legacy_field}: {nom.get('pattern_name', '?')}",
                  file=sys.stderr)
            rejected += 1
            continue
        missing = [f for f in NOMINATION_FIELDS if not nom.get(f)]
        if missing:
            print(f"  ✗ 提名缺字段 {missing}: {nom.get('pattern_name', '?')}", file=sys.stderr)
            rejected += 1
            continue
        try:
            _validate_reuse_candidates(nom["reuse_candidates"])
        except ValueError as e:
            print(f"  ✗ {nom.get('pattern_name')}: {e}", file=sys.stderr)
            rejected += 1
            continue
        kept = []
        for ev in nom["evidence_scenes"]:
            real = normalize_scene_id(novel, ev.get("scene_id", ""), idx_map)
            if real is None:
                print(f"  ✗ {nom.get('pattern_name')}: 佐证不存在已剔除 {ev.get('scene_id')}",
                      file=sys.stderr)
                continue
            try:
                kept.append({"scene_id": real, "note": ev.get("note", ""),
                             **_source_window(ev)})
            except ValueError as e:
                print(f"  ✗ {nom.get('pattern_name')}: {e}", file=sys.stderr)
                kept = []
                break
        if not kept:
            print(f"  ✗ {nom.get('pattern_name')}: 佐证全部不存在", file=sys.stderr)
            rejected += 1
            continue
        clean = {f: nom[f] for f in NOMINATION_FIELDS}
        clean["evidence_scenes"] = kept
        try:
            clean.update(_source_analyses(nom, [{"novel": novel, **s} for s in kept]))
        except ValueError as e:
            print(f"  ✗ {nom.get('pattern_name')}: {e}", file=sys.stderr)
            rejected += 1
            continue
        if nom.get("phase_affinity"):
            try:
                clean["phase_affinity"] = _normalize_phase_affinity(nom["phase_affinity"])
            except ValueError as e:
                print(f"  ✗ {nom.get('pattern_name')}: {e}", file=sys.stderr)
                rejected += 1
                continue
        accepted.append(clean)
    if not accepted:
        print("[build_inspiration_cards INGEST_ERROR] 提名全部被拒收", file=sys.stderr)
        return 1
    nom_dir = INSPIRATION_DIR / "_nominations"
    nom_dir.mkdir(parents=True, exist_ok=True)
    out_path = nom_dir / f"{novel}.json"
    out_path.write_text(
        json.dumps({"novel": novel, "nominations": accepted}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"写入: {out_path}（接受 {len(accepted)} / 拒收 {rejected}）")
    return 0 if rejected == 0 else 1


# ---------------------------------------------------------------------------
# cluster
# ---------------------------------------------------------------------------
def prepare_cluster(out: str) -> int:
    nom_dir = INSPIRATION_DIR / "_nominations"
    nominations = []
    for path in sorted(nom_dir.glob("*.json")) if nom_dir.exists() else []:
        data = json.loads(path.read_text(encoding="utf-8"))
        novel = data.get("novel") or path.stem
        for nom in data.get("nominations", []):
            nominations.append({"novel": novel, **nom})
    if not nominations:
        print("[build_inspiration_cards NO_NOMINATIONS] 无 nominations，先跑 nominate 两段", file=sys.stderr)
        return 2
    idx_map = load_idx_map()
    task = {
        "layer": "inspiration_cluster",
        "instructions": CLUSTER_INSTRUCTIONS,
        "output_contract": {
            "说明": "把聚类结果写为一个 JSON 文件（UTF-8），结构 {\"cards\": [...]}；"
                  "随后用 --stage cluster --ingest [--replace] 校验写回",
            "cards": [{
                **{f: ("[...]" if f in ("reuse_candidates", "tags", "source_scenes") else "...")
                   for f in CARD_FIELDS},
                "mechanism": "共同关系及成立条件",
                "source_analyses": [{"novel": "原作品目录名", "creative_move": "创意及作用",
                                     "narrative_reason": "保留逐作品解释",
                                     "transfer_conditions": "保留条件差异",
                                     "source_scene_ids": ["原样 scene_id"]}],
            }],
        },
        "scene_id_inventory": {n: sorted(ids) for n, ids in sorted(idx_map.items())
                               if any(nom["novel"] == n for nom in nominations)},
        "nominations": nominations,
    }
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"任务包已写入: {out_path}（{len(nominations)} 条提名）")
    return 0


def ingest_cluster(file: str, replace: bool) -> int:
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    cards = data.get("cards") or []
    if not cards:
        print("[build_inspiration_cards INGEST_ERROR] 产出文件无 cards", file=sys.stderr)
        return 2
    idx_map = load_idx_map()
    cleaned, rejected = [], 0
    seen_ids: set[str] = set()
    for card in cards:
        try:
            clean = validate_card(card, idx_map)
        except ValueError as e:
            print(f"  ✗ {card.get('card_id', '<no-id>')}: {e}", file=sys.stderr)
            rejected += 1
            continue
        if clean["card_id"] in seen_ids:
            print(f"  ✗ card_id 重复: {clean['card_id']}", file=sys.stderr)
            rejected += 1
            continue
        seen_ids.add(clean["card_id"])
        cleaned.append(clean)
    if not cleaned:
        print("[build_inspiration_cards INGEST_ERROR] 卡片全部被拒收", file=sys.stderr)
        return 1
    if replace:
        for old in _iter_card_paths(INSPIRATION_DIR):
            old.unlink()
    for clean in cleaned:
        write_card(INSPIRATION_DIR, clean)
    rebuild_index(INSPIRATION_DIR)
    cross = sum(1 for c in cleaned if len({s['novel'] for s in c['source_scenes']}) > 1)
    print(f"cards={len(cleaned)} rejected={rejected} cross_book={cross}")
    return 0 if rejected == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 inspiration cards（prepare/ingest，零 LLM 调用）")
    parser.add_argument("--stage", choices=["nominate", "cluster", "index"], default="nominate")
    parser.add_argument("--from-nominations", action="store_true", help="等价于 --stage cluster")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true", help="装配任务包")
    mode.add_argument("--ingest", type=str, metavar="FILE", help="校验并写回产出文件")
    parser.add_argument("--novel", default=None, help="书名子串过滤（nominate --prepare）")
    parser.add_argument("--force", action="store_true", help="已有提名也重新出任务包（nominate --prepare）")
    parser.add_argument("--replace", action="store_true", help="cluster --ingest 时先清空既有卡再写入")
    parser.add_argument("--out", default=None, help="任务包输出路径（--prepare；nominate 为目录，cluster 为文件）")
    args = parser.parse_args()

    stage = "cluster" if args.from_nominations else args.stage
    if args.from_nominations and args.stage != "nominate":
        print("[build_inspiration_cards ARG_ERROR] --from-nominations 不可与显式 --stage 混用", file=sys.stderr)
        return 2

    if stage == "index":
        rebuild_index(INSPIRATION_DIR)
        print(f"rebuilt: {INSPIRATION_DIR / 'index.md'}")
        return 0
    if not args.prepare and not args.ingest:
        print("[build_inspiration_cards ARG_ERROR] nominate/cluster 需指定 --prepare 或 --ingest", file=sys.stderr)
        return 2

    if stage == "nominate":
        if args.prepare:
            return prepare_nominate(args.novel, args.force,
                                    args.out or "tmp/annotation-tasks/nominate")
        return ingest_nominate(args.ingest)
    if args.prepare:
        return prepare_cluster(args.out or "tmp/annotation-tasks/cluster.task.json")
    return ingest_cluster(args.ingest, args.replace)


if __name__ == "__main__":
    sys.exit(main())
