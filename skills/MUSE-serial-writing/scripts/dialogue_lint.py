#!/usr/bin/env python3
"""S3 — 对白多合一 lint（纯台词段 / 指代混乱 / 孤立说话动作 / 模板说话动词）。

覆盖 55+1 条清单第 16/20/56 条 + 条 4 模板扩展。
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

import yaml

DIALOGUE_PATTERN = re.compile(r'(["“][^"”]{1,200}["”])')
SPEECH_VERB_TEMPLATE = re.compile(r"[\u4e00-\u9fa5]{1,4}[地的]说道")
# v9 commit 7: stock_speech_tag — 库存语气标签（round-3 实证驱动）
# "淡淡道 / 声音不高 / 低声道 / 平静道 / 沉声道 / 悠悠道" 等模板替代角色实际语气、
# 动作压力或对白本身。confidence=medium：脚本作低风险 hit list，A 组人工核实
# "删去后信息不损失"原则——避免误伤合法语境（如某角色一贯的"低声道"刻画）。
STOCK_SPEECH_TAG = re.compile(
    r"(声音不高|淡淡(?:道|地说|一笑)|低声道|平静道|沉声道|悠悠道)"
)
# 弱表述候选：只给 A 组提供人物描写附近的低风险提示，不直接判错。
# medium = 有锚点（声音/神情/动作/心中）；low = 仅代词锚点，召回更宽，A 组按对比式具体动作豁免规则筛掉。
WEAK_CHARACTER_EXPRESSION_PATTERNS = [
    (re.compile(
        r"((?:声音|语声|嗓音|话音|语气)[^。！？\n]{0,8}"
        # 长 alternative 在前——避免"平淡"被先命中的"平"截断
        r"(?:压低到|压得极低|低了下去|(?<!降)低到|没有起伏|不带情绪|不带感情|"
        r"仍平|平平|平淡|平静|短硬|不高|不大|不响|不扬|很轻|很低|极低|"
        r"温和|微弱|发紧|平))"
    ), "medium"),
    (re.compile(
        r"((?:神色|脸色|表情|眼神|目光|眼里|脸上)[^。！？\n]{0,10}"
        r"(?:不变|没变|没有变化|没有波澜|没有怒气|没有焦虑|"
        r"没有愤怒|没有笑意|平静|淡淡|显得|有些))"
    ), "medium"),
    (re.compile(
        r"((?:脚步|步子|动作|手|指尖|肩|背影|身子)[^。！？\n]{0,8}"
        r"(?:不慢|不快|不重|不轻|不动|没动|没有动|没有抖|没抖|"
        r"没有停|没停|(?:仍|依旧|微微|有些)[^。！？\n]{0,4}(?:抖|动|停|垂|攥)))"
    ), "medium"),
    (re.compile(
        r"((?:心中|心里)[^。！？\n]{0,12}"
        r"(?:只是|仿佛|似乎|好像|像是|几乎|觉得|显得|没有|没|不是|(?:仍|依旧)[^。！？\n]{0,4}(?:想|觉|记|念)))"
    ), "medium"),
    # 代词锚点：宽召回兜底，无身体部位/感官名词锚点时仍捕捉"他/她 + 弱副词 + 弱动词"。
    # 因结构上无法区分"对比式具体动作"（接过 + 没饮 + 望着），固定 confidence=low，
    # 由 A 组按 A_aesthetic.md weak_character_expression 豁免规则筛除有效描写。
    (re.compile(
        r"((?:他(?!们)|她(?!们))"
        r"[^。！？\n\"“”'‘’：:]{0,8}"
        r"(?:只是|只|没有|没|并不|不再|仍|依旧|微微|有些)"
        r"[^。！？\n\"“”'‘’：:]{0,10}"
        r"(?:看着|望着|盯着|说话|回答|动|抖|停|笑|哭|问))"
    ), "low"),
    (re.compile(r"(不是问句)"), "medium"),
]
SPEAKER_AMBIGUOUS = ["那人", "对方"]

DEFAULT_PURE_DIALOGUE_THRESHOLD = 0.80


def _locate(text: str, pos: int) -> str:
    return f"L{text.count(chr(10), 0, pos) + 1}"


def _line_no(text: str, pos: int) -> int:
    """返回字符位置对应的 1-indexed 行号。"""
    return text.count("\n", 0, pos) + 1


def _dialogue_line_numbers(text: str) -> set[int]:
    """所有含对白引号（DIALOGUE_PATTERN 命中）的行号集合（1-indexed）。"""
    return {_line_no(text, m.start()) for m in DIALOGUE_PATTERN.finditer(text)}


def _is_near_dialogue(line_no: int, dialogue_lines: set[int], window: int = 2) -> bool:
    """命中行 ± window 行内是否有对白行——hot zone 判定（A 组按此提高怀疑级别）。

    用纯行号窗口，不做同一说话人识别（对白前后 1-2 行的状态标签是
    weak_character_expression 高发区，无需区分是否同人对话）。
    """
    return any((line_no + offset) in dialogue_lines for offset in range(-window, window + 1))


def extract_dialogue_blocks(text: str) -> list[dict]:
    blocks = []
    for m in DIALOGUE_PATTERN.finditer(text):
        blocks.append({
            "content": m.group(0),
            "start": m.start(),
            "location": _locate(text, m.start()),
        })
    return blocks


def _is_description(para: str) -> bool:
    """描写段判定：非空、非纯对白段、字数 ≥ 6。"""
    if not para.strip():
        return False
    dialogue_chars = sum(len(m.group(0)) for m in DIALOGUE_PATTERN.finditer(para))
    return dialogue_chars / max(len(para), 1) < 0.5 and len(para.strip()) >= 6


def detect_pure_dialogue(text: str, threshold: float = DEFAULT_PURE_DIALOGUE_THRESHOLD) -> list[dict]:
    """某段 ≥threshold 字符在引号内**且前后 ±1 段无描写句**才命中。"""
    hits = []
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    for idx, para in enumerate(paragraphs):
        if len(para) == 0:
            continue
        dialogue_chars = sum(len(m.group(0)) for m in DIALOGUE_PATTERN.finditer(para))
        if dialogue_chars / len(para) < threshold:
            continue
        prev_para = paragraphs[idx - 1] if idx > 0 else ""
        next_para = paragraphs[idx + 1] if idx < len(paragraphs) - 1 else ""
        if _is_description(prev_para) or _is_description(next_para):
            continue
        hits.append({
            "rule": "pure_dialogue_paragraph",
            "pattern": f"对白占比 {dialogue_chars / len(para):.0%}，前后无描写",
            "location": f"para{idx + 1}",
            "snippet": para[:60],
            "confidence": "high",
        })
    return hits


def detect_ambiguous_referent(text: str) -> list[dict]:
    """对话密集段内模糊代词"那人/对方"作说话人 ≥2 次（收窄剔除"他"——高频正常代词）。"""
    hits = []
    lines = [l for l in text.splitlines() if l.strip()]
    window_size = 5
    # 短文本：整体作一个窗口；长文本：滑动窗口
    windows = []
    if len(lines) <= window_size:
        windows.append((0, "\n".join(lines), len(lines)))
    else:
        for i in range(len(lines) - window_size + 1):
            windows.append((i, "\n".join(lines[i:i + window_size]), window_size))

    for start, window, span in windows:
        if len(DIALOGUE_PATTERN.findall(window)) < 3:
            continue
        ambiguous_count = sum(window.count(w) for w in SPEAKER_AMBIGUOUS)
        if ambiguous_count >= 2:
            hits.append({
                "rule": "ambiguous_referent",
                "pattern": f"那人/对方 ×{ambiguous_count}",
                "location": f"L{start + 1}-{start + span}",
                "snippet": window[:80],
                "confidence": "medium",
            })
            break  # 一场景一报
    return hits


def detect_template_speech_verb(text: str) -> list[dict]:
    hits = []
    for m in SPEECH_VERB_TEMPLATE.finditer(text):
        hits.append({
            "rule": "template_speech_verb",
            "pattern": m.group(0),
            "location": _locate(text, m.start()),
            "snippet": m.group(0),
            "confidence": "high",
        })
    return hits


def detect_stock_speech_tag(text: str) -> list[dict]:
    """v9 commit 7: 库存语气标签命中（round-3 实证驱动 4 处实例）"""
    hits = []
    for m in STOCK_SPEECH_TAG.finditer(text):
        hits.append({
            "rule": "stock_speech_tag",
            "pattern": m.group(0),
            "location": _locate(text, m.start()),
            "snippet": text[max(0, m.start() - 10):min(len(text), m.end() + 30)],
            "confidence": "medium",
        })
    return hits


def detect_weak_character_expression_candidate(text: str) -> list[dict]:
    """人物声音/神情/动作/心理附近的弱表述候选。

    该规则只输出统一 candidate，由 A 组判断是否构成 micro_language 问题。
    与 stock_speech_tag 重叠的命中交给 stock_speech_tag，避免重复提示。

    每条 hit 附 ``near_dialogue: bool`` —— 命中行 ± 2 行内有对白引号即 True。
    A 组按 hot zone 提高怀疑级别（不强制必报，仍按豁免规则判读）。
    """
    hits = []
    seen: set[tuple[int, str]] = set()
    dialogue_lines = _dialogue_line_numbers(text)
    for pattern, confidence in WEAK_CHARACTER_EXPRESSION_PATTERNS:
        for m in pattern.finditer(text):
            match = m.group(1)
            if STOCK_SPEECH_TAG.search(match):
                continue
            key = (m.start(), match)
            if key in seen:
                continue
            seen.add(key)
            line_no = _line_no(text, m.start())
            hits.append({
                "rule": "weak_character_expression_candidate",
                "pattern": match,
                "location": _locate(text, m.start()),
                "snippet": text[max(0, m.start() - 10):min(len(text), m.end() + 30)],
                "confidence": confidence,
                "near_dialogue": _is_near_dialogue(line_no, dialogue_lines),
            })
    return hits


def detect_isolated_speech_beat(text: str, window: int = 2) -> list[dict]:
    """对白密集段前后 window 行无描写句的报警。"""
    hits = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not DIALOGUE_PATTERN.search(line):
            continue
        neighbors = lines[max(0, i - window):i] + lines[i + 1:i + 1 + window]
        has_description = any(
            bool(n.strip())
            and not DIALOGUE_PATTERN.search(n)
            and not n.rstrip().endswith(("说。", "道。", "问。", "答。", "笑。", "叹。"))
            for n in neighbors
        )
        if not has_description:
            hits.append({
                "rule": "isolated_speech_beat",
                "pattern": "前后无描写",
                "location": _locate(text, sum(len(l) + 1 for l in lines[:i])),
                "snippet": line[:60],
                "confidence": "medium",
            })
    return hits


def analyze(text: str, pure_dialogue_threshold: float = DEFAULT_PURE_DIALOGUE_THRESHOLD) -> dict:
    all_hits = (
        detect_pure_dialogue(text, threshold=pure_dialogue_threshold)
        + detect_ambiguous_referent(text)
        + detect_template_speech_verb(text)
        + detect_stock_speech_tag(text)
        + detect_weak_character_expression_candidate(text)
        + detect_isolated_speech_beat(text)
    )
    return {
        "hits": all_hits,
        "density": {
            "total_chars": len(text),
            "total_dialogue_blocks": len(extract_dialogue_blocks(text)),
            "hits_per_1k": round(len(all_hits) / max(len(text), 1) * 1000, 2),
            "top_patterns": [],
        },
        "meta": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="S3 dialogue lint")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--pure-dialogue-threshold", type=float, default=None)
    parser.add_argument("--genre", default=None)
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{args.scene_id}.md"
    if not scene_path.exists():
        print(f"[dialogue_lint] ERROR: {scene_path} not found", file=sys.stderr)
        return 1

    thresholds = {
        "pure_dialogue": args.pure_dialogue_threshold if args.pure_dialogue_threshold is not None else DEFAULT_PURE_DIALOGUE_THRESHOLD,
    }
    threshold_source = "cli" if args.pure_dialogue_threshold is not None else "default"

    text = scene_path.read_text(encoding="utf-8")
    result = analyze(text, pure_dialogue_threshold=thresholds["pure_dialogue"])
    result["meta"] = {
        "thresholds": thresholds,
        "threshold_source": threshold_source,
        "genre": args.genre,
    }
    output = {
        "scene_id": args.scene_id,
        "script": "dialogue_lint",
        "version": "r2",
        **result,
    }

    out_path = work_dir / "pipeline" / "review" / "lint" / f"{args.scene_id}.dialogue.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(output, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        f"✅ {out_path} · {len(result['hits'])} hits · "
        f"{result['density']['total_dialogue_blocks']} dialogue blocks"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
