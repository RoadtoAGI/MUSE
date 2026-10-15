#!/usr/bin/env python3
"""verify_shortform_review_complete.py — 短链终验：核对交付包，列出未解决项。

成稿与修订各一轮：审阅 PASS 就交付，REVISE 时修订一次后交付，作者要再修时手动发起下一轮。
所以终验只拦交付包本身的缺陷，质量结论列出来交作者，不拦交付。

exit 1（交付包有缺陷，补齐后再验）：
  ① story.md 不在场
  ② 没有 pipeline/shortform/review/short_story_review.rN.yaml，或最新一份格式错误
     （含 status=PASS 却有 BLOCKER 这类自相矛盾）
  ③ 最新报告的 story_sha256 与当前 story.md 不同，且审阅之后没有修订记录
     （revision_summary.md 不晚于该报告）——正文在审阅后改过却说不清依据
  ④ conception.requirements 非空时，requirements_coverage 缺失或与其不一一对应，
     或某项标 met=true 却没有 evidence

列出、不拦交付：wholetext gate 对当前正文 FAIL；审阅 status=REVISE；BLOCKER finding；
未满足的 requirements；修订后未复审（列出 revision_summary.md 的 status）。

用法:
    python3 verify_shortform_review_complete.py --work-dir <run 目录>

退出码: 0=可交付（未解决项随输出列出）; 1=交付包有缺陷; 2=用法/环境错误
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

REVIEW_NAME_RE = re.compile(r"^short_story_review\.r(\d+)\.yaml$")

# 审阅报告 schema（终验 gate 是该报告的属主校验器——shortform/review/ 不归 contract hook）
REPORT_ALLOWED = {"story_sha256", "status", "requirements_coverage", "findings"}
FINDING_REQUIRED = {"severity", "dimension", "quote", "note"}
FINDING_ALLOWED = FINDING_REQUIRED | {"subkind"}
SEVERITY_ENUM = {"BLOCKER", "MAJOR", "MINOR"}
DIMENSION_ENUM = {"冲突", "价值转变", "人物声音", "POV", "叙事组织", "文本质量", "灵感落点", "遮名-饱和度",
                  "范文语域"}
# 文本质量的 subkind 沿 story-review 的 ai_pattern 与 micro_language 两组（story-review/references/
# output-schema.md 为枚举权威）；写作简报按它解锁条目（scripts/brief_rules.yaml）
SUBKIND_ENUM = {
    "carrier_missing", "carrier_then_explain", "omission_violated", "narrator_self_corrects",
    "emotion_naming_under_face_loss", "monologue_padding", "subtext_translated_by_narrator",
    "planning_trace_leakage",
    "false_literary_diction", "sensory_mismatch", "abstract_judgment_without_action", "stock_speech_tag",
    "weak_character_expression",
}
COVERAGE_ALLOWED = {"requirement", "met", "evidence"}


def _validate_report_schema(report: dict, name: str) -> list[str]:
    """正向校验报告结构——畸形 findings/枚举漂移不得静默绕过业务断言。"""
    errors: list[str] = []
    unknown = set(report.keys()) - REPORT_ALLOWED
    if unknown:
        errors.append(f"{name}: 未知顶层字段 {sorted(unknown)}")
    if not (isinstance(report.get("story_sha256"), str) and report["story_sha256"].strip()):
        errors.append(f"{name}: story_sha256 缺失或非法")
    if report.get("status") not in {"PASS", "REVISE"}:
        errors.append(f"{name}: status={report.get('status')!r} 不在 PASS|REVISE")
    findings = report.get("findings")
    if findings is not None:
        if not isinstance(findings, list):
            errors.append(f"{name}: findings 必须是 list（当前 {type(findings).__name__}）")
        else:
            for i, f in enumerate(findings):
                if not isinstance(f, dict):
                    errors.append(f"{name}: findings[{i}] 必须是 mapping")
                    continue
                unknown = set(f.keys()) - FINDING_ALLOWED
                if unknown:
                    errors.append(f"{name}: findings[{i}] 未知字段 {sorted(unknown)}")
                for key in FINDING_REQUIRED:
                    if not (isinstance(f.get(key), str) and f[key].strip()):
                        errors.append(f"{name}: findings[{i}].{key} 缺失或非法")
                if f.get("subkind") is not None:
                    if f.get("dimension") != "文本质量":
                        errors.append(f"{name}: findings[{i}].subkind 只用于 文本质量")
                    elif f["subkind"] not in SUBKIND_ENUM:
                        errors.append(f"{name}: findings[{i}].subkind={f['subkind']!r} 不在枚举")
                if f.get("severity") not in SEVERITY_ENUM:
                    errors.append(f"{name}: findings[{i}].severity={f.get('severity')!r} 不在枚举（精确匹配）")
                if f.get("dimension") not in DIMENSION_ENUM:
                    errors.append(f"{name}: findings[{i}].dimension={f.get('dimension')!r} 不在枚举")
    coverage = report.get("requirements_coverage")
    if coverage is not None:
        if not isinstance(coverage, list):
            errors.append(f"{name}: requirements_coverage 必须是 list")
        else:
            for i, c in enumerate(coverage):
                if not isinstance(c, dict):
                    errors.append(f"{name}: requirements_coverage[{i}] 必须是 mapping")
                    continue
                unknown = set(c.keys()) - COVERAGE_ALLOWED
                if unknown:
                    errors.append(f"{name}: requirements_coverage[{i}] 未知字段 {sorted(unknown)}")
                if not (isinstance(c.get("requirement"), str) and c["requirement"].strip()):
                    errors.append(f"{name}: requirements_coverage[{i}].requirement 缺失或非法")
                if not isinstance(c.get("met"), bool):
                    errors.append(f"{name}: requirements_coverage[{i}].met 必须是 bool")
    return errors


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_review(review_dir: Path) -> Path | None:
    best: tuple[int, Path] | None = None
    if not review_dir.is_dir():
        return None
    for entry in review_dir.iterdir():
        match = REVIEW_NAME_RE.match(entry.name)
        if match:
            rn = int(match.group(1))
            if best is None or rn > best[0]:
                best = (rn, entry)
    return best[1] if best else None


def _fail(msg: str) -> int:
    print(f"[shortform-final-gate] FAIL: {msg}")
    return 1


def _summary_status(path: Path) -> str:
    """revision_summary.md 顶部的 status 行；读不到时返回"未写明"。"""
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:10]:
            m = re.match(r"\s*status:\s*(\w+)", line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "未写明"


def run_gate(work_dir: Path) -> int:
    failures = 0
    open_items: list[str] = []

    # ① 正文在场
    story = work_dir / "story.md"
    if not story.exists():
        return _fail(f"story.md 不存在：{story}")

    conception_path = work_dir / "pipeline" / "shortform" / "conception.yaml"
    try:
        conception = yaml.safe_load(conception_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"[shortform-final-gate] ERROR: conception.yaml 不可读取——{exc}")
        return 2
    if not isinstance(conception, dict):
        print("[shortform-final-gate] ERROR: conception.yaml 须为 mapping")
        return 2
    raw_requirements = conception.get("requirements", [])
    if not isinstance(raw_requirements, list) or any(
        not isinstance(item, str) or not item.strip() for item in raw_requirements
    ):
        print("[shortform-final-gate] ERROR: conception.requirements 须为非空字符串列表")
        return 2
    requirements = raw_requirements
    current_hash = _sha256(story)

    # ② 复用当前正文已有结果；缺失、旧版本或不可解析时运行检查。
    gate_path = work_dir / "pipeline" / "review" / "wholetext_gate.yaml"
    try:
        gate_report = yaml.safe_load(gate_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        gate_report = None
    current_gate = (
        isinstance(gate_report, dict)
        and gate_report.get("input_story_sha256") == current_hash
        and gate_report.get("verdict") in {"PASS", "REVIEW", "FAIL"}
    )
    if current_gate:
        if gate_report["verdict"] == "FAIL":
            open_items.append("wholetext gate 对当前正文 FAIL")
    else:
        wholetext = Path(__file__).resolve().parent / "wholetext_gate.py"
        result = subprocess.run(
            [sys.executable, str(wholetext), "--story", str(story), "--work-dir", str(work_dir)],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 2:
            print(f"[shortform-final-gate] ERROR: wholetext_gate 运行失败——{result.stderr.strip()}")
            return 2
        if result.returncode != 0:
            open_items.append(f"wholetext gate 对当前正文 FAIL——{result.stdout.strip()}")

    # ③ 最新审阅报告：格式、与正文的对应关系；status 与 BLOCKER 列出不拦
    review_dir = work_dir / "pipeline" / "shortform" / "review"
    report_path = _latest_review(review_dir)
    if report_path is None:
        failures += _fail(f"未找到 short_story_review.rN.yaml（应在 {review_dir}）")
    else:
        try:
            report = yaml.safe_load(report_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            return _fail(f"{report_path.name} YAML 解析失败——{exc}") or 1
        if not isinstance(report, dict):
            failures += _fail(f"{report_path.name} 顶层必须是 mapping")
            report = {}

        # schema 正向校验先于业务断言（畸形结构直接 fail，不进入 BLOCKER 判定）
        for err in _validate_report_schema(report, report_path.name):
            failures += _fail(err)

        source = f"{report_path.name}"
        if report.get("story_sha256") != current_hash:
            summary = review_dir / "revision_summary.md"
            if summary.is_file() and summary.stat().st_mtime >= report_path.stat().st_mtime:
                source = f"修订前的 {report_path.name}"
                open_items.append(f"正文按 {report_path.name} 修订过一次，修订后未复审；"
                                  f"revision_summary.md status: {_summary_status(summary)}")
            else:
                failures += _fail(
                    f"{report_path.name} 的 story_sha256 与当前 story.md 失配，且审阅之后没有修订记录"
                )
        status = report.get("status")
        findings = report.get("findings") if isinstance(report.get("findings"), list) else []
        blockers = [
            f for f in findings
            if isinstance(f, dict) and f.get("severity") == "BLOCKER"
        ]
        if blockers and status == "PASS":
            failures += _fail(f"{report_path.name} 含 {len(blockers)} 个 BLOCKER 却 status=PASS（含 BLOCKER 必 REVISE）")
        elif status != "PASS":
            open_items.append(f"{source} status={status}"
                              + (f"，含 {len(blockers)} 个 BLOCKER" if blockers else ""))

        # ④ requirements 一一对应核销；未满足的列出
        if requirements:
            coverage = report.get("requirements_coverage")
            if not isinstance(coverage, list):
                failures += _fail("conception.requirements 非空但报告缺 requirements_coverage")
            else:
                covered = [
                    c.get("requirement") for c in coverage if isinstance(c, dict)
                ]
                if covered != requirements:
                    failures += _fail(
                        "requirements_coverage 与 conception.requirements 序列不一致"
                        "（须一一对应：无缺项/增项/重复）"
                    )
                for i, c in enumerate(coverage):
                    if not isinstance(c, dict):
                        failures += _fail(f"requirements_coverage[{i}] 必须是 mapping")
                        continue
                    evidence = c.get("evidence")
                    if c.get("met") is not True:
                        open_items.append(f"{source} 记 requirement 未满足：{c.get('requirement')}")
                    elif not (isinstance(evidence, str) and evidence.strip()):
                        failures += _fail(f"requirements_coverage[{i}] 标 met=true 却没有 evidence")

    if failures:
        print(f"[shortform-final-gate] 交付包有缺陷（{failures} 项），补齐后再验")
        return 1
    if open_items:
        print("[shortform-final-gate] 可交付；以下未解决，写进交付说明，由作者决定是否再修一轮：")
        for item in open_items:
            print(f"- {item}")
        return 0
    print("[shortform-final-gate] PASS：交付包齐全，审阅 PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="短链终验 gate")
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    work_dir = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[shortform-final-gate] ERROR: work-dir 不存在：{work_dir}", file=sys.stderr)
        return 2
    return run_gate(work_dir)


if __name__ == "__main__":
    sys.exit(main())
