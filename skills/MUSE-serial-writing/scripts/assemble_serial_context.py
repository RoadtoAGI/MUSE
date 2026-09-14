#!/usr/bin/env python3
"""assemble_serial_context.py — 章级作者侧上下文装配（机械拼接，不调 LLM）

按 serial-outline workspace-schema.md 契约，从章卡 recap_inputs 出发机械拼接：
  ①全局脉络（story_bible.frozen、创作锚与 intent + 三级 digest：远卷 one_liner /
  卷首章特例注入上一卷末单元 paragraph / 本卷前单元 paragraph / 本单元前章
  recap.summary 全文）②本卷卷纲切片 ③设定集切片（worldbook 地图 + 公理册
  硬约束恒注 + 章卡声明分册全文）④来源窗口内的世界事实
  ⑤角色现状 ⑥未决线头，渲染为固定段落 Markdown，写入本章 workspace
  pipeline/serial_context.md 供编排、派生与 writer 消费。编排前选择人物与
  实体后装配；章卡变化后重跑本脚本
  （纯机械可反复重跑，重装配义务见 workspace-schema 章卡一节）。

作者侧上下文保留点名实体的事实与合时知情者，不按章主 POV 删去其他角色的材料。
人物知识由 role-view 派生器按本场故事时点与获知渠道分配；actor 不读本文件。

设定集（worldbook）：series/worldbook/index.yaml 存在才装配③段——设定集地图
（全部分册 summary_line）+ 公理册硬约束表恒注 + `recap_inputs.worldbook_sections`
声明分册全文（分册以 `## 素材库` 标题切两段：硬约束部恒保、素材库部可裁）。
目录或 index 缺失（既有工作区无分域设定集）按"本作品无分域设定集"跳过；
声明的分册未注册/文件缺失 → WARN + 跳过该项。

buffer 前章合并：`series/series_state.yaml` 的 `buffer.drafted_unpublished`
列表内、且位于本章 `prev_chapter` 链上游（回溯不限单元/不限卷）的章，其
`recap.yaml.deltas` 尚未入三台账转正——本脚本额外合并这些候选 delta 到对应
段落（fact_deltas → 段③、character_deltas → 段④、thread_events → 段⑤），
并标注"buffer 候选"来源章号，避免 writer 基于台账过期状态续写。buffer 章的
`recap.yaml` 若缺失（该章可能刚被重写作废）只 WARN，不阻断装配。

用法：
    python3 assemble_serial_context.py --work-dir <works/<slug>/ 工作区根> \
        --chapter C0005 [--budget-chars 12000] [--max-facts-per-entity 12]

预算裁剪（保序阶梯，逐级降档直到入预算）：
  1. 段①远卷 digest 明细（从最早一条起丢弃）
  2. 段①本卷前单元 digest 明细（同上）
  3. 段③声明分册的素材库部（按声明序逐册置省略注；硬约束部恒保）
  4. 段④每实体事实条数上限降档（默认 12 → 8 → 5 → 3；kind 优先级
     状态类>规则类>其他，同级 established_at 近者优先——保序裁剪）
本单元前章 recap 全文、段②卷纲切片、角色现状与未决线头永不裁剪。全部阶梯
用尽仍超预算则原样输出并在 stderr 提示。每实体条数上限在不超预算时也生效
（默认 12，防单实体长程累积撑爆注入面），被裁条目渲染省略注指回台账。

失败语义：
    0 — 完成
    1 — 数据错：既有 YAML 解析失败
    2 — 阻断：--work-dir 不存在 / --chapter 格式非法 / 卷纲反查不到该
        chapter_id、或对应 chapters/V0N/C####/chapter_card.yaml 不存在

本脚本不调 LLM（纯机械字段提取 + 拼接 + 预算裁剪）。
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import yaml

from character_context import (
    CharacterContextError, character_names, normalize_character_facts,
    resolve_character, scoped_persona,
)
from consumer_contract import load_chapter_anchors, validate_milestones, validate_tentpoles
from ledger_tools import active_facts

CHAPTER_RE = re.compile(r"^C\d{4}$")
VOL_NUM_RE = re.compile(r"^V(\d+)$")
# milestone.at：C#### 或 C####S##，章号取捕获组 1（与 snapshot_character 同口径）
CHAPTER_PART_RE = re.compile(r"^(C\d{4})(S\d{2})?$")

EMPTY_NOTE = "（该级摘要尚未生成）"
CUT_NOTE = "（因预算裁剪省略，完整内容见 series/digests/）"

HEADER = ("# 连载上下文（机器装配）\n\n"
          "本文件供编排、人物派生和 writer 使用。卷向与本章目标属于设计；"
          "事实、人物与前章材料属于带来源的连续性资料，均不等于所有人物已知。"
          "actor 只读取自己的 role_view；场景倒叙时由派生器再按故事时点筛选。")

# worldbook 分册两段式切分标题：之前为硬约束部（恒保），之后为素材库部（可裁）
WB_SOFT_HEAD = "## 素材库"

# facts 保序裁剪的 kind 优先级：状态类 > 规则类 > 其他（V1 架构 §6.2 保序承诺）
_KIND_STATE = {"state", "ability", "relation", "secret"}
_KIND_RULE = {"rule"}


def _kind_priority(kind: str | None) -> int:
    if kind in _KIND_STATE:
        return 0
    if kind in _KIND_RULE:
        return 1
    return 2


def source_position(ref, sequence: dict[str, int]) -> int | None:
    """A chapter anchor locates source order, not fictional chronology."""
    match = CHAPTER_PART_RE.fullmatch(str(ref or ""))
    return sequence.get(match.group(1)) if match else None


class BlockingError(Exception):
    """阻断性前置条件不满足：--work-dir/--chapter 非法，或章卡资源不存在。"""


class DataError(Exception):
    """既有 YAML 内容解析失败。"""


_WARNED: set[str] = set()


def warn_once(msg: str) -> None:
    """预算裁剪阶梯会多次重渲染同一段——同文案 WARN 只打一次。"""
    if msg in _WARNED:
        return
    _WARNED.add(msg)
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# 通用 IO
# ---------------------------------------------------------------------------


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def load_yaml_or_none(path: Path) -> dict | None:
    """文件不存在 → None（调用方按空结构解释）；存在但解析失败 → 抛 DataError。"""
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


def render_generic_fields(data: dict) -> str:
    """快照文件 schema 未在 workspace-schema.md 定义字段表（自由结构），
    通用渲染其顶层字段，不假设具体键名。"""
    lines: list[str] = []
    for k, v in data.items():
        if k == "schema_version":
            continue
        if isinstance(v, (dict, list)):
            dumped = yaml.safe_dump(v, allow_unicode=True, sort_keys=False).strip()
            lines.append(f"- **{k}**:")
            for sub in dumped.splitlines():
                lines.append(f"  {sub}")
        else:
            lines.append(f"- **{k}**: {v}")
    return "\n".join(lines) if lines else "（快照文件为空）"


# ---------------------------------------------------------------------------
# 卷纲反查：chapter_id → 所属卷 / unit / 卷纲条目位置
# ---------------------------------------------------------------------------


def load_all_volumes(work_dir: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """扫描 series/volumes/*.yaml，建 chapter_id → {volume_id, unit, position,
    chapters_list} 反查表 + volume_id → 卷纲整体数据表。"""
    volumes_dir = work_dir / "series" / "volumes"
    chapter_index: dict[str, dict] = {}
    volumes_data: dict[str, dict] = {}
    if not volumes_dir.is_dir():
        return chapter_index, volumes_data

    for vol_path in sorted(volumes_dir.glob("V*.yaml")):
        data = load_yaml_or_none(vol_path) or {}
        vol_id = data.get("volume_id") or vol_path.stem
        volumes_data[vol_id] = data
        chapters = data.get("chapters") or []
        for idx, entry in enumerate(chapters):
            if not isinstance(entry, dict):
                continue
            cid = entry.get("chapter_id")
            if not cid:
                continue
            chapter_index[cid] = {
                "volume_id": vol_id,
                "unit": entry.get("unit"),
                "entry": entry,
                "position": idx,
                "chapters_list": chapters,
            }
    return chapter_index, volumes_data


def _vol_num(vol_id: str) -> int | None:
    m = VOL_NUM_RE.match(vol_id)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 段①：全局脉络 —— frozen 全量 + 三级 digest
# ---------------------------------------------------------------------------


def collect_far_volume_digests(work_dir: Path, volumes_data: dict, current_vol_id: str) -> list[tuple[str, str]]:
    """远卷 one_liner：只取严格早于当前卷、且 digest 文件已产出的卷（未收束的
    卷天然无 digest 文件，无需额外过滤）。"""
    current_num = _vol_num(current_vol_id)
    ordered_ids = sorted(
        (v for v in volumes_data if v != current_vol_id),
        key=lambda v: (_vol_num(v) is None, _vol_num(v) or 0),
    )
    items: list[tuple[str, str]] = []
    digests_dir = work_dir / "series" / "digests"
    for vol_id in ordered_ids:
        num = _vol_num(vol_id)
        if current_num is not None and num is not None and num >= current_num:
            continue
        digest = load_yaml_or_none(digests_dir / f"{vol_id}.yaml")
        if digest and digest.get("one_liner"):
            items.append((vol_id, digest["one_liner"]))
    return items


def collect_prior_unit_digests(
    work_dir: Path, current_vol_id: str, current_vol_data: dict, current_unit: str | None
) -> list[tuple[str, str]]:
    """本卷前单元 paragraph：单元顺序取自卷纲 chapters[] 列表的首次出现序
    （append-only 追加协议下天然是时间序），不对 unit 命名做数字假设。"""
    chapters = current_vol_data.get("chapters") or []
    units_in_order: list[str] = []
    for entry in chapters:
        if not isinstance(entry, dict):
            continue
        u = entry.get("unit")
        if u and u not in units_in_order:
            units_in_order.append(u)

    if current_unit not in units_in_order:
        return []
    prior_units = units_in_order[: units_in_order.index(current_unit)]

    items: list[tuple[str, str]] = []
    digests_dir = work_dir / "series" / "digests"
    for unit_id in prior_units:
        digest = load_yaml_or_none(digests_dir / f"{current_vol_id}-{unit_id}.yaml")
        if digest and digest.get("paragraph"):
            items.append((unit_id, digest["paragraph"]))
    return items


def collect_prev_chain_recaps(
    work_dir: Path,
    chapter_index: dict,
    current_unit: str | None,
    current_vol_id: str,
    prev_chapter: str | None,
) -> list[tuple[str, str | None]]:
    """沿 prev_chapter 链回溯，只收本卷本单元内前章的 recap.summary 全文；
    一旦链条跨入更早的 unit 或更早的卷（或找不到反查记录）即停止——更早内容
    已由远卷/前单元 digest 覆盖。止步判据用 (volume_id, unit) 联合键：unit
    编号卷内局部，跨卷同名不串，仅比对 unit 字符串会在跨卷同名单元时误连。"""
    collected: list[tuple[str, str | None]] = []
    cursor = prev_chapter
    while cursor:
        info = chapter_index.get(cursor)
        if (
            info is None
            or info.get("unit") != current_unit
            or info.get("volume_id") != current_vol_id
        ):
            break
        vol_id = info["volume_id"]
        chapter_dir = work_dir / "chapters" / vol_id / cursor
        recap = load_yaml_or_none(chapter_dir / "recap.yaml")
        summary = recap.get("summary") if recap else None
        imported_chapter = not chapter_dir.exists()
        if imported_chapter and info.get("entry", {}).get("status") == "published":
            logline = info["entry"].get("logline")
            summary = f"（接管卷纲摘要）{logline}" if logline else None
        collected.append((cursor, summary))

        card = load_yaml_or_none(chapter_dir / "chapter_card.yaml")
        if card:
            cursor = card.get("prev_chapter")
        elif imported_chapter and info["position"] > 0:
            cursor = info["chapters_list"][info["position"] - 1].get("chapter_id")
        else:
            cursor = None

    collected.reverse()  # 时序：最早在前，最贴近当前章在后
    return collected


# ---------------------------------------------------------------------------
# buffer 前章合并：series_state.buffer.drafted_unpublished 中位于 prev 链
# 上游（不限单元/不限卷）的章，其 recap.yaml.deltas 尚未入台账转正
# ---------------------------------------------------------------------------


def collect_buffer_ancestor_deltas(
    work_dir: Path, chapter_index: dict, prev_chapter: str | None, buffer_ids: set[str]
) -> list[tuple[str, dict]]:
    """沿 prev_chapter 链回溯（不限单元、不限卷——buffer 是已定稿未发布的
    连续中段，其 delta 尚未入台账，必须无条件合并，否则 writer 基于过期
    台账续写），收集其中属于 buffer_ids 的章的 recap.yaml deltas。

    recap.yaml 缺失（该 buffer 章可能刚被重写作废）只 WARN，不阻断——台账
    从未写入该章内容，作废不破坏 append-only 语义。"""
    collected: list[tuple[str, dict]] = []
    if not buffer_ids:
        return collected

    cursor = prev_chapter
    seen: set[str] = set()
    remaining = set(buffer_ids)
    while cursor and cursor not in seen and remaining:
        seen.add(cursor)
        info = chapter_index.get(cursor)
        if info is None:
            break
        vol_id = info["volume_id"]
        chapter_dir = work_dir / "chapters" / vol_id / cursor

        if cursor in remaining:
            remaining.discard(cursor)
            recap_path = chapter_dir / "recap.yaml"
            recap = load_yaml_or_none(recap_path)
            if recap is None:
                print(
                    f"[assemble_serial_context WARN] buffer 章 {cursor} 的 "
                    f"recap.yaml 不存在（{recap_path}），跳过其 delta 合并"
                    "（该章可能刚被重写作废）",
                    file=sys.stderr,
                )
            else:
                collected.append((cursor, recap.get("deltas") or {}))

        card = load_yaml_or_none(chapter_dir / "chapter_card.yaml")
        cursor = card.get("prev_chapter") if card else None

    collected.reverse()  # 时序：最早在前，最贴近当前章在后
    return collected


def load_context_clock(work_dir: Path, chapter_index: dict, current_chapter_id: str | None) -> tuple[dict[str, int], int]:
    """Use the same source cutoff for persona, facts and thread consumers."""
    manifest = load_yaml_or_none(work_dir / "published" / "manifest.yaml") or {}
    sequence: dict[str, int] = {}
    for entry in manifest.get("entries") or []:
        if not isinstance(entry, dict):
            raise DataError("manifest entries 条目必须为映射")
        cid, seq = entry.get("chapter_id"), entry.get("published_seq")
        if not cid or type(seq) is not int or seq < 1 or cid in sequence or seq in sequence.values():
            raise DataError("manifest 章 ID 或 published_seq 缺失、非法或重复")
        sequence[cid] = seq
    if not current_chapter_id:
        return sequence, max(sequence.values(), default=0)
    if current_chapter_id in sequence:
        return sequence, sequence[current_chapter_id] - 1
    cursor, seen = current_chapter_id, set()
    while cursor:
        if cursor in sequence:
            return sequence, sequence[cursor]
        if cursor in seen:
            raise DataError("章 prev 链成环，无法确定上下文来源窗口")
        seen.add(cursor)
        info = chapter_index.get(cursor) or {}
        card = load_yaml_or_none(work_dir / "chapters" / str(info.get("volume_id", "")) / cursor / "chapter_card.yaml")
        if card:
            cursor = card.get("prev_chapter")
        elif info.get("position", 0) > 0:
            cursor = info["chapters_list"][info["position"] - 1].get("chapter_id")
        else:
            cursor = None
    return sequence, 0


def facts_in_source_window(facts: list[dict], sequence: dict[str, int], cutoff: int, *, historical: bool = False) -> list[dict]:
    """Keep source-backed facts and knowledge receipts without changing ledgers."""
    result = []
    for fact in facts:
        if not isinstance(fact, dict):
            raise DataError("facts 条目必须为映射")
        position = source_position(fact.get("established_at"), sequence)
        if position is None:
            warn_once(f"事实 {fact.get('fact_id', '')}: established_at 无法定位，未注入")
            continue
        if position > cutoff:
            continue
        if historical and fact.get("origin") == "errata":
            warn_once("历史来源窗口不反投最新 errata；需要该事实时回读对应原文")
            continue
        if fact.get("status") == "retracted":
            continue
        row = dict(fact)
        if fact.get("kind") == "secret":
            known = []
            for entry in fact.get("known_by") or []:
                if not isinstance(entry, dict):
                    raise DataError("known_by 条目必须为映射")
                learned = source_position(entry.get("learned_at"), sequence)
                if learned is None:
                    warn_once(f"事实 {fact.get('fact_id', '')}: 知情者 {entry.get('char_id', '')} 缺少可定位 learned_at，未作为已知注入")
                elif learned <= cutoff:
                    known.append(dict(entry))
            row["known_by"] = known
        result.append(row)
    return result


def render_fact_line(f: dict, suffix: str = "") -> str:
    limitation = f.get("limitation")
    extra = ""
    if f.get("kind") == "secret":
        known = [f"{k.get('char_id')}@{k.get('learned_at')}" for k in f.get("known_by") or []]
        extra = "；已登记知情者: " + (", ".join(known) if known else "无可用获知证据")
    if f.get("kind") in ("ability", "rule") and limitation:
        extra = f"；limitation: {limitation}"
    if f.get("note"):
        extra += f"；备注: {f['note']}"
    return (
        f"- {f.get('entity')} · {f.get('attribute')}: {f.get('value')}"
        f"（kind: {f.get('kind')}, established_at: {f.get('established_at')}{extra}）{suffix}"
    )


def collect_prev_volume_last_unit_digest(
    work_dir: Path, volumes_data: dict, current_vol_id: str
) -> tuple[str, str] | None:
    """卷首章特例（跨卷承接信息需求最高、分辨率落差最陡）：取上一卷卷纲
    chapters[] 末项所在单元的 digest paragraph，作为远卷 one_liner 与本卷
    空前史之间的中距离缓冲。上一卷不存在 / 无章 / digest 未产出 → None。"""
    current_num = _vol_num(current_vol_id)
    if current_num is None:
        return None
    best_num, best_id = None, None
    for vol_id in volumes_data:
        num = _vol_num(vol_id)
        if num is None or num >= current_num:
            continue
        if best_num is None or num > best_num:
            best_num, best_id = num, vol_id
    if best_id is None:
        return None
    prev_chapters = volumes_data[best_id].get("chapters") or []
    last_unit = None
    for entry in reversed(prev_chapters):
        if isinstance(entry, dict) and entry.get("unit"):
            last_unit = entry["unit"]
            break
    if not last_unit:
        return None
    digest = load_yaml_or_none(work_dir / "series" / "digests" / f"{best_id}-{last_unit}.yaml")
    if digest and digest.get("paragraph"):
        return (f"{best_id}-{last_unit}", digest["paragraph"])
    return None


def render_section1(
    frozen: dict,
    far_items: list[tuple[str, str]],
    far_originally_empty: bool,
    unit_items: list[tuple[str, str]],
    unit_originally_empty: bool,
    recap_items: list[tuple[str, str | None]],
    is_opening: bool,
    prev_vol_unit_item: tuple[str, str] | None = None,
    intent: dict | None = None,
) -> str:
    lines = ["## 全局脉络", "", "### 总纲（frozen）"]
    lines.append(f"- 前提：{frozen.get('premise', '')}")
    lines.append(f"- 主角欲望系统：{frozen.get('protagonist_want_need', '')}")
    lines.append(f"- 世界天花板：{frozen.get('world_ceiling', '')}")
    power = frozen.get("power_system_pyramid")
    lines.append(f"- 力量体系：{power if power else '本作品无独立力量体系分级'}")
    lines.append(f"- 主线方向：{frozen.get('spine_direction', '')}")

    creative_anchors = frozen.get("creative_anchors") or {}
    if creative_anchors:
        anchor_lines = []
        for key, label in (
            ("title", "作品名"), ("core_value", "核心价值与关注"),
            ("primary_drive", "叙事驱动"), ("controlling_idea", "表达方向"),
            ("unique_angle", "独创角度"), ("style_directives", "作品风格"),
        ):
            value = creative_anchors.get(key)
            if value is not None and value != "" and value != []:
                values = value if isinstance(value, list) else [value]
                anchor_lines.extend(f"- {label}：{item}" for item in values)
        if anchor_lines:
            lines.extend(["", "### 已确认的创作锚（作者侧）", *anchor_lines])

    intent = intent or {}
    if intent.get("current_thrust"):
        lines.extend(["", "### 当前已确认方向（作者侧计划）",
                      str(intent["current_thrust"])])
    if intent.get("open_questions"):
        lines.extend(["", "### 未决问题（保留未定，依赖该选择的设计待裁决）"])
        lines.extend(f"- {question}" for question in intent["open_questions"])

    if is_opening:
        # 首章没有前史摘要；作者方向与未决问题仍须进入首稿上下文。
        return "\n".join(lines)

    lines.append("")
    lines.append("### 远卷摘要")
    if far_items:
        for vol_id, one_liner in far_items:
            lines.append(f"- {vol_id}：{one_liner}")
    else:
        lines.append(EMPTY_NOTE if far_originally_empty else CUT_NOTE)

    if prev_vol_unit_item:
        unit_key, paragraph = prev_vol_unit_item
        lines.append("")
        lines.append("### 上一卷末单元摘要（卷首承接）")
        lines.append(f"- {unit_key}：{paragraph}")

    lines.append("")
    lines.append("### 本卷前单元摘要")
    if unit_items:
        for unit_id, paragraph in unit_items:
            lines.append(f"- {unit_id}：{paragraph}")
    else:
        lines.append(EMPTY_NOTE if unit_originally_empty else CUT_NOTE)

    lines.append("")
    lines.append("### 本单元前章 recap")
    if recap_items:
        for cid, summary in recap_items:
            lines.append(f"- {cid}：{summary if summary is not None else '（该章 recap 尚未生成）'}")
    else:
        lines.append(EMPTY_NOTE)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 段②：本卷 —— protagonist_delta + tentpoles + world_reveal_plan + 前后卷纲条目
# ---------------------------------------------------------------------------


def render_section2(
    volume_data: dict, chapter_info: dict, chapter_id: str, current_unit: str | None
) -> str:
    lines = ["## 本卷", ""]
    pd = volume_data.get("protagonist_delta") or {}
    lines.append("### 主角本卷变化（protagonist_delta）")
    lines.append(f"- 起点：{pd.get('from', '')}")
    lines.append(f"- 终点：{pd.get('to', '')}")

    lines.append("")
    lines.append("### 本卷 dramatic question（volume_question）")
    lines.append(volume_data.get("volume_question") or "（本卷未填 volume_question）")

    lines.append("")
    lines.append("### Tentpoles")
    tentpoles = volume_data.get("tentpoles") or []
    if tentpoles:
        for t in tentpoles:
            lines.append(
                f"- {t.get('beat', '')}（value_shift: {t.get('value_shift', '')}；"
                f"anchor: {t.get('anchor', '')}）"
            )
    else:
        lines.append("（本卷暂无 tentpoles）")

    lines.append("")
    lines.append("### 本章活跃叙事线")
    active_lines = []
    for line in volume_data.get("narrative_lines") or []:
        active_at = {str(anchor) for anchor in (line.get("active_at") or [])}
        if chapter_id in active_at or (current_unit and current_unit in active_at):
            active_lines.append(line)
    if active_lines:
        for line in active_lines:
            lines.append(f"- {line.get('line_id', '')}：{line.get('description', '')}")
    else:
        lines.append("（本章无单独声明的活跃叙事线）")

    lines.append("")
    lines.append("### 世界揭示计划（world_reveal_plan）")
    reveals = volume_data.get("world_reveal_plan") or []
    if reveals:
        for r in reveals:
            line = (
                f"- [{r.get('status', '')}] {r.get('reveal', '')}"
                f"（from_ceiling: {r.get('from_ceiling', '')}"
            )
            # 揭示位置按卷纲实际列表比较；缺锚不是普遍禁令。
            if r.get("status") == "planned":
                planned_at = r.get("planned_at")
                entries = volume_data.get("chapters") or []
                current_pos = next((i for i, e in enumerate(entries)
                                    if e.get("chapter_id") == chapter_id), None)
                target_positions = [i for i, e in enumerate(entries)
                                    if planned_at and planned_at in (e.get("chapter_id"), e.get("unit"))]
                if planned_at and str(planned_at) in (chapter_id, current_unit or ""):
                    line += f"；预定揭示锚: {planned_at}——本章处于预定揭示范围，可兑现"
                elif target_positions and current_pos is not None:
                    if current_pos < min(target_positions):
                        line += f"；预定揭示锚: {planned_at}——保留到该位置，当前可铺垫"
                    else:
                        line += f"；预定揭示锚: {planned_at}——锚点已过但仍标 planned，核对实际正文与当前设计"
                else:
                    line += f"；揭示位置未能定位（{planned_at or '未指定'}）——按已确认意图核对本章是否承担正式揭示"
            line += "）"
            lines.append(line)
    else:
        lines.append("（本卷无新增世界揭示）")

    lines.append("")
    entry = chapter_info["entry"]
    lines.append("### 本章意图（设计）")
    lines.append(f"- {chapter_id}：{entry.get('logline', '')}")
    lines.append(f"- 钩子方向：{entry.get('hook_type', '')}")
    lines.append(f"- 需开启：{', '.join(entry.get('opened') or []) or '（无）'}；需回收：{', '.join(entry.get('closed') or []) or '（无）'}")
    lines.append("")
    lines.append("### 本章前后卷纲条目")
    chapters_list = chapter_info["chapters_list"]
    pos = chapter_info["position"]
    neighbor_lines: list[str] = []
    if pos - 1 >= 0:
        e = chapters_list[pos - 1]
        neighbor_lines.append(
            f"- 前章（{e.get('chapter_id')}）：{e.get('logline', '')}"
            f"（hook_type: {e.get('hook_type', '')}, status: {e.get('status', '')}）"
        )
    if pos + 1 < len(chapters_list):
        e = chapters_list[pos + 1]
        neighbor_lines.append(
            f"- 后章（{e.get('chapter_id')}）：{e.get('logline', '')}"
            f"（hook_type: {e.get('hook_type', '')}, status: {e.get('status', '')}）"
        )
    lines.extend(neighbor_lines if neighbor_lines else ["（本章无前后卷纲条目）"])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 段③：设定集切片（worldbook） —— 地图恒注 + 公理册硬约束恒注 + 声明分册全文
# ---------------------------------------------------------------------------


def load_worldbook_sections(work_dir: Path) -> list[dict] | None:
    """读 series/worldbook/index.yaml 注册表。目录或 index 缺失（既有工作区
    无分域设定集）→ None，装配跳过设定集段。"""
    index = load_yaml_or_none(work_dir / "series" / "worldbook" / "index.yaml")
    if index is None:
        return None
    return [s for s in (index.get("sections") or []) if isinstance(s, dict)]


def split_worldbook_text(text: str) -> tuple[str, str | None]:
    """分册两段式切分：`## 素材库` 标题之前为硬约束部（恒保），之后为素材库部
    （预算裁剪候选）。无该标题的分册整册视为硬约束部。"""
    idx = text.find(WB_SOFT_HEAD)
    if idx == -1:
        return text.strip(), None
    return text[:idx].strip(), text[idx:].strip()


def render_worldbook_section(
    work_dir: Path,
    sections: list[dict],
    declared: list[str],
    soft_cut: set[str],
) -> str:
    """③段渲染。恒注面 = 设定集地图（全分册 summary_line）+ 公理册硬约束表；
    按需面 = 章卡声明分册全文（soft_cut 内的分册素材库部以省略注替代）。
    声明分册未注册 / 分册文件缺失 → stderr WARN + 行内注记，不阻断。"""
    wb_dir = work_dir / "series" / "worldbook"
    by_id = {s.get("section_id"): s for s in sections if s.get("section_id")}

    lines = ["## 设定集切片", "", "### 设定集地图"]
    if sections:
        for s in sections:
            lines.append(
                f"- {s.get('section_id')}｜{s.get('title', '')}"
                f"（{s.get('mutability', '')}）：{s.get('summary_line', '')}"
            )
    else:
        lines.append("（设定集注册表为空）")

    def _read_section_text(s: dict) -> str | None:
        fname = s.get("file") or f"{s.get('section_id')}.md"
        path = wb_dir / fname
        if not path.is_file():
            warn_once(
                f"[assemble_serial_context WARN] worldbook 分册文件缺失："
                f"{path}（index 已注册 {s.get('section_id')}），跳过注入"
            )
            return None
        return path.read_text(encoding="utf-8")

    declared_set = set(declared)
    for s in sections:
        sid = s.get("section_id")
        if s.get("mutability") != "axiom" or sid in declared_set:
            continue
        text = _read_section_text(s)
        if text is None:
            continue
        hard, _soft = split_worldbook_text(text)
        lines.append("")
        lines.append(f"### 公理册硬约束：{s.get('title', '')}（{sid}）")
        lines.append(hard)

    for sid in declared:
        s = by_id.get(sid)
        if s is None:
            warn_once(
                f"[assemble_serial_context WARN] 章卡声明的设定集分册 {sid!r} "
                "未在 series/worldbook/index.yaml 注册，跳过"
            )
            lines.append("")
            lines.append(f"###（声明分册 {sid} 未注册，已跳过）")
            continue
        text = _read_section_text(s)
        if text is None:
            continue
        hard, soft = split_worldbook_text(text)
        lines.append("")
        lines.append(
            f"### 本章声明分册：{s.get('title', '')}（{sid}｜{s.get('mutability', '')}）"
        )
        lines.append(hard)
        if soft:
            if sid in soft_cut:
                fname = s.get("file") or f"{sid}.md"
                lines.append("")
                lines.append(f"（素材库部因预算省略，完整内容见 series/worldbook/{fname}）")
            else:
                lines.append("")
                lines.append(soft)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 段④：作者侧世界事实 —— 选中实体的来源窗口 + 秘密获知依据
# ---------------------------------------------------------------------------


def cap_facts_per_entity(
    visible: list[dict], cap: int, sequence: dict[str, int] | None = None
) -> tuple[list[dict], dict[str, int]]:
    """每实体保序裁剪：kind 优先级（状态类>规则类>其他）+ established_at 近者
    优先，超出 cap 的条目丢弃并按实体计数返回（供渲染省略注指回台账）。保留
    条目维持台账原相对顺序。cap<=0 视为不设上限。"""
    if cap <= 0:
        return visible, {}
    by_entity: dict[str, list[dict]] = {}
    for f in visible:
        by_entity.setdefault(f.get("entity"), []).append(f)
    dropped: dict[str, int] = {}
    keep_ids: set[int] = set()
    for entity, rows in by_entity.items():
        if len(rows) <= cap:
            keep_ids.update(map(id, rows))
            continue
        ranked = sorted(
            rows,
            key=lambda f: (_kind_priority(f.get("kind")), -(source_position(f.get("established_at"), sequence or {}) or 0)),
        )
        keep_ids.update(map(id, ranked[:cap]))
        dropped[entity] = len(rows) - cap
    return [f for f in visible if id(f) in keep_ids], dropped


def render_section3(
    facts: list[dict],
    characters: list[str],
    locations: list[str],
    items: list[str],
    buffer_fact_deltas: list[tuple[str, list[dict]]],
    facts_cap: int,
    sequence: dict[str, int] | None = None,
    history_gaps: set[tuple[str, str]] | None = None,
) -> str:
    entity_filter = set(characters) | set(locations) | set(items)
    visible = [f for f in facts if f.get("entity") in entity_filter]
    visible, dropped = cap_facts_per_entity(visible, facts_cap, sequence)

    # buffer 候选不裁：最新未转正进展是 writer 续写的必需增量，条数天然有界
    buffer_visible: list[tuple[str, dict]] = []
    for chap_id, fdeltas in buffer_fact_deltas:
        buffer_visible.extend((chap_id, f) for f in fdeltas if f.get("entity") in entity_filter)

    lines = ["## 世界事实（作者侧来源窗口）", "",
             "以下事实供规划和写作使用；人物是否知情由其经历、观察或获知锚决定。秘密附已登记的知情者。"]
    if visible or buffer_visible:
        for f in visible:
            lines.append(render_fact_line(f))
        for chap_id, f in buffer_visible:
            lines.append(render_fact_line(f, suffix=f"（buffer 候选，来自 {chap_id}）"))
        for entity, n in dropped.items():
            lines.append(
                f"- （{entity} 另有 {n} 条较早/低优先级事实因预算省略，"
                "按本章来源窗口回读 series/ledgers/world_facts.yaml）"
            )
    else:
        lines.append("（recap_inputs 点名实体在本章来源窗口内暂无记录）")

    for entity, attribute in sorted(history_gaps or set()):
        if entity in entity_filter:
            lines.append(f"- {entity} · {attribute}：原台账有缺少变更时间的作废/勘误，本窗口未推定其历史值；涉及该事实时回读对应发布原文。")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 段⑤：角色现状 —— 最新卷快照 + 本卷累计 milestones
# ---------------------------------------------------------------------------


def render_section4(
    work_dir: Path,
    characters: list[str],
    chapter_index: dict,
    current_vol_id: str,
    buffer_character_deltas: dict[str, list[tuple[str, dict]]],
    current_chapter_id: str | None = None,
    anchors: dict | None = None,
) -> str:
    lines = ["## 角色现状", ""]
    if not characters:
        lines.append("（recap_inputs.characters 为空）")
        return "\n".join(lines)

    current_num = _vol_num(current_vol_id)
    published_seq, cutoff = load_context_clock(work_dir, chapter_index, current_chapter_id)

    def snapshot_sequence(data: dict, vid: str) -> int | None:
        if _vol_num(vid) == 0:
            return 0
        through = data.get("through_chapter")
        if through is not None:
            return published_seq.get(through)
        candidates = [published_seq[cid] for cid, info in chapter_index.items()
                      if info.get("volume_id") == vid and cid in published_seq]
        return max(candidates) if candidates else None

    for char_id in characters:
        lines.append(f"### {char_id}")

        snap_dir = work_dir / "series" / "ledgers" / "characters" / char_id / "snapshots"
        chosen_vol = None
        snapshot_text = None
        if snap_dir.is_dir():
            candidates: list[tuple[int, Path]] = []
            for p in snap_dir.glob("V*.yaml"):
                num = _vol_num(p.stem)
                if num is None:
                    continue
                if current_num is not None and num > current_num:
                    continue
                data = load_yaml_or_none(p) or {}
                seq = snapshot_sequence(data, p.stem)
                if seq is None:
                    warn_once(f"{p}: 无法从发布册确定快照覆盖章，略过")
                    continue
                if seq > cutoff:
                    continue
                candidates.append((num, p))
            if candidates:
                candidates.sort()
                _, chosen_path = candidates[-1]
                chosen_vol = chosen_path.stem
                chain = []
                seen = set()
                path = chosen_path
                while True:
                    if path.stem in seen:
                        raise DataError(f"{path}: 快照 extends 成环")
                    seen.add(path.stem)
                    data = load_yaml_or_none(path)
                    if not data:
                        raise DataError(f"{path}: 快照继承来源缺失")
                    seq = snapshot_sequence(data, path.stem)
                    if seq is None or seq > cutoff:
                        raise DataError(f"{path}: 继承快照的覆盖章未知或晚于可见截止点")
                    if chain and seq > snapshot_sequence(chain[-1][1], chain[-1][0]):
                        raise DataError(f"{path}: 继承链覆盖时间逆行")
                    chain.append((path.stem, data))
                    parent = data.get("extends")
                    if parent is None:
                        break
                    parent_num = _vol_num(str(parent))
                    if parent_num is None or parent_num >= _vol_num(path.stem):
                        raise DataError(f"{path}: extends 必须指向更早卷")
                    path = snap_dir / f"{parent}.yaml"
                chunks = ["以下按时间继承；后项只改变所述状态，未改变的信息继续有效。"]
                for vid, data in reversed(chain):
                    fields = {k: v for k, v in data.items()
                              if k not in {"schema_version", "char_id", "volume_id", "extends", "milestones_in_volume"}}
                    chunks.append(f"**{vid}**：\n{render_generic_fields(fields)}")
                snapshot_text = "\n\n".join(chunks)

        persona = work_dir / "series" / "ledgers" / "characters" / char_id / "persona.md"
        if persona.is_file():
            try:
                body, omitted = scoped_persona(
                    persona, published_seq, cutoff,
                    initial_design=(snap_dir / "V00.yaml").is_file(),
                )
            except CharacterContextError as exc:
                raise DataError(str(exc)) from exc
            if body:
                lines.extend(["**人物基线**：", body, ""])
            elif omitted:
                lines.extend([f"（人物基线未注入：{omitted}）", ""])

        lines.append(f"**最新卷快照**{f'（{chosen_vol}）' if chosen_vol else ''}：")
        lines.append(snapshot_text if snapshot_text else "（该角色尚无快照）")
        lines.append("")

        bio_path = work_dir / "series" / "ledgers" / "characters" / char_id / "biography.yaml"
        bio = load_yaml_or_none(bio_path)
        milestones_in_volume = []
        if bio:
            milestones = bio.get("milestones") or []
            if not isinstance(milestones, list):
                raise DataError(f"{bio_path}: milestones 必须为列表")
            for m in milestones:
                if not isinstance(m, dict):
                    raise DataError(f"{bio_path}: milestone 必须为映射")
                match = CHAPTER_PART_RE.match(str(m.get("at", "")))
                if not match:
                    raise DataError(f"{bio_path}: milestone.at 必须为 C#### 或 C####S##")
                chap_id = match.group(1) if match else None
                if (chap_id and chapter_index.get(chap_id, {}).get("volume_id") == current_vol_id
                        and chap_id in published_seq and published_seq[chap_id] <= cutoff):
                    milestones_in_volume.append(m)

        if milestones_in_volume:
            try:
                if anchors is None:
                    anchors = load_chapter_anchors(work_dir)
                errors = validate_milestones(milestones_in_volume, anchors)
            except ValueError as exc:
                raise DataError(str(exc)) from exc
            if errors:
                raise DataError(f"{bio_path}: {'; '.join(errors)}")

        lines.append("**本卷累计 milestones**：")
        if milestones_in_volume:
            for m in milestones_in_volume:
                lines.append(
                    f"- [{m.get('kind')}] {m.get('before')} → {m.get('after')}"
                    f"（evidence: “{m.get('evidence')}”，at: {m.get('at')}）"
                )
        else:
            lines.append("（本卷暂无该角色 milestone 记录）")
        lines.append("")

        buffer_changes = buffer_character_deltas.get(char_id) or []
        if buffer_changes:
            try:
                if anchors is None:
                    anchors = load_chapter_anchors(work_dir)
                errors = validate_milestones([delta for _, delta in buffer_changes], anchors)
            except ValueError as exc:
                raise DataError(str(exc)) from exc
            if errors:
                raise DataError(f"{char_id} buffer character_deltas: {'; '.join(errors)}")
            lines.append("**本卷新近变化（buffer 候选）**：")
            for chap_id, d in buffer_changes:
                lines.append(
                    f"- [{d.get('kind')}] {d.get('before')} → {d.get('after')}"
                    f"（evidence: “{d.get('evidence')}”，at: {d.get('at')}，来自 {chap_id}）"
                )
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 段⑥：未决线头 —— recap_inputs.threads 台账条目 + 本章 opened/closed 义务
# ---------------------------------------------------------------------------


def render_section5(
    threads_data: dict,
    thread_ids: list[str],
    current_entry: dict,
    buffer_advance_payoff: dict[str, list[tuple[str, dict]]],
    buffer_open_events: list[tuple[str, dict]],
    sequence: dict[str, int] | None = None,
    cutoff: int | None = None,
) -> str:
    lines = ["## 未决线头", ""]
    if sequence is not None and cutoff is None:
        cutoff = max(sequence.values(), default=0)
    threads = threads_data.get("threads") or []
    by_id = {t.get("thread_id"): t for t in threads if isinstance(t, dict)}

    if thread_ids:
        for tid in thread_ids:
            t = by_id.get(tid)
            if not t:
                lines.append(f"- [{tid}]（台账中未找到该条目）")
            else:
                horizon = (t.get("intended_payoff") or {}).get("horizon", "")
                opened = source_position(t.get("opened_at"), sequence) if sequence is not None else None
                if sequence is not None and (opened is None or opened > cutoff):
                    # A planned thread can be referenced by the current outline;
                    # its planned opening is not already established continuity.
                    lines.append(f"- [{tid}] 线头设计（尚无本窗口内的开启来源）：{t.get('statement', '')}（预期回收：{horizon}）")
                else:
                    events = []
                    for index, event in enumerate(t.get("events") or []):
                        if not isinstance(event, dict):
                            raise DataError(f"线头 {tid}: events 条目必须为映射")
                        position = source_position(event.get("at"), sequence) if sequence is not None else index
                        if position is None:
                            warn_once(f"线头 {tid}: 事件 {event.get('at')} 无法定位，未注入")
                        elif cutoff is None or position <= cutoff:
                            events.append((position, index, event))
                    events.sort(key=lambda item: item[:2])
                    historical = sequence is not None and cutoff < max(sequence.values(), default=0)
                    if historical:
                        status = "paid" if any(e[2].get("kind") == "payoff" for e in events) else ("advanced" if events else "open")
                        status_note = f"来源窗口内事件状态: {status}"
                    else:
                        status_note = f"status: {t.get('status', '')}"
                    lines.append(
                        f"- [{tid}] ({t.get('kind', '')}, {status_note}) "
                        f"初始埋设：{t.get('statement', '')}（opened_at: {t.get('opened_at')}；预期回收：{horizon}）"
                    )
                    if events:
                        latest = events[-1][2]
                        lines.append(f"  - 最近已发生事件（{latest.get('at')}）：[{latest.get('kind')}] {latest.get('note', '')}")
                        if len(events) > 1:
                            lines.append("  - 其余推进经过按需回读 series/ledgers/threads.yaml 中本来源窗口的 events。")
            for chap_id, ev in buffer_advance_payoff.get(tid, []):
                lines.append(
                    f"  - 最近事件（buffer 候选，来自 {chap_id}）：[{ev.get('kind')}] {ev.get('note', '')}"
                )
    else:
        lines.append("（recap_inputs.threads 为空）")

    if buffer_open_events:
        lines.append("")
        lines.append("### 新线头（buffer 候选）")
        for chap_id, ev in buffer_open_events:
            horizon = (ev.get("intended_payoff") or {}).get("horizon", "")
            lines.append(
                f"- [{ev.get('thread_id')}] ({ev.get('thread_kind', '')}) "
                f"{ev.get('statement', '')}（预期回收：{horizon}，来自 {chap_id}）"
            )

    opened = current_entry.get("opened") or []
    closed = current_entry.get("closed") or []
    lines.append("")
    lines.append("**本章义务**：")
    if opened or closed:
        lines.append(f"- 需开启：{', '.join(opened) if opened else '（无）'}")
        lines.append(f"- 需回收：{', '.join(closed) if closed else '（无）'}")
    else:
        lines.append("（本章无开启/回收义务）")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run(work_dir: Path, chapter_id: str, budget_chars: int, facts_cap: int) -> Path:
    chapter_index, volumes_data = load_all_volumes(work_dir)

    info = chapter_index.get(chapter_id)
    if info is None:
        raise BlockingError(
            f"未找到 chapter_id={chapter_id} 对应的章卡（chapter_card.yaml）："
            f"该 chapter_id 未出现在任何卷纲 series/volumes/*.yaml 的 chapters[] "
            f"列表中，无法反查所属卷号以定位 chapters/V0N/{chapter_id}/ 路径"
        )

    vol_id = info["volume_id"]
    volume_data = volumes_data[vol_id]
    chapter_dir = work_dir / "chapters" / vol_id / chapter_id
    chapter_card_path = chapter_dir / "chapter_card.yaml"
    if not chapter_card_path.is_file():
        raise BlockingError(f"chapter_card.yaml 不存在: {chapter_card_path}")

    chapter_card = load_yaml_or_none(chapter_card_path) or {}
    published_seq, published_cutoff = load_context_clock(work_dir, chapter_index, chapter_id)
    historical = published_cutoff < max(published_seq.values(), default=0)
    prev_chapter = chapter_card.get("prev_chapter")
    recap_inputs = chapter_card.get("recap_inputs") or {}
    characters = recap_inputs.get("characters") or []
    locations = recap_inputs.get("locations") or []
    items = recap_inputs.get("items") or []
    thread_ids = recap_inputs.get("threads") or []
    declared_sections = recap_inputs.get("worldbook_sections") or []
    try:
        ids, names = character_names(work_dir)
        characters = [resolve_character(c, ids, names) or c for c in characters]
        anchors = load_chapter_anchors(work_dir)
        errors = validate_tentpoles(volume_data.get("tentpoles"), anchors, vol_id)
        if errors:
            raise DataError(f"series/volumes/{vol_id}.yaml: {'; '.join(errors)}")
    except (CharacterContextError, ValueError) as exc:
        raise DataError(str(exc)) from exc
    is_opening = prev_chapter is None
    current_unit = info.get("unit")

    # ---- 段①素材 ----
    story_bible = load_yaml_or_none(work_dir / "series" / "story_bible.yaml")
    if not story_bible or not story_bible.get("frozen"):
        raise DataError("series/story_bible.yaml 不存在或缺 frozen 区")
    frozen = story_bible["frozen"]

    far_items = [] if is_opening else collect_far_volume_digests(work_dir, volumes_data, vol_id)
    far_originally_empty = not far_items
    unit_items = [] if is_opening else collect_prior_unit_digests(work_dir, vol_id, volume_data, current_unit)
    unit_originally_empty = not unit_items
    recap_items = (
        [] if is_opening
        else collect_prev_chain_recaps(work_dir, chapter_index, current_unit, vol_id, prev_chapter)
    )
    # 卷首章特例：跨卷承接章的中距离缓冲（上一卷末单元 paragraph），不参与裁剪
    prev_vol_unit_item = (
        collect_prev_volume_last_unit_digest(work_dir, volumes_data, vol_id)
        if (not is_opening and info["position"] == 0)
        else None
    )

    # ---- 段②-⑥素材 ----
    wb_sections = load_worldbook_sections(work_dir)
    facts_current = load_yaml_or_none(work_dir / "series" / "ledgers" / "facts_current.yaml")
    history_gaps: set[tuple[str, str]] = set()
    if historical or facts_current is None:
        ledger = load_yaml_or_none(work_dir / "series" / "ledgers" / "world_facts.yaml")
        if ledger is not None:
            ledger_facts = ledger.get("facts") or []
            facts = facts_in_source_window(ledger_facts, published_seq, published_cutoff, historical=historical)
            if historical:
                gap_rows = []
                for row in ledger_facts:
                    position = source_position(row.get("established_at"), published_seq)
                    if (position is not None and position <= published_cutoff
                            and (row.get("status") == "retracted" or row.get("origin") == "errata")):
                        gap_rows.append({key: row.get(key) for key in ("entity", "attribute", "kind")})
                try:
                    # Apply the same explicit character-name compatibility to
                    # the affected keys and their still-visible predecessors.
                    facts = normalize_character_facts(facts, ids, names, set(locations) | set(items), set(characters))
                    gap_rows = normalize_character_facts(gap_rows, ids, names, set(locations) | set(items), set(characters))
                except CharacterContextError as exc:
                    raise DataError(str(exc)) from exc
                history_gaps = {(row.get("entity"), row.get("attribute")) for row in gap_rows}
                # A later retraction has no timestamp. Do not infer that its
                # predecessor was already restored at the historical cutoff.
                facts = [f for f in facts if (f.get("entity"), f.get("attribute")) not in history_gaps]
            facts = active_facts(facts)
        else:
            warn_once("原事实台账缺失，仅过滤现存视图；历史状态缺口需回读发布原文")
            facts = facts_in_source_window((facts_current or {}).get("facts") or [], published_seq, published_cutoff, historical=historical)
    else:
        facts = facts_in_source_window(facts_current.get("facts") or [], published_seq, published_cutoff)
    threads_data = load_yaml_or_none(work_dir / "series" / "ledgers" / "threads.yaml") or {}

    # ---- buffer 前章合并素材：series_state.buffer.drafted_unpublished 中
    # 位于 prev 链上游的章，其 recap.yaml.deltas 尚未入台账 ----
    series_state = load_yaml_or_none(work_dir / "series" / "series_state.yaml")
    buffer_ids = set((series_state or {}).get("buffer", {}).get("drafted_unpublished") or [])
    buffer_deltas_chain = (
        [] if is_opening
        else collect_buffer_ancestor_deltas(work_dir, chapter_index, prev_chapter, buffer_ids)
    )
    source_order = {cid: seq for cid, seq in published_seq.items() if seq <= published_cutoff}
    for offset, (cid, _) in enumerate(buffer_deltas_chain, 1):
        source_order[cid] = published_cutoff + offset

    buffer_fact_deltas: list[tuple[str, list[dict]]] = []
    buffer_character_deltas: dict[str, list[tuple[str, dict]]] = {}
    buffer_advance_payoff: dict[str, list[tuple[str, dict]]] = {}
    buffer_open_events: list[tuple[str, dict]] = []
    for chap_id, deltas in buffer_deltas_chain:
        buffer_fact_deltas.append((chap_id, facts_in_source_window(
            deltas.get("fact_deltas") or [], source_order, source_order[chap_id],
        )))
        for cd in deltas.get("character_deltas") or []:
            if isinstance(cd, dict) and cd.get("char_id") in characters:
                buffer_character_deltas.setdefault(cd["char_id"], []).append((chap_id, cd))
        for ev in deltas.get("thread_events") or []:
            if not isinstance(ev, dict):
                continue
            if ev.get("kind") == "open":
                buffer_open_events.append((chap_id, ev))
            elif ev.get("thread_id") in thread_ids:
                buffer_advance_payoff.setdefault(ev["thread_id"], []).append((chap_id, ev))

    try:
        noncharacters = set(locations) | set(items)
        selected = set(characters)
        for row in facts:
            if (isinstance(row, dict) and row.get("kind") != "relation"
                    and isinstance(row.get("entity"), str)
                    and row["entity"] not in noncharacters | ids
                    and names.get(row["entity"], set()) & selected):
                warn_once(f"事实 {row.get('fact_id', '')} 的 entity={row['entity']!r} 使用显示名；"
                          "主体类型未明，未自动归入人物。确认是人物后使用其 char_id。")
        facts = normalize_character_facts(facts, ids, names, noncharacters, selected)
        buffer_fact_deltas = [
            (cid, normalize_character_facts(rows, ids, names, noncharacters, selected))
            for cid, rows in buffer_fact_deltas
        ]
    except CharacterContextError as exc:
        raise DataError(str(exc)) from exc
    superseded_by_buffer = {f.get("supersedes") for _, rows in buffer_fact_deltas for f in rows if f.get("supersedes")}
    facts = [f for f in facts if f.get("fact_id") not in superseded_by_buffer]
    # These sections are not budget-trimmed; parse and validate them once.
    section2 = render_section2(volume_data, info, chapter_id, current_unit)
    section4 = render_section4(
        work_dir, characters, chapter_index, vol_id, buffer_character_deltas, chapter_id, anchors,
    )

    def render_full(far: list, unit: list, wb_soft_cut: set[str], cap: int) -> str:
        section1 = render_section1(
            frozen, far, far_originally_empty, unit, unit_originally_empty, recap_items,
            is_opening, prev_vol_unit_item, intent=story_bible.get("intent"),
        )
        sections = [HEADER, section1, section2]
        if wb_sections is not None:
            sections.append(
                render_worldbook_section(work_dir, wb_sections, declared_sections, wb_soft_cut)
            )
        sections.append(
            render_section3(facts, characters, locations, items, buffer_fact_deltas, cap, source_order, history_gaps)
        )
        sections.append(section4)
        sections.append(
            render_section5(threads_data, thread_ids, info["entry"], buffer_advance_payoff, buffer_open_events, published_seq, published_cutoff)
        )
        return "\n\n".join(s.rstrip("\n") for s in sections) + "\n"

    soft_cut: set[str] = set()
    cap_now = facts_cap
    full_md = render_full(far_items, unit_items, soft_cut, cap_now)

    if len(full_md) > budget_chars:
        far_trim = list(far_items)
        unit_trim = list(unit_items)
        while len(full_md) > budget_chars and far_trim:
            far_trim.pop(0)
            full_md = render_full(far_trim, unit_trim, soft_cut, cap_now)
        while len(full_md) > budget_chars and unit_trim:
            unit_trim.pop(0)
            full_md = render_full(far_trim, unit_trim, soft_cut, cap_now)
        # 阶梯 3：声明分册素材库部按声明序逐册置省略注（硬约束部恒保）
        if wb_sections is not None:
            for sid in declared_sections:
                if len(full_md) <= budget_chars:
                    break
                soft_cut.add(sid)
                full_md = render_full(far_trim, unit_trim, soft_cut, cap_now)
        # 阶梯 4：每实体事实条数上限降档（只降不升——用户已给更紧上限时跳过松档）
        for stage in (8, 5, 3):
            if len(full_md) <= budget_chars:
                break
            if facts_cap > 0 and stage >= facts_cap:
                continue
            cap_now = stage
            full_md = render_full(far_trim, unit_trim, soft_cut, cap_now)
        if len(full_md) > budget_chars:
            print(
                f"[assemble_serial_context WARN] 预算 --budget-chars={budget_chars} 不足："
                f"已用尽全部裁剪阶梯（digest 明细/素材库/事实上限降档），仍输出 "
                f"{len(full_md)} 字符（本单元前章 recap、卷纲切片、硬约束部、"
                "角色现状与未决线头不裁剪）",
                file=sys.stderr,
            )

    output_path = chapter_dir / "pipeline" / "serial_context.md"
    atomic_write_text(output_path, full_md)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    parser.add_argument("--chapter", required=True, help="裸章号，如 C0005")
    parser.add_argument(
        "--budget-chars", type=int, default=12000,
        help="输出字符预算（启发式参考，默认 12000）",
    )
    parser.add_argument(
        "--max-facts-per-entity", type=int, default=12,
        help="段④每实体事实条数上限（保序裁剪，0 = 不设上限；默认 12）",
    )
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[assemble_serial_context ERROR] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 2

    if not CHAPTER_RE.match(args.chapter):
        print(f"[assemble_serial_context ERROR] --chapter 必须匹配 C\\d{{4}}，实为 {args.chapter!r}", file=sys.stderr)
        return 2

    try:
        output_path = run(work_dir, args.chapter, args.budget_chars, args.max_facts_per_entity)
    except BlockingError as exc:
        print(f"[assemble_serial_context ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[assemble_serial_context ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"✅ serial_context written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
