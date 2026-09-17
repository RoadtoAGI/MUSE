#!/usr/bin/env python3
"""package_lint.py — 静态防回潮扫，git pre-commit 调用或手动跑。

检查项：
- 无 <claude-mem-context> 残留
- 无冻结术语 character-performance / use_actors / phase4_spine.yaml
- 无协议版本 / 历史 review / 路线图注记（Rn+N / R-x.y / R-N F-N / @x.y.z / codex finding /
  Plan-Task / 后续版本 / 当前未实施 / V-N 演进 / 截图诊断 等）
  扫描域 = 四包 runtime skill 文档（MUSE-writing|MUSE-canon-distill|MUSE-serial-writing|
  MUSE-serial-distill 的 skills/ + agents/ 下 .md/.yaml）；knowledge-base/（生成态角色 skill）、
  scripts/.py、hooks/.sh 不在协议注记域内。
- (--strict only) 无 __pycache__ / .pytest_cache 物理目录残留（pytest 必然产，仅 publish 前扫）
- 原创与连载同时存在时，已统一的工坊与世界观参考保持同文；各包特化入口独立维护

输出 WARN 到 stderr，exit 0（warning only，不阻断 commit）。
若需要 hard fail，传 --strict。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

FROZEN_TERMS = [
    "character-performance",
    "use_actors",
    "phase4_spine.yaml",
]

CONTEXT_TAG_PATTERN = re.compile(r"<claude-mem-context>")

# 协议版本 / 历史 review / 路线图注记——开发痕迹，不该进 runtime skill 文档。
# 正则按仓库实际注记形精确锚定：避开 Phase 范围 P0-7（单位数）、裸优先级 P0/P1、
# schema 日期示例（completed_at: YYYY-MM-DD）、合法文档名/示例标识符——无白名单豁免，
# 误伤靠正则收窄而非放行。
PROTOCOL_NOTE_PATTERNS = [
    (re.compile(r"\bv0\.\d+\b"), "协议版本注记 v0.x"),
    (re.compile(r"\bStep \d+\.x 后会\b"), "未来 Step 承诺"),
    (re.compile(r"\b未来 batch\b"), "未来 batch 承诺"),
    (re.compile(r"\bPlan \d+ Task \d+\b"), "Plan/Task 引用注记"),
    (re.compile(r"\bbrief r\d+\b"), "brief review 历史注记"),
    (re.compile(r"\bRn\+\d+"), "开发轮注记 Rn+N"),
    (re.compile(r"\bR\d+\.\d+"), "开发轮注记 R-x.y"),
    (re.compile(r"\bR\d+ F\d+\b"), "Codex 轮次 finding 注记 R-N F-N"),
    (re.compile(r"\bR\d+ #\d+"), "开发轮 issue 注记 R-N #N"),
    (re.compile(r"\b[Rr]\d+ ?(?:新增|引入|改造|升级|起强制|衍生模式|沿用|阶段|渐进|ship|已 ship)"),
     "开发轮注记 R-N + 动作"),
    (re.compile(r"\b[Rr]\d+ Step \d"), "开发轮注记 r-N Step"),
    (re.compile(r"[Cc]odex (?:R\d+ )?[Ff]inding ?\d*"), "Codex 审查 finding 注记"),
    (re.compile(r"Plan §\d|来自 Plan\b|plan 附录|\bpost-plan\b|本 Task\b"), "Plan/Task 引用注记"),
    (re.compile(r"\bP\d-\d{2,}"), "finding/backlog ID 注记"),
    (re.compile(r"\bP\d\.b\d"), "finding/backlog ID 注记"),
    (re.compile(r"@\d+\.\d+\.\d+"), "版本号注记 @x.y.z"),
    (re.compile(r"后续版本|当前未实施|已 backlog|未来增强|后续(?:可)?升级"), "路线图残留措辞"),
    (re.compile(r"\bV\d+ (?:曾|改为|架构)"), "版本演进注记 V-N"),
    (re.compile(r"plan ship|截图诊断|历史排查记录"), "开发态诊断/ship 注记"),
    # 开发痕迹混入执行热路径——历史变更解释 / 事故记录 / 维护编号溯源。
    # skill 正文给执行者看：只写当场需要的时机/动作/判据/依据；变更动机与事故案例归 docs CHANGELOG。
    (re.compile(r"\bS0-\d+ ?(?:新增|同源|起)"), "维护编号溯源注记 S0-xx"),
    (re.compile(r"为什么改默认|为何改默认|为什么撤销"), "历史变更解释混入执行段"),
    (re.compile(r"实战曾|曾出现.{0,10}(?:卡死|手动终止)"), "事故记录混入执行段"),
    (re.compile(r"来自旧版本|旧版本创作|（[^）]*早期版本）"), "旧版本出处注记"),
    # 案例来源标识本身合法；只提示把维护任务写进运行指令的形式。
    (re.compile(r"(?:回归任务|测试任务|待验证用例)[：: ]*(?:query[_ ]?\d+|writing-bench ?\d+)", re.I),
     "开发测试任务混入执行段"),
    (re.compile(r"实测中|当前阶段：|留 backlog|未来若引入"), "事故叙述/阶段路线图措辞"),
]

CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache"}

# 完整定义由原创包维护，两包各自携带可独立读取的副本。
# 仅包含已经逐机制整合的整文件；SKILL.md 与编排保留包内输入合同。
SHARED_REFERENCE_PAIRS = tuple(
    (path, path) for path in (
        "prose-craft/references/novel-craft-patterns.md",
        "prose-craft/references/ai-cliche-patterns.md",
        "prose-craft/references/observed-action-cases.md",
        "prose-craft/references/forbidden_migration_patterns.yaml",
        "dialogue-craft/references/dialogue-rules.md",
        "dialogue-craft/references/speech-attribution-patterns.md",
        "dialogue-craft/references/subtext-theory.md",
    )
) + tuple(
    (f"phase1-world-building/references/{path}", f"world-bible-design/references/{path}")
    for path in (
        "mckee-setting.md",
        "genre-worldbuilding/README.md",
        "genre-worldbuilding/apocalypse.md",
        "genre-worldbuilding/mystery.md",
        "genre-worldbuilding/palace-intrigue.md",
        "genre-worldbuilding/romance.md",
        "genre-worldbuilding/scifi.md",
        "genre-worldbuilding/wuxia.md",
        "genre-worldbuilding/xianxia.md",
    )
)


def scan_shared_references(root: Path) -> int:
    """检查已声明共享的参考副本；独立安装单包时没有跨包依赖。"""
    writing = root / "skills/MUSE-writing/skills"
    serial = root / "skills/MUSE-serial-writing/skills"
    if not writing.is_dir() or not serial.is_dir():
        return 0
    warn_count = 0
    for writing_rel, serial_rel in SHARED_REFERENCE_PAIRS:
        source, peer = writing / writing_rel, serial / serial_rel
        if not source.is_file() or not peer.is_file():
            reason = "共享参考缺件"
        elif source.read_text(encoding="utf-8") != peer.read_text(encoding="utf-8"):
            reason = "共享参考分歧，按机制核对并同步"
        else:
            continue
        print(f"[package-lint] WARN: {source.relative_to(root)} ↔ {peer.relative_to(root)}: {reason}",
              file=sys.stderr)
        warn_count += 1
    return warn_count

# 协议注记扫描域：四包手维护的 runtime skill 文档（model 在生成时实际加载的 prompt 文本）。
# 排除 knowledge-base/（生成态角色 skill）、scripts/.py 与 hooks/.sh（代码出处注释非 prompt）。
_SKILL_DOC_PREFIXES = (
    "skills/MUSE-writing/skills/",
    "skills/MUSE-writing/agents/",
    "skills/MUSE-canon-distill/skills/",
    "skills/MUSE-canon-distill/agents/",
    "skills/MUSE-serial-writing/skills/",
    "skills/MUSE-serial-writing/agents/",
    "skills/MUSE-serial-distill/skills/",
    "skills/MUSE-serial-distill/agents/",
)


def is_runtime_skill_doc(rel: Path) -> bool:
    if rel.suffix not in (".md", ".yaml"):
        return False
    posix = rel.as_posix()
    return any(posix.startswith(p) for p in _SKILL_DOC_PREFIXES)


def scan_cache_dirs(root: Path) -> int:
    """物理目录扫：MUSE plugin 子树内 __pycache__ / .pytest_cache 残留。

    扫描范围限定 skills/MUSE-writing/ 子树——repos/ 评测副本、其他 .claude/skills 子包不归 MUSE 治理。
    """
    warn_count = 0
    for scope_name in ("MUSE-writing",):
        scope = root / "skills" / scope_name
        if not scope.is_dir():
            continue
        for path in scope.rglob("*"):
            if not path.is_dir():
                continue
            if path.name not in CACHE_DIR_NAMES:
                continue
            rel = path.relative_to(root)
            print(f"[package-lint] WARN: {rel}/: 缓存目录残留，请清理", file=sys.stderr)
            warn_count += 1
    return warn_count


def scan_text_files(root: Path, *, strict: bool = False) -> int:
    # cache 扫仅在 strict 模式触发——pytest / 开发态必然产，日常 commit 不该被打扰；
    # 真实价值场景是 plugin publish 前快照检查
    warn_count = scan_shared_references(root)
    if strict:
        warn_count += scan_cache_dirs(root)

    target_globs = [
        "skills/MUSE-writing/agents/*.md",
        "skills/MUSE-writing/skills/**/*.md",
        "skills/MUSE-writing/skills/**/*.yaml",
        "skills/MUSE-writing/hooks/**/*.sh",
        "skills/MUSE-writing/scripts/**/*.py",
        "skills/MUSE-canon-distill/skills/**/*.md",
        "skills/MUSE-canon-distill/skills/**/*.yaml",
        "skills/MUSE-canon-distill/agents/*.md",
        "skills/MUSE-serial-writing/agents/*.md",
        "skills/MUSE-serial-writing/skills/**/*.md",
        "skills/MUSE-serial-writing/skills/**/*.yaml",
        "skills/MUSE-serial-distill/agents/*.md",
        "skills/MUSE-serial-distill/skills/**/*.md",
        "skills/MUSE-serial-distill/skills/**/*.yaml",
        ".claude/agents/*.md",
        ".claude/skills/**/*.md",
        ".claude/CLAUDE.md",
    ]
    files = set()
    for g in target_globs:
        files.update(root.glob(g))

    for f in files:
        rel = f.relative_to(root)
        # lint 脚本自身豁免：FROZEN_TERMS 字面量、CONTEXT_TAG_PATTERN 都会扫到自身
        if "package_lint" in str(rel):
            continue

        # decision-log 档案不入 runtime references（CLAUDE.md 执行者视角红线：决策起源归 docs CHANGELOG）
        if f.name == "decision-log.md":
            print(f"[package-lint] WARN: {rel}: decision-log 档案应迁 docs CHANGELOG，不入 skill references",
                  file=sys.stderr)
            warn_count += 1
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # claude-mem-context 残留
        if CONTEXT_TAG_PATTERN.search(text):
            print(f"[package-lint] WARN: {rel}: 含 <claude-mem-context> 残留", file=sys.stderr)
            warn_count += 1

        # 冻结术语（扫描面已收紧到 runtime 热路径，路径白名单不再必要）
        for term in FROZEN_TERMS:
            for m in re.finditer(re.escape(term), text):
                line_no = text[: m.start()].count("\n") + 1
                print(f"[package-lint] WARN: {rel}:{line_no}: 冻结术语 `{term}`", file=sys.stderr)
                warn_count += 1

        # 协议版本 / 历史 review / 路线图注记
        # 扫描域 = 四包 runtime skill 文档（skills/ + agents/ 下 .md/.yaml）；
        # knowledge-base/（生成态角色 skill）、scripts/.py、hooks/.sh、.claude/ 不在域内
        if is_runtime_skill_doc(rel):
            for pattern, label in PROTOCOL_NOTE_PATTERNS:
                for m in pattern.finditer(text):
                    line_no = text[: m.start()].count("\n") + 1
                    print(f"[package-lint] WARN: {rel}:{line_no}: {label} `{m.group()}`", file=sys.stderr)
                    warn_count += 1

    print(f"[package-lint] 总 WARN={warn_count}", file=sys.stderr)
    if strict and warn_count > 0:
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--strict", action="store_true", help="WARN 时 exit 1")
    args = parser.parse_args()
    return scan_text_files(Path(args.root), strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
