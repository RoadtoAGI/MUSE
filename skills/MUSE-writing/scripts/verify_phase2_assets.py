#!/usr/bin/env python3
"""verify_phase2_assets.py — phase2 出口验证

用法:
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_phase2_assets.py <pipeline_dir>

退出码:
  0 — 必建集全部建成 + supporting_cast 全部有判定 + build-report 不幻觉
      + 每个已建 slug 4 产物完整 + provenance/adapter sha/结构不变量全过
  非 0 — 至少一项失败（stdout 报具体失败原因）

校验维度（回应 codex r2 CRITICAL #1 + r3 CRITICAL #1 + r3 IMPORTANT #3）:
  1. phase2_character.yaml 真实 schema：protagonist/deuteragonist/antagonist/supporting_cast 用 name 不用 slug
  2. build-report.md 是 name→slug 映射桥梁（character-persona builder 产出）
  3. 必建集（protagonist + deuteragonist + antagonist）name 必须出现在 build-report 已构建表
  4. supporting_cast 每个 name 必须在 build-report 已构建或未构建任一表（builder 必须做判定）
  5. build-report 未构建条目必须有 skip_reason
  6. build-report 不允许幻觉构建（已构建 name 必须在 phase2 出现）
  7. 每个已构建 slug 4 产物完整：SKILL.md / state.md / build-meta.yaml /
     pipeline/characters/{display_name}.md
  8. build-meta provenance + adapter sha 一致性
  9. SKILL.md 章节白名单（从 skill-template.md 派生，不硬编码）

不做计数门槛检查（描述性质量信号由 reviewer 判断）。
"""
import hashlib, re, sys, yaml
from pathlib import Path

CORE_META_FIELDS = [
    "generated_by", "character_slug", "character_display_name",
    "input_sources", "adapter_path", "adapter_sha256",
]

# 章节白名单从 skill-template.md 运行时派生——禁止硬编码
# 模板路径相对本脚本（脚本与 skills/ 同处 plugin 根下）
DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills/character-persona/references/skill-template.md"
)

def parse_template_sections(template_path: Path):
    """解析 skill-template.md，返回 (required_set, allowed_set)

    每个顶级 ## 章节允许标注 <!-- required --> 或 <!-- optional -->，
    标注可在两种位置：
      1. 同行：`## 身份 <!-- required -->`
      2. 下一行：`## 身份` 后跟独立一行 `<!-- required -->`（T3 落地实际格式）
    """
    required, allowed = set(), set()
    if not template_path.exists():
        raise FileNotFoundError(f"template not found: {template_path}")
    lines = template_path.read_text().splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        # 同行注释（plan 原版语义）
        head, _, tail = line.partition("<!--")
        name = head.removeprefix("## ").strip()
        marker_line = tail.split("-->")[0].strip().lower()
        # 下一行注释（T3 落地实际格式）
        if not marker_line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line.startswith("<!--") and next_line.endswith("-->"):
                marker_line = next_line[4:-3].strip().lower()
        if marker_line == "required":
            required.add(name); allowed.add(name)
        elif marker_line == "optional":
            allowed.add(name)
    if not required:
        raise ValueError(
            f"template {template_path} has no <!-- required --> sections; "
            f"refusing to fall back to hardcoded defaults"
        )
    return required, allowed

def parse_phase2_yaml(pipeline: Path):
    """读 phase2_character.yaml；返回 {required_names, supporting_names, all_phase2_names}
    真实 schema 用 name 不用 slug（含 deuteragonist；codex r3 CRITICAL #1）。"""
    p = pipeline / "pipeline" / "phase2_character.yaml"
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text()) or {}

    def names_of(v):
        if isinstance(v, dict) and v.get("name"):
            return [v["name"]]
        if isinstance(v, list):
            return [item["name"] for item in v if isinstance(item, dict) and item.get("name")]
        return []

    required = []
    for key in ("protagonist", "deuteragonist", "antagonist"):
        required += names_of(data.get(key))
    supporting = [
        c["name"] for c in (data.get("supporting_cast") or [])
        if isinstance(c, dict) and c.get("name")
    ]
    return {
        "required_names": required,
        "supporting_names": supporting,
        "all_phase2_names": set(required + supporting),
    }

