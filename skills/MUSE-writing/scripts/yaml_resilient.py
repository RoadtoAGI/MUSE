"""LLM 产 yaml 常见 quote 越界的消费端 graceful recovery。

定位的失败 pattern：mapping value 用双引号 scalar，但内容含未转义内 `"`，
触发 yaml.safe_load 抛 YAMLError。例：

    value_start: "沈砚秋已三日前出长安。裴自以为已"妥善"处理。"

恢复方式：把该行改写成 block scalar `|`，原内容保持不动（block scalar 不
要求转义引号）：

    value_start: |
      沈砚秋已三日前出长安。裴自以为已"妥善"处理。

适用约束：
- 只动 `<key>: "..."` 形式的 mapping value 行
- 已转义 `\\"` / block scalar / 单引号 scalar / 列表项均不动
- 缩进错乱、缺字段等结构 / schema 错一律 raise 原始 YAMLError

主调用方：extract_scene_card.py / generate_phase6_index.py
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class RecoveryReport:
    recovered_lines: list[int] = field(default_factory=list)
    fixed_text: str | None = None


_KEY_VALUE_DQUOTE_RE = re.compile(
    r'^(?P<indent>\s*)(?P<key>[\w_-]+)\s*:\s*"(?P<value>.*)"\s*$'
)

# F3: list item 双引号形式 `<indent>- "<value>"<trailing>`
# greedy `.*"` 让 value 吃到最后一个 "，trailing 拿最后一个 " 之后剩余非空白
_LIST_ITEM_DQUOTE_RE = re.compile(
    r'^(?P<indent>\s*)-\s+"(?P<value>.*)"(?P<trailing>.*)$'
)


def _count_unescaped_dquotes(s: str) -> int:
    """Count " not preceded by backslash."""
    count = 0
    for i, ch in enumerate(s):
        if ch == '"' and (i == 0 or s[i - 1] != '\\'):
            count += 1
    return count


def _is_broken_dquote_line(line: str) -> tuple[bool, str | None, str | None, str | None]:
    """识别 `<indent><key>: "<value with inner ">"` 形式。

    返回 (是否需修, indent, key, value)；不需修时返回 (False, None, None, None)。
    """
    m = _KEY_VALUE_DQUOTE_RE.match(line)
    if not m:
        return False, None, None, None
    value = m.group("value")
    # value 部分若含未转义 `"`，说明实际是 `"…"内嵌"…"` 越界
    if _count_unescaped_dquotes(value) == 0:
        return False, None, None, None
    return True, m.group("indent"), m.group("key"), value


def _is_broken_list_item_line(line: str) -> tuple[bool, str | None, str | None]:
    """识别 broken list item 形式：

    (1) `- "外"内"尾"`：value 含未转义内 `"`，无 trailing
        → 剥外层引号（与 mapping value 处理一致），body = `外"内"尾`
    (2) `- "well-quoted"（trailing plain）`：well-quoted 后跟非空白 plain 续接
        → 保留完整字面（外层引号本身是引文语义的一部分），body = `"well-quoted"（trailing plain）`

    返回 (是否需修, indent, body)；不需修时 (False, None, None)。
    """
    m = _LIST_ITEM_DQUOTE_RE.match(line)
    if not m:
        return False, None, None
    value = m.group("value")
    trailing = m.group("trailing")
    inner_unescaped = _count_unescaped_dquotes(value) > 0
    has_trailing = bool(trailing.strip())
    if not (inner_unescaped or has_trailing):
        return False, None, None
    if has_trailing:
        # case 2：trailing 在，外层引号属引文，整体保留
        body = f'"{value}"{trailing}'
    else:
        # case 1：纯内引号越界，外层引号是 yaml 包裹符号应剥
        body = value
    return True, m.group("indent"), body


def _promote_to_block_scalar(indent: str, key: str, value: str) -> str:
    """把 `key: "value"` 升级为 block scalar `key: |-\\n  value`。

    用 `|-`（strip mode）而非裸 `|`，保证还原值不带尾 \\n——与原双引号
    scalar 字面语义一致（双引号 scalar 不含隐含尾换行）。
    """
    body_indent = indent + "  "
    return f"{indent}{key}: |-\n{body_indent}{value}\n"


def _promote_list_item_to_block_scalar(indent: str, body: str) -> str:
    """把 broken list item `- "..."<trailing>` 升级为 `- |-\\n  <body>`。

    body 是含原 quotes 的完整字面字符串；缩进相对 `-` 留 2 格。
    """
    body_indent = indent + "  "
    return f"{indent}- |-\n{body_indent}{body}\n"


def _attempt_recovery(text: str) -> tuple[str, list[int]]:
    """扫一遍文本，找所有 broken `<key>: "..."` 行升级为 block scalar。

    返回 (fixed_text, 1-based recovered line numbers)。
    """
    lines = text.splitlines(keepends=False)
    out: list[str] = []
    fixed_at: list[int] = []
    for i, raw_line in enumerate(lines, start=1):
        broken, indent, key, value = _is_broken_dquote_line(raw_line)
        if broken:
            out.append(_promote_to_block_scalar(indent, key, value).rstrip("\n"))
            fixed_at.append(i)
            continue
        li_broken, li_indent, li_body = _is_broken_list_item_line(raw_line)
        if li_broken:
            out.append(_promote_list_item_to_block_scalar(li_indent, li_body).rstrip("\n"))
            fixed_at.append(i)
            continue
        out.append(raw_line)
    # 重新拼回（splitlines 已去掉尾 \n，确保结尾换行存在）
    fixed_text = "\n".join(out)
    if text.endswith("\n"):
        fixed_text += "\n"
    return fixed_text, fixed_at


def load_yaml_resilient(text: str) -> tuple[Any, RecoveryReport]:
    """优先 strict 解析；失败时尝试一次 `"..."` → `|` 自救，仍失败则 raise。

    Args:
        text: yaml 文本。

    Returns:
        (parsed_doc, RecoveryReport)。RecoveryReport.recovered_lines 列出
        被改写的 1-based 行号，空列表表示无需自救。

    Raises:
        yaml.YAMLError: 自救后仍失败 / 自救不适用（无 broken 行可改）/
            原 yaml 无 broken 行但本身有其他结构错。
    """
    try:
        return yaml.safe_load(text), RecoveryReport()
    except yaml.YAMLError:
        fixed_text, fixed_at = _attempt_recovery(text)
        if not fixed_at:
            # 没有 `<key>: "..."` 行可改，原错保留
            raise
        # 自救后再 parse；如仍失败则把这次的错暴露（说明不是 quote 问题）
        doc = yaml.safe_load(fixed_text)
        return doc, RecoveryReport(recovered_lines=fixed_at, fixed_text=fixed_text)
