"""段落密度分析脚本

为 MUSE pipeline 多处 skill 提供客观的段落结构度量：

- `scene-reference`（隐式，通过 kb_query.py）：在产出 ref 文件时注入范文的密度元数据
- `story-review`（显式）：对比场景输出 vs 对应范文的密度差距，标注偏离
- `phase7-integration`（显式）：批量扫描所有场景与范文对比，指导第三轮润色
- `novel-analysis`（可选）：建库时验证新入库小说的段落分布合理性

用法
----

单文件统计::

    python paragraph_density.py path/to/story.md [--format yaml|json|text] [--lang auto|zh|en]

对比模式（输出 vs 范文）::

    python paragraph_density.py --compare path/to/output.md path/to/reference.md

作为模块::

    from paragraph_density import analyze_file, compare_files
    stats = analyze_file("story.md")
    result = compare_files("output.md", "reference.md")
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal


# ============================================================================
# 度量定义
# ============================================================================

SIGNIFICANT_LONG_GAP = 15  # 长段落比例差 ≥15 百分点 → SIGNIFICANT_DEVIATION


@dataclass
class DensityStats:
    """段落密度统计结果"""
    n_paras: int
    total_sentences: int
    mean: float
    median: float
    stdev: float
    max_len: int
    short_pct: float   # ≤2 句段落占比
    medium_pct: float  # 3-5 句
    long_pct: float    # ≥6 句
    vlong_pct: float   # ≥10 句
    lang: str


# ============================================================================
# 语言检测
# ============================================================================

def detect_lang(text: str) -> Literal["zh", "en"]:
    """从前 500 字符判断语言——汉字比字母多即认为是中文"""
    sample = text[:500]
    zh_chars = len(re.findall(r"[\u4e00-\u9fff]", sample))
    en_chars = len(re.findall(r"[a-zA-Z]", sample))
    return "zh" if zh_chars > en_chars else "en"


# ============================================================================
# 段落切分
# ============================================================================

def _is_metadata_block(block: str) -> bool:
    """识别并跳过标题、分隔符、元数据短行、装饰符等非正文段落"""
    b = block.strip()
    if not b:
        return True
    if b.startswith("#"):
        return True
    if b.startswith("<!--") or b.startswith("---"):
        return True
    if b.startswith(">"):
        return True
    # 短粗体元数据行（如 **出处**：... ）
    if b.startswith("**") and "**" in b[2:] and len(b) < 80:
        return True
    # 纯装饰行 ＊　　＊　　＊
    if "＊" in b and len(b.replace("＊", "").replace("\u3000", "").strip()) < 5:
        return True
    return False


def split_paragraphs(text: str) -> list[str]:
    """将文本切分为正文段落列表

    处理两种常见格式：

    1. **空行分段**（标准 Markdown）：按 ``\\n\\n`` 切分
    2. **全角空格缩进分段**（中文传统排版，如金庸原著）：段落之间无空行，
       每段以 ``\\u3000\\u3000`` 起始。当一个 block 的多行中 >50% 以全角空格
       开头时，按这些标记重新拆分
    """
    # 第一步：空行切分 + 元数据过滤
    raw_blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    content_blocks = [b for b in raw_blocks if not _is_metadata_block(b)]

    # 第二步：对每个 block 检查是否是"伪单段"——实际上是缩进分段的 block
    final: list[str] = []
    for block in content_blocks:
        lines = block.split("\n")
        indented_lines = [
            line for line in lines
            if line.startswith("\u3000\u3000") or line.startswith("\u3000")
        ]
        if len(lines) > 5 and len(indented_lines) / len(lines) > 0.5:
            # 按全角空格缩进重新拆段
            current_para: list[str] = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if line.startswith("\u3000\u3000") or line.startswith("\u3000"):
                    if current_para:
                        final.append("".join(current_para))
                    current_para = [stripped]
                else:
                    current_para.append(stripped)
            if current_para:
                final.append("".join(current_para))
        else:
            final.append(block)

    return final


# ============================================================================
# 句子计数
# ============================================================================

def count_sentences(paragraph: str, lang: str = "auto") -> int:
    """统计单个段落的句子数——至少返回 1"""
    p = paragraph.strip().lstrip("\u3000").lstrip()
    if not p:
        return 1

    if lang == "auto":
        lang = detect_lang(p)

    if lang == "zh":
        # 中文句末 + 段内可能混入的英文
        zh = len(re.findall(r"[。！？]", p))
        en_mixed = len(re.findall(r'[.!?](?:\s|$|")', p))
        return max(zh + en_mixed, 1)
    else:
        # 英文：句末 + 大写开头 / 行尾 / 引号
        en = len(re.findall(r'[.!?](?:\s+[A-Z]|\s*$|")', p))
        if en == 0:
            # 回退：直接数 .!?
            en = len(re.findall(r"[.!?]", p))
        return max(en, 1)


# ============================================================================
# 统计计算
# ============================================================================

def compute_stats(lengths: list[int], lang: str = "zh") -> DensityStats | None:
    """从句数列表计算密度统计"""
    if not lengths:
        return None
    n = len(lengths)
    total = sum(lengths)
    short = sum(1 for l in lengths if l <= 2)
    medium = sum(1 for l in lengths if 3 <= l <= 5)
    long_ = sum(1 for l in lengths if l >= 6)
    vlong = sum(1 for l in lengths if l >= 10)
    return DensityStats(
        n_paras=n,
        total_sentences=total,
        mean=round(total / n, 2),
        median=statistics.median(lengths),
        stdev=round(statistics.stdev(lengths), 2) if n > 1 else 0.0,
        max_len=max(lengths),
        short_pct=round(short / n * 100, 1),
        medium_pct=round(medium / n * 100, 1),
        long_pct=round(long_ / n * 100, 1),
        vlong_pct=round(vlong / n * 100, 1),
        lang=lang,
    )


# ============================================================================
# 文件分析接口
# ============================================================================

def analyze_text(text: str, lang: str = "auto") -> DensityStats | None:
    """分析一段文本，返回密度统计"""
    if lang == "auto":
        lang = detect_lang(text)
    paras = split_paragraphs(text)
    lengths = [count_sentences(p, lang) for p in paras]
    return compute_stats(lengths, lang)


def analyze_file(path: str | Path, lang: str = "auto") -> DensityStats | None:
    """分析一个文件，返回密度统计"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"❌ 读取文件失败: {path}: {e}", file=sys.stderr)
        return None
    return analyze_text(text, lang)