def verify_canon_archetype(phase2: dict, ledger: dict) -> list:
    """校验 phase2 各角色的 canon_archetype 字段。

    Returns: findings 列表，每个 finding 含 code / message / role_slug。
    """
    findings = []
    cards = ledger.get("inspirations") or ledger.get("inspiration_ledger") or []
    ledger_index = {
        c.get("id"): c for c in cards
        if isinstance(c, dict) and c.get("id")
    }

    for role_slug in ("protagonist", "deuteragonist", "antagonist"):
        role = phase2.get(role_slug)
        if not isinstance(role, dict):
            continue
        archetypes = role.get("canon_archetype")
        if not archetypes:
            continue

        for archetype in archetypes:
            if archetype.get("weight") == "secondary" and not archetype.get("merge_boundary"):
                findings.append({
                    "code": "canon_archetype_secondary_missing_merge_boundary",
                    "message": (
                        f"{role_slug} canon_archetype {archetype.get('id')} "
                        "weight=secondary 但缺 merge_boundary"
                    ),
                    "role_slug": role_slug,
                })

        for archetype in archetypes:
            ins_id = archetype.get("id")
            if ins_id not in ledger_index:
                findings.append({
                    "code": "canon_archetype_ledger_id_missing",
                    "message": f"{role_slug} canon_archetype 引用 {ins_id} 在 ledger 中找不到",
                    "role_slug": role_slug,
                })
                continue
            card = ledger_index[ins_id]
            if card.get("type") != "archetype":
                findings.append({
                    "code": "canon_archetype_ledger_type_mismatch",
                    "message": (
                        f"{role_slug} canon_archetype 引用 {ins_id} 在 ledger 中 "
                        f"type={card.get('type')}，应为 archetype"
                    ),
                    "role_slug": role_slug,
                })
            if card.get("status") not in ("accepted", "bound"):
                findings.append({
                    "code": "canon_archetype_ledger_status_invalid",
                    "message": (
                        f"{role_slug} canon_archetype 引用 {ins_id} 在 ledger 中 "
                        f"status={card.get('status')}，必须为 accepted 或 bound"
                    ),
                    "role_slug": role_slug,
                })
            if card.get("archetype_target_slug") != role_slug:
                findings.append({
                    "code": "canon_archetype_target_slug_mismatch",
                    "message": (
                        f"{role_slug} canon_archetype 引用 {ins_id} 的 "
                        f"archetype_target_slug={card.get('archetype_target_slug')}，"
                        f"应为 {role_slug}"
                    ),
                    "role_slug": role_slug,
                })

    return findings

def _parse_md_table(body: str) -> list[dict]:
    """按表头解析 markdown 表：返回 [dict(列名小写 -> cell)]；跳过分隔线行。"""
    rows = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("|")]
    if not rows:
        return []

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    header = [h.lower() for h in cells(rows[0])]
    out = []
    for line in rows[1:]:
        cs = cells(line)
        if all(c.replace("-", "").replace(":", "") == "" for c in cs):
            continue  # 表头分隔线
        out.append({header[i]: cs[i] for i in range(min(len(header), len(cs)))})
    return out

def parse_build_report(pipeline: Path):
    """解析 build-report.md（表头驱动：已构建至少取 name/slug，未构建取 name/skip_reason，其余列忽略）
    返回 {built: [(name, slug, reason)], unbuilt: [(name, skip_reason)]}"""
    p = pipeline / "pipeline" / "story-character-skills" / "build-report.md"
    if not p.exists():
        return None
    text = p.read_text()
    sections = re.split(r"^##\s+", text, flags=re.M)
    built, unbuilt = [], []
    for sec in sections:
        head = sec.split("\n", 1)[0].strip()
        body = sec[len(head):]
        rows = _parse_md_table(body)
        if head.startswith("已构建"):
            for r in rows:
                if r.get("name") and r.get("slug"):
                    built.append((r["name"], r["slug"], r.get("reason", "")))
        elif head.startswith("未构建"):
            for r in rows:
                if not r.get("name"):
                    continue
                unbuilt.append((r["name"], r.get("skip_reason") or r.get("reason") or ""))
    return {"built": built, "unbuilt": unbuilt}

def check_skill(pipeline: Path, slug: str, display_name: str,
                required_sections: set, allowed_sections: set):
    errors = []
    skill_dir = pipeline / "pipeline" / "story-character-skills" / ".claude" / "skills" / slug

    # 4 产物完整性
    skill_md = skill_dir / "SKILL.md"
    state_md = skill_dir / "state.md"
    meta_path = skill_dir / "build-meta.yaml"
    adapter_path = pipeline / "pipeline" / "characters" / f"{display_name}.md"

    for label, p in [("SKILL.md", skill_md), ("state.md", state_md),
                     ("build-meta.yaml", meta_path), (f"adapter ({adapter_path.name})", adapter_path)]:
        if not p.exists():
            errors.append(f"{slug}: missing 4-artifact item '{label}' at {p}")
    if errors:
        return errors  # 缺产物时跳过下游字段校验

    try:
        meta = yaml.safe_load(meta_path.read_text())
    except yaml.YAMLError as e:
        errors.append(f"{slug}: build-meta.yaml not valid YAML — {e}")
        return errors

    for f in CORE_META_FIELDS:
        if f not in meta or meta[f] in (None, ""):
            errors.append(f"{slug}: build-meta.yaml missing field '{f}'")
    if meta.get("generated_by") != "character-persona":
        errors.append(
            f"{slug}: generated_by={meta.get('generated_by')!r} "
            f"(expected 'character-persona' — placeholder forbidden)"
        )

    # adapter 一致性
    if "adapter_sha256" in meta:
        actual_adapter_sha = hashlib.sha256(adapter_path.read_bytes()).hexdigest()[:16]
        if meta["adapter_sha256"] != actual_adapter_sha:
            errors.append(
                f"{slug}: build-meta.adapter_sha256={meta['adapter_sha256']} "
                f"!= actual adapter sha={actual_adapter_sha} "
                f"(adapter modified after build)"
            )

    # 章节白名单
    sections = [
        line[3:].split("<!--")[0].strip()
        for line in skill_md.read_text().splitlines()
        if line.startswith("## ")
    ]
    section_set = set(sections)
    missing = required_sections - section_set
    if missing:
        errors.append(f"{slug}: SKILL.md missing required sections {sorted(missing)}")
    extra = section_set - allowed_sections
    if extra:
        errors.append(
            f"{slug}: SKILL.md has sections not in template whitelist {sorted(extra)} "
            f"(template={DEFAULT_TEMPLATE_PATH.name})"
        )
    return errors

