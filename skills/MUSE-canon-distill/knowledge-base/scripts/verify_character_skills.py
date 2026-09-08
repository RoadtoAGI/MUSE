"""校验单本小说所有已蒸馏角色 SKILL 的结构完整性。

用法：
    # 校验单本小说所有已蒸馏角色
    python verify_character_skills.py --novel-dir path/to/novels/书名

    # 校验单一角色（role-slug）
    python verify_character_skills.py --novel-dir path/to/novels/书名 --role role-slug

校验项（4 项硬约束，全部通过才视为合格）：
    1. parse_locators(SKILL.md) 数量
    2. count(key-dialogues.md sections) 数量
    3. build-meta.yaml.locator_count
    上述三处必须一致；
    4. character_map.json 包含 {build-meta.display_name: role_slug}

任一不一致 → stderr 列出 diff，进程退出码 1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from build_character_references import parse_locators  # noqa: E402
from verify_claims_factual import check_claims_writeback  # noqa: E402

# key-dialogues.md 的 section header 形如 `### scenes/scene_S12.md:L42-L58`
SECTION_HEADER_PATTERN = re.compile(r"^### [\w\-/.]+\.md:L\d+-L\d+", re.MULTILINE)

# 身份必备；其他参考章节按证据生成，已有六章节包继续兼容。
REQUIRED_SECTION_PREFIXES = ("身份",)
SECTION_PREFIXES = ("身份", "核心欲望", "性格真相", "声音框架", "边界", "弧光")

# 所有二级标题均结束前一节，避免借用其他章节的定位。
SKILL_SECTION_PATTERN = re.compile(
    r"^##[ \t]+([^\n]+)$",
    re.MULTILINE,
)

# 边界段 bullet 起始（行首 `- ` 或 `* `）
BULLET_START_PATTERN = re.compile(r"^[-*]\s", re.MULTILINE)

# SKILL.md frontmatter 必含字段（codex Finding 2）
REQUIRED_FRONTMATTER_KEYS = ("name", "description", "version", "allowed-tools")

# role-slug 格式：小写字母开头 + 小写字母/数字/连字符；不以连字符结尾；≥ 2 字符
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")

# frontmatter 块：文件起始 `---\n...\n---\n`
FRONTMATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\s*\n", re.DOTALL)


def count_dialogue_sections(file_path: Path) -> int:
    """统计 key-dialogues.md 中符合 `### {path}:L{a}-L{b}` 格式的 section 数。"""
    return len(SECTION_HEADER_PATTERN.findall(file_path.read_text(encoding="utf-8")))


def parse_sections(skill_content: str) -> dict[str, str]:
    """把 SKILL.md 解析为 `{章节前缀: 章节正文}` 字典。

    前缀用 SECTION_PREFIXES 的六个字符串之一。
    缺失章节在返回 dict 中 absent（不会返回空字符串）。
    """
    sections: dict[str, str] = {}
    matches = list(SKILL_SECTION_PATTERN.finditer(skill_content))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(skill_content)
        body = skill_content[body_start:body_end]
        for prefix in SECTION_PREFIXES:
            if title.startswith(prefix):
                sections[prefix] = body
                break
    return sections


def check_all_sections_have_locator(sections: dict[str, str]) -> list[str]:
    """身份必备，所有实际生成的参考章节均须有来源定位。"""
    issues: list[str] = []
    for prefix in REQUIRED_SECTION_PREFIXES:
        if prefix not in sections:
            issues.append(f"缺失必备章节：{prefix}")
    for prefix, body in sections.items():
        if not parse_locators(body):
            issues.append(f"章节 '{prefix}' 无原文引用定位")
    return issues


def check_boundary_each_bullet_has_locator(boundary_body: str) -> list[str]:
    """边界段每条 bullet（可跨多行）都必须有 locator。"""
    # 按行首的 bullet 标记切块
    # 每个块 = 从当前 `- ` / `* ` 到下一个 bullet 起始（或节末）
    bullets: list[str] = []
    current: list[str] = []
    for line in boundary_body.split("\n"):
        if BULLET_START_PATTERN.match(line):
            if current:
                bullets.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        bullets.append("\n".join(current))

    issues: list[str] = []
    for i, bullet in enumerate(bullets, 1):
        if not parse_locators(bullet):
            first_line = bullet.strip().split("\n")[0][:40]
            issues.append(f'边界第 {i} 条无 locator："{first_line}"')
    return issues


def collect_role_dirs(chars_dir: Path) -> list[Path]:
    """从 characters/ 下挑出"已蒸馏（或部分蒸馏）的角色目录"。

    判定：含以下任一角色产物即视为角色目录：
        - SKILL.md
        - build-meta.yaml
        - references/key-dialogues.md

    这样既能跳过旧分组目录（如射雕的"主角与镜像/"、"五绝/" 只含散 .md
    画像文件，不含上述任一），又能捕获**损坏的角色目录**（如 build-meta
    存在但 SKILL.md 缺失）——交给 verify_role() 准确报"缺什么"，避免静默
    跳过损坏状态。
    """
    role_artifact_paths = (
        Path("SKILL.md"),
        Path("build-meta.yaml"),
        Path("references") / "key-dialogues.md",
    )
    return sorted(
        d for d in chars_dir.iterdir()
        if d.is_dir() and any((d / p).is_file() for p in role_artifact_paths)
    )


def check_review_log(role_dir: Path) -> list[str]:
    """Layer 4 gate：review-log.yaml 中所有 severity: high 必须 resolved。

    - 文件不存在 → 视为 OK（没审过就没审过，不阻塞）
    - severity != high → 永远不 gate（只 warning 级）
    - severity == high AND status == resolved → OK
    - severity == high AND status ∈ {wontfix, dispute} 且有 resolution → OK
    - 否则 fail
    """
    log_file = role_dir / "review-log.yaml"
    if not log_file.exists():
        return []

    try:
        parsed = yaml.safe_load(log_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return [f"review-log.yaml 解析失败: {e}"]

    if parsed is None:
        return []  # 空文件视为 OK
    if not isinstance(parsed, dict):
        return [f"review-log.yaml 顶层必须是 mapping，实际为 {type(parsed).__name__}"]

    reviews = parsed.get("reviews", [])
    if not isinstance(reviews, list):
        return [f"review-log.yaml 的 reviews 字段必须是 list，实际为 {type(reviews).__name__}"]

    issues: list[str] = []
    for r in reviews:
        if not isinstance(r, dict):
            continue
        if r.get("severity") != "high":
            continue
        review_id = r.get("id", "?")
        status = r.get("status", "unresolved")
        resolution = r.get("resolution")
        if status == "resolved":
            continue
        if status in ("wontfix", "dispute") and resolution:
            continue
        # 其他情况（unresolved / wontfix 或 dispute 无 resolution）→ fail
        if status in ("wontfix", "dispute"):
            issues.append(
                f"review-log 条目 {review_id}（high/{status}）缺 resolution 说明"
            )
        else:
            issues.append(
                f"review-log 条目 {review_id}（high/{status}）未解决"
            )
    return issues


def check_claims(role_dir: Path) -> list[str]:
    """按同一契约检查已有 claims；未启用该附件时合法。"""
    return check_claims_writeback(role_dir)


def parse_frontmatter(skill_content: str) -> dict | None:
    """抽 SKILL.md 起始的 YAML frontmatter，解析失败或无 frontmatter 返回 None。"""
    m = FRONTMATTER_PATTERN.match(skill_content)
    if not m:
        return None
    try:
        parsed = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def check_frontmatter_complete(skill_content: str) -> list[str]:
    """codex Finding 2：frontmatter 必含 name/description/version/allowed-tools。"""
    fm = parse_frontmatter(skill_content)
    if fm is None:
        return ["SKILL.md 缺 YAML frontmatter（必须以 `---` 开头）"]
    missing = [k for k in REQUIRED_FRONTMATTER_KEYS if not fm.get(k)]
    if missing:
        return [f"SKILL.md frontmatter 缺字段: {missing}"]
    return []


def check_slug_format(role_slug: str) -> list[str]:
    """codex Finding 2：role-slug 必须是小写字母/数字/连字符格式。"""
    if not SLUG_PATTERN.match(role_slug):
        return [
            f"目录名 '{role_slug}' 不符合 role-slug 格式"
            f"（要求：小写字母开头 + 小写字母/数字/连字符 + 非连字符结尾 + ≥ 2 字符）"
        ]
    return []


def check_role_slug_consistency(
    role_dir_name: str,
    build_meta: dict | None,
    frontmatter: dict | None,
) -> list[str]:
    """codex Finding 2：build-meta.role_slug 与 frontmatter.name 都应等于 role_dir.name。"""
    issues: list[str] = []
    if build_meta is not None:
        meta_slug = build_meta.get("role_slug")
        if meta_slug and meta_slug != role_dir_name:
            issues.append(
                f"build-meta.role_slug='{meta_slug}' 与目录名 '{role_dir_name}' 不一致"
            )
    if frontmatter is not None:
        fm_name = frontmatter.get("name")
        if fm_name and fm_name != role_dir_name:
            issues.append(
                f"SKILL.md frontmatter.name='{fm_name}' 与目录名 '{role_dir_name}' 不一致"
            )
    return issues



def verify_role(
    novel_dir: Path | None,
    role_dir: Path,
    *,
    character_map_path: Path | None = None,
    checks: set[str] | None = None,
) -> list[str]:
    """对单角色目录执行校验，返回 issues 列表（空列表表示全通过）。

    两种调用方式：
    - 知识库模式：传 novel_dir，脚本自动在 `{novel_dir}/characters/character_map.json`
      找 map；character_map_path 可覆盖此默认位置。
    - 续写工作区模式（role-dir 模式）：novel_dir=None，必须显式传 role_dir；
      不传 character_map_path 则跳过 map 校验。

    checks 参数：选定要跑的子检查集合（见 V2 架构 §7.10 四层 gate）。
    - {"structure"}：仅 Layer 1（结构+character_map）
    - {"review_log"}：仅 Layer 4 审阅 gate
    - {"claims"}：仅 Layer 3 事实 gate
    - None（默认）：全开
    """
    ALL_CHECKS = {"structure", "review_log", "claims"}
    if checks is None:
        checks = ALL_CHECKS
    else:
        checks = set(checks) & ALL_CHECKS

    issues: list[str] = []

    # Layer 4：审阅 gate
    if "review_log" in checks:
        issues.extend(check_review_log(role_dir))

    # Layer 3：事实核对 gate（仅检查流程状态）
    if "claims" in checks:
        issues.extend(check_claims(role_dir))

    # Layer 1：结构检查（下方主逻辑）
    if "structure" not in checks:
        return issues

    skill_md = role_dir / "SKILL.md"
    key_dialogues = role_dir / "references" / "key-dialogues.md"
    build_meta = role_dir / "build-meta.yaml"
    # character_map 位置：显式 > novel_dir 默认 > 跳过
    if character_map_path is not None:
        map_file: Path | None = character_map_path
    elif novel_dir is not None:
        map_file = novel_dir / "characters" / "character_map.json"
    else:
        map_file = None

    # 0. 目录名符合 slug 格式（codex Finding 2）
    issues.extend(check_slug_format(role_dir.name))

    # 1. SKILL.md 必存
    if not skill_md.exists():
        issues.append(f"SKILL.md 不存在: {skill_md}")
        return issues  # 后续校验都依赖 SKILL.md

    skill_content = skill_md.read_text(encoding="utf-8")
    locators = parse_locators(skill_content)
    n_locators = len(locators)

    # 新硬约束 A：6 个必备章节每个至少 1 个 locator
    sections = parse_sections(skill_content)
    issues.extend(check_all_sections_have_locator(sections))

    # 新硬约束 B：边界段每条 bullet 都有 locator
    if "边界" in sections:
        issues.extend(check_boundary_each_bullet_has_locator(sections["边界"]))

    # 新硬约束 C：frontmatter 完整性（codex Finding 2）
    issues.extend(check_frontmatter_complete(skill_content))
    frontmatter = parse_frontmatter(skill_content)

    # 2. key-dialogues.md section 数 == n_locators
    if not key_dialogues.exists():
        issues.append(f"key-dialogues.md 不存在: {key_dialogues}")
    else:
        n_sections = count_dialogue_sections(key_dialogues)
        if n_locators != n_sections:
            issues.append(
                f"locator 数 ({n_locators}) != key-dialogues section 数 ({n_sections})"
            )

    # 3. build-meta.yaml.locator_count == n_locators
    meta: dict = {}
    if not build_meta.exists():
        issues.append(f"build-meta.yaml 不存在: {build_meta}")
    else:
        try:
            parsed = yaml.safe_load(build_meta.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            issues.append(f"build-meta.yaml 解析失败: {e}")
        else:
            if parsed is None:
                meta = {}  # 空文件视为空 dict
            elif not isinstance(parsed, dict):
                issues.append(
                    f"build-meta.yaml 顶层必须是 mapping，实际为 {type(parsed).__name__}"
                )
            else:
                meta = parsed
                n_meta = meta.get("locator_count")
                if n_meta != n_locators:
                    issues.append(
                        f"locator 数 ({n_locators}) != build-meta.locator_count ({n_meta})"
                    )

    # 新硬约束 D：role-slug 一致性（目录名 == build-meta.role_slug == frontmatter.name）
    issues.extend(check_role_slug_consistency(
        role_dir.name, meta if meta else None, frontmatter
    ))

    # 4. character_map.json 包含 {display_name: role_slug}
    # map_file is None 表示续写工作区模式下未传 map → 跳过 map 校验
    role_slug = role_dir.name
    if map_file is None:
        pass  # 显式跳过
    elif not map_file.exists():
        issues.append(f"character_map.json 不存在: {map_file}")
    else:
        try:
            mapping = json.loads(map_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            issues.append(f"character_map.json 解析失败: {e}")
        else:
            if not isinstance(mapping, dict):
                issues.append(
                    f"character_map.json 顶层必须是 object，实际为 {type(mapping).__name__}"
                )
            else:
                display_name = meta.get("display_name") if meta else None
                if not display_name:
                    issues.append(
                        f"build-meta.yaml 未定义 display_name，无法核对 character_map"
                    )
                elif mapping.get(display_name) != role_slug:
                    issues.append(
                        f"character_map.json 缺映射或映射错: 期望 '{display_name}' → '{role_slug}'，"
                        f"实际 '{display_name}' → '{mapping.get(display_name)}'"
                    )

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "校验已蒸馏角色 SKILL 的结构完整性。\n"
            "两种模式：\n"
            "  A) 知识库模式：--novel-dir（校验整本书的 characters/）\n"
            "  B) 续写工作区模式：--role-dir（直接指向单角色目录，无需知识库结构）"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--novel-dir",
        type=Path,
        help="知识库小说根目录（内含 characters/ 子目录）",
    )
    mode.add_argument(
        "--role-dir",
        type=Path,
        help="单角色目录（续写工作区模式——bypass 知识库目录结构）",
    )
    parser.add_argument(
        "--role",
        help="知识库模式下只校验单角色（role-slug）；role-dir 模式下此参数无效",
    )
    parser.add_argument(
        "--character-map",
        type=Path,
        help=(
            "显式指定 character_map.json 位置。\n"
            "  - 知识库模式：默认 {novel-dir}/characters/character_map.json\n"
            "  - 续写工作区模式：不传则跳过 map 校验"
        ),
    )
    # 四层 gate 子检查开关（见 V2 架构 §7.10）
    parser.add_argument(
        "--check-structure",
        action="store_true",
        help="只跑 Layer 1 结构检查（locator 完整性 / 章节 / 边界 bullet / character_map）",
    )
    parser.add_argument(
        "--check-review-log",
        action="store_true",
        help="只跑 Layer 4 审阅 gate（review-log.yaml 中 severity: high 必须 resolved）",
    )
    parser.add_argument(
        "--check-claims",
        action="store_true",
        help="检查已有 claims 的来源记录与未完成核对；不要求全角色生成 claims",
    )
    args = parser.parse_args()

    # 解析 checks 集合：若显式指定了任何 --check-* flag，则只跑指定的；否则默认全开
    explicit_checks = set()
    if args.check_structure:
        explicit_checks.add("structure")
    if args.check_review_log:
        explicit_checks.add("review_log")
    if args.check_claims:
        explicit_checks.add("claims")
    checks: set[str] | None = explicit_checks if explicit_checks else None

    if args.role_dir is not None:
        # 模式 B：续写工作区
        if not args.role_dir.is_dir():
            print(f"ERROR: --role-dir 不是有效目录: {args.role_dir}", file=sys.stderr)
            sys.exit(1)
        if args.role is not None:
            print("WARN: --role-dir 模式下 --role 参数被忽略", file=sys.stderr)
        role_dirs = [args.role_dir]
        novel_dir: Path | None = None
    else:
        # 模式 A：知识库
        chars_dir = args.novel_dir / "characters"
        if not chars_dir.exists():
            print(f"ERROR: characters/ 目录不存在: {chars_dir}", file=sys.stderr)
            sys.exit(1)

        if args.role:
            role_dirs = [chars_dir / args.role]
            if not role_dirs[0].is_dir():
                print(f"ERROR: 角色目录不存在: {role_dirs[0]}", file=sys.stderr)
                sys.exit(1)
        else:
            role_dirs = collect_role_dirs(chars_dir)

        if not role_dirs:
            print(
                f"未发现已蒸馏角色（characters/ 下无含 SKILL.md 的子目录）: {chars_dir}",
                file=sys.stderr,
            )
            sys.exit(1)
        novel_dir = args.novel_dir

    all_passed = True

    for role_dir in role_dirs:
        issues = verify_role(
            novel_dir=novel_dir,
            role_dir=role_dir,
            character_map_path=args.character_map,
            checks=checks,
        )
        if issues:
            all_passed = False
            print(f"❌ {role_dir.name}", file=sys.stderr)
            for i in issues:
                print(f"  - {i}", file=sys.stderr)
        else:
            print(f"✅ {role_dir.name}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
