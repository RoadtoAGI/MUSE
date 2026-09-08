#!/usr/bin/env python3
"""verify_shortform_review_complete.py — 短链终验 gate（交付前最后一道机器闸）。

五断言（任一不过 → exit 1 = 不得交付）：
  ① story.md 在场
  ② wholetext_gate 报告与当前正文匹配时复用，否则运行现有检查
  ③ 最新 pipeline/shortform/review/short_story_review.rN.yaml 的 story_sha256
     == 当前 story.md 哈希（修订后未复审即交付在此 fail）
  ④ 该报告 status=PASS 且 findings 无 BLOCKER（含 BLOCKER 必 REVISE 的一致性也在此断言）
  ⑤ conception.requirements 非空时，requirements_coverage 与其一一对应
     （序列完全一致，无缺项/增项/重复）且逐项 met=true、evidence 非空

用法:
    python3 verify_shortform_review_complete.py --work-dir <run 目录>

退出码: 0=放行; 1=终验不过; 2=用法/环境错误
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
FINDING_ALLOWED = {"severity", "dimension", "quote", "note"}
SEVERITY_ENUM = {"BLOCKER", "MAJOR", "MINOR"}
DIMENSION_ENUM = {"冲突", "价值转变", "人物声音", "POV", "叙事组织", "文本质量", "灵感落点", "遮名-饱和度"}
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
                for key in FINDING_ALLOWED:
                    if not (isinstance(f.get(key), str) and f[key].strip()):
                        errors.append(f"{name}: findings[{i}].{key} 缺失或非法")
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


def run_gate(work_dir: Path) -> int:
    failures = 0

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
            failures += _fail("wholetext gate 对当前正文 FAIL")
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
            failures += _fail(f"wholetext gate 对当前正文 FAIL——{result.stdout.strip()}")

    # ③④ 最新审阅报告：hash 对齐 + status/BLOCKER
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

        if report.get("story_sha256") != current_hash:
            failures += _fail(
                f"{report_path.name} 的 story_sha256 与当前 story.md 失配——修订后未复审即交付"
            )
        status = report.get("status")
        findings = report.get("findings") if isinstance(report.get("findings"), list) else []
        blockers = [
            f for f in findings
            if isinstance(f, dict) and f.get("severity") == "BLOCKER"
        ]
        if status != "PASS":
            failures += _fail(f"{report_path.name} status={status!r}（须 PASS 才可交付）")
        if blockers:
            failures += _fail(
                f"{report_path.name} 含 {len(blockers)} 个 BLOCKER finding"
                + ("（且 status=PASS——违反含 BLOCKER 必 REVISE 的一致性）" if status == "PASS" else "")
            )

        # ⑤ requirements 一一对应核销
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
                    if c.get("met") is not True:
                        failures += _fail(f"requirements_coverage[{i}] 未核销（met != true）")
                    evidence = c.get("evidence")
                    if not (isinstance(evidence, str) and evidence.strip()):
                        failures += _fail(f"requirements_coverage[{i}] evidence 为空")

    if failures:
        print(f"[shortform-final-gate] 终验不过（{failures} 项），不得交付")
        return 1
    print("[shortform-final-gate] PASS：全部断言通过，放行交付")
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