def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("pipeline_dir", type=Path)
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_PATH)
    args = ap.parse_args()
    required_sections, allowed_sections = parse_template_sections(args.template)
    pipeline = args.pipeline_dir

    phase2 = parse_phase2_yaml(pipeline)
    if phase2 is None:
        print(f"FAIL: phase2_character.yaml not found under {pipeline}/pipeline/", file=sys.stderr)
        sys.exit(1)

    report = parse_build_report(pipeline)
    if report is None:
        print(f"FAIL: build-report.md not found under {pipeline}/pipeline/story-character-skills/",
              file=sys.stderr)
        sys.exit(1)

    all_errors = []

    ledger_path = pipeline / "pipeline" / "inspiration_ledger.yaml"
    phase2_path = pipeline / "pipeline" / "phase2_character.yaml"
    try:
        phase2_raw = yaml.safe_load(phase2_path.read_text()) or {}
        ledger_data = (yaml.safe_load(ledger_path.read_text()) or {}) if ledger_path.exists() else {}
        if not isinstance(ledger_data, dict):
            raise ValueError("inspiration_ledger.yaml must be a mapping with an inspirations list")
    except (yaml.YAMLError, ValueError) as e:
        all_errors.append(f"canon_archetype: invalid input — {e}")
    else:
        for finding in verify_canon_archetype(phase2_raw, ledger_data):
            all_errors.append(
                f"canon_archetype: [{finding['code']}] {finding['message']}"
            )

    # name → slug 映射（来自 build-report 已构建表）
    name_to_slug = {n: s for n, s, _ in report["built"]}
    built_names = set(name_to_slug.keys())
    unbuilt_names = {n for n, _ in report["unbuilt"]}

    # 校验 1: 必建集 name 必须出现在 build-report 已构建表
    for name in phase2["required_names"]:
        if name not in built_names:
            all_errors.append(
                f"required role '{name}' (protagonist/deuteragonist/antagonist) "
                f"not in build-report '已构建' (codex r3 CRITICAL #1)"
            )

    # 校验 2: supporting_cast 每个 name 必须在已构建或未构建任一表
    for name in phase2["supporting_names"]:
        if name not in built_names and name not in unbuilt_names:
            all_errors.append(
                f"supporting_cast '{name}' 缺判定: 既不在 build-report 已构建也不在未构建"
            )

    # 校验 3: 未构建条目必须有 skip_reason
    for name, reason in report["unbuilt"]:
        if not reason:
            all_errors.append(f"build-report 未构建项 '{name}' 缺 skip_reason")

    # 校验 4: 已构建表不允许幻觉构建（name 必须在 phase2_character.yaml）
    for name in built_names:
        if name not in phase2["all_phase2_names"]:
            all_errors.append(
                f"build-report 'hallucinated' built role '{name}': "
                f"not in phase2_character.yaml (未授权构建)"
            )

    # 校验 5: 每个已构建 slug 必须有 4 产物 + provenance + adapter sha + 章节白名单
    skills_dir = pipeline / "pipeline" / "story-character-skills" / ".claude" / "skills"
    for name, slug, _ in report["built"]:
        # 跳过未在 phase2 中的（已在校验 4 报错）
        if name not in phase2["all_phase2_names"]:
            continue
        if not skills_dir.is_dir() or not (skills_dir / slug).is_dir():
            all_errors.append(f"{slug} ({name}): skill directory missing under {skills_dir}")
            continue
        all_errors.extend(check_skill(pipeline, slug, name,
                                       required_sections, allowed_sections))

    if all_errors:
        print("verify_phase2_assets FAILED:")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)
    print(
        f"verify_phase2_assets PASSED "
        f"(required={len(phase2['required_names'])}, "
        f"supporting_built={len([n for n in phase2['supporting_names'] if n in built_names])}, "
        f"supporting_skipped={len([n for n in phase2['supporting_names'] if n in unbuilt_names])})"
    )
    sys.exit(0)

if __name__ == "__main__":
    main()