# ============================================================================
# 对比模式
# ============================================================================

def compare_files(
    output_path: str | Path,
    reference_path: str | Path,
) -> dict | None:
    """对比输出文件与范文文件的段落密度"""
    output_stats = analyze_file(output_path)
    ref_stats = analyze_file(reference_path)
    if output_stats is None or ref_stats is None:
        return None

    gap = {
        "long_pct": round(output_stats.long_pct - ref_stats.long_pct, 1),
        "vlong_pct": round(output_stats.vlong_pct - ref_stats.vlong_pct, 1),
        "stdev": round(output_stats.stdev - ref_stats.stdev, 2),
        "max_len": output_stats.max_len - ref_stats.max_len,
    }

    verdict = "ALIGNED"
    if abs(gap["long_pct"]) >= SIGNIFICANT_LONG_GAP:
        verdict = "SIGNIFICANT_DEVIATION"

    return {
        "output": {
            "long_pct": output_stats.long_pct,
            "vlong_pct": output_stats.vlong_pct,
            "stdev": output_stats.stdev,
            "max_len": output_stats.max_len,
            "n_paras": output_stats.n_paras,
        },
        "reference": {
            "long_pct": ref_stats.long_pct,
            "vlong_pct": ref_stats.vlong_pct,
            "stdev": ref_stats.stdev,
            "max_len": ref_stats.max_len,
            "n_paras": ref_stats.n_paras,
        },
        "gap": gap,
        "verdict": verdict,
    }


# ============================================================================
# 输出格式化
# ============================================================================

def format_yaml(stats: DensityStats) -> str:
    """YAML 风格输出（纯字符串，不依赖 pyyaml）"""
    d = asdict(stats)
    lines = []
    for key in (
        "n_paras", "total_sentences", "mean", "median", "stdev", "max_len",
        "short_pct", "medium_pct", "long_pct", "vlong_pct", "lang",
    ):
        v = d[key]
        if isinstance(v, str):
            lines.append(f"{key}: {v}")
        else:
            lines.append(f"{key}: {v}")
    return "\n".join(lines)


def format_text(stats: DensityStats) -> str:
    """人类可读的简短文本"""
    return (
        f"段落总数 {stats.n_paras}, 总句数 {stats.total_sentences}, "
        f"段均 {stats.mean} 句, 方差 {stats.stdev}, 最长 {stats.max_len} 句\n"
        f"  短段落(≤2)  {stats.short_pct}%\n"
        f"  中段落(3-5) {stats.medium_pct}%\n"
        f"  长段落(≥6)  {stats.long_pct}%\n"
        f"  极长(≥10)   {stats.vlong_pct}%\n"
        f"  语言: {stats.lang}"
    )


def format_compare_yaml(result: dict) -> str:
    """对比结果的 YAML 风格输出"""
    lines = ["output:"]
    for k, v in result["output"].items():
        lines.append(f"  {k}: {v}")
    lines.append("reference:")
    for k, v in result["reference"].items():
        lines.append(f"  {k}: {v}")
    lines.append("gap:")
    for k, v in result["gap"].items():
        lines.append(f"  {k}: {v}")
    lines.append(f"verdict: {result['verdict']}")
    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="段落密度分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python paragraph_density.py story.md\n"
            "  python paragraph_density.py story.md --format json\n"
            "  python paragraph_density.py --compare output.md reference.md\n"
        ),
    )
    parser.add_argument(
        "files", nargs="*",
        help="要分析的文件（单文件模式）",
    )
    parser.add_argument(
        "--compare", nargs=2, metavar=("OUTPUT", "REFERENCE"),
        help="对比模式：比较两个文件的段落密度",
    )
    parser.add_argument(
        "--format", choices=["yaml", "json", "text"], default="yaml",
        help="输出格式 (默认: yaml)",
    )
    parser.add_argument(
        "--lang", choices=["auto", "zh", "en"], default="auto",
        help="语言 (默认: auto)",
    )
    args = parser.parse_args()

    if args.compare:
        result = compare_files(args.compare[0], args.compare[1])
        if result is None:
            return 1
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_compare_yaml(result))
        return 0 if result["verdict"] == "ALIGNED" else 2

    if not args.files:
        parser.error("必须提供要分析的文件，或使用 --compare")

    for i, f in enumerate(args.files):
        stats = analyze_file(f, args.lang)
        if stats is None:
            return 1
        if len(args.files) > 1:
            print(f"=== {f} ===")
        if args.format == "json":
            print(json.dumps(asdict(stats), ensure_ascii=False, indent=2))
        elif args.format == "text":
            print(format_text(stats))
        else:
            print(format_yaml(stats))
        if i < len(args.files) - 1:
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
