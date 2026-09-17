import subprocess, os, yaml
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "verify_phase2_assets.py"
FIXTURE_DIR = Path(__file__).parent / "fixtures"
MUSE_WRITING_ROOT = Path(__file__).parents[2]
SKILL_TEMPLATE = MUSE_WRITING_ROOT / "skills" / "character-persona" / "references" / "skill-template.md"
PHASE2_SCHEMA = MUSE_WRITING_ROOT / "skills" / "phase2-character" / "references" / "output-schema.md"

ACTOR_FACING_SECTIONS = (
    "## 身份与处境\nx\n"
    "## 经历与信念\nx\n"
    "## 自觉追求\nx\n"
    "## 判断习惯与行为盲区\nx\n"
    "## 声音框架\nx\n"
    "## 边界（Layer 0 硬规则）\nx\n"
)

def write_phase2_yaml(tmp, characters):
    """写最小 phase2_character.yaml；characters = [(name, role)]
    role ∈ protagonist / deuteragonist / antagonist / supporting"""
    p = Path(tmp) / "pipeline" / "phase2_character.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    yml = {"supporting_cast": []}
    for name, role in characters:
        entry = {"name": name}
        if role in ("protagonist", "deuteragonist", "antagonist"):
            yml[role] = entry
        else:
            yml["supporting_cast"].append(entry)
    p.write_text(yaml.safe_dump(yml, allow_unicode=True))

def write_build_report(tmp, built, unbuilt=None):
    """写 build-report.md
    built = [(name, slug, reason)]
    unbuilt = [(name, skip_reason)] (default empty)"""
    unbuilt = unbuilt or []
    p = Path(tmp) / "pipeline" / "story-character-skills" / "build-report.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# 角色 Skill 构建报告", "", "## 已构建", "",
             "| name | slug | reason |", "| --- | --- | --- |"]
    for name, slug, reason in built:
        lines.append(f"| {name} | {slug} | {reason} |")
    lines += ["", "## 未构建", "",
              "| name | skip_reason |", "| --- | --- |"]
    for name, reason in unbuilt:
        lines.append(f"| {name} | {reason} |")
    p.write_text("\n".join(lines) + "\n")

def make_skill_pkg(tmp, slug, display_name, sections=None, meta_overrides=None,
                   skip_files=None):
    """构造角色包；skip_files=['state.md'|'SKILL.md'|'build-meta.yaml']。"""
    skip_files = skip_files or []
    base = Path(tmp) / "pipeline" / "story-character-skills" / ".claude" / "skills" / slug
    base.mkdir(parents=True, exist_ok=True)
    sections = sections or ACTOR_FACING_SECTIONS
    skill_content = f"---\nversion: v1\n---\n# {display_name}\n{sections}\n"

    if "SKILL.md" not in skip_files:
        (base / "SKILL.md").write_text(skill_content)
    if "state.md" not in skip_files:
        (base / "state.md").write_text("state content")
    if "build-meta.yaml" not in skip_files:
        meta = {
            "generated_by": "character-persona",
            "character_slug": slug,
            "character_display_name": display_name,
            "input_sources": ["phase2_character.yaml"],
        }
        if meta_overrides:
            meta.update(meta_overrides)
            for k, v in meta_overrides.items():
                if v is None:
                    meta.pop(k, None)
        (base / "build-meta.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True))

def run(tmp):
    return subprocess.run(["python3", str(SCRIPT), str(tmp)],
                          capture_output=True, text=True)

def test_pass_when_184_realistic_shape(tmp_path):
    """real-world fixture：184 形态——name only / 含 deuteragonist / 5 角色 / 2 群敌 skip"""
    write_phase2_yaml(tmp_path, [
        ("杨过", "protagonist"),
        ("小龙女", "deuteragonist"),
        ("罗照弦", "antagonist"),
        ("沈青芜", "supporting"),
        ("孟霜弦", "supporting"),
        ("照影楼灯使", "supporting"),
        ("照影楼探子", "supporting"),
    ])
    write_build_report(tmp_path, built=[
        ("杨过", "yang-guo", "主角"),
        ("小龙女", "xiaolongnu", "双主角"),
        ("罗照弦", "luo-zhaoxian", "主要对手"),
        ("沈青芜", "shen-qingwu", "关键新友"),
        ("孟霜弦", "meng-shuangxian", "关键新友"),
    ], unbuilt=[
        ("照影楼灯使", "群体敌人，无独立弧光"),
        ("照影楼探子", "短暂行动角色"),
    ])
    for name, slug in [("杨过", "yang-guo"), ("小龙女", "xiaolongnu"),
                       ("罗照弦", "luo-zhaoxian"), ("沈青芜", "shen-qingwu"),
                       ("孟霜弦", "meng-shuangxian")]:
        make_skill_pkg(tmp_path, slug, name)
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr


def test_new_actor_facing_package_passes_without_author_sections(tmp_path):
    """新 runtime 只含 actor-facing 必备章节即可通过。"""
    write_phase2_yaml(tmp_path, [("杨过", "protagonist")])
    write_build_report(tmp_path, built=[("杨过", "yang-guo", "主角")])
    make_skill_pkg(tmp_path, "yang-guo", "杨过", sections=ACTOR_FACING_SECTIONS)

    result = run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_legacy_author_sections_remain_allowed_during_rebuild(tmp_path):
    """旧章节保持 optional，迁移期间不会因 extra section 被误杀。"""
    legacy_sections = (
        "## 核心欲望\nx\n"
        "## 性格真相\nx\n"
        "## 人物轨迹\nx\n"
        "## 弧光\nx\n"
        "## 内在生存能力\nx\n"
        "## 主体性物件\nx\n"
        "## 表演规则\nx\n"
    )
    write_phase2_yaml(tmp_path, [("杨过", "protagonist")])
    write_build_report(tmp_path, built=[("杨过", "yang-guo", "主角")])
    make_skill_pkg(
        tmp_path,
        "yang-guo",
        "杨过",
        sections=ACTOR_FACING_SECTIONS + legacy_sections,
    )

    result = run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_actor_facing_section_fails(tmp_path):
    """行为盲区是新 runtime 的必备输入，缺失时明确失败。"""
    missing_blind_spot = ACTOR_FACING_SECTIONS.replace(
        "## 判断习惯与行为盲区\nx\n", ""
    )
    write_phase2_yaml(tmp_path, [("杨过", "protagonist")])
    write_build_report(tmp_path, built=[("杨过", "yang-guo", "主角")])
    make_skill_pkg(tmp_path, "yang-guo", "杨过", sections=missing_blind_spot)

    result = run(tmp_path)

    assert result.returncode != 0
    assert "判断习惯与行为盲区" in result.stdout + result.stderr


def test_phase2_keeps_author_design_while_generated_skill_omits_it():
    """作者设计保留在 Phase 2；新生成模板不暴露诊断与未来轨迹。"""
    template = SKILL_TEMPLATE.read_text(encoding="utf-8")
    block_start = template.index("```markdown", template.index("## SKILL.md 模板"))
    block_start += len("```markdown")
    generated_block = template[block_start:template.index("\n```", block_start)]
    schema = PHASE2_SCHEMA.read_text(encoding="utf-8")

    for author_field in ("unconscious:", "core_flaw:", "end_state:", "transformation:"):
        assert author_field in schema
    for leaked_runtime_term in (
        "不自觉欲望",
        "核心缺陷",
        "end_state",
        "## 人物轨迹",
        "## 表演规则",
    ):
        assert leaked_runtime_term not in generated_block

def test_fail_when_required_role_not_built(tmp_path):
    """protagonist/deuteragonist/antagonist 任一缺 → fail"""
    write_phase2_yaml(tmp_path, [
        ("杨过", "protagonist"),
        ("小龙女", "deuteragonist"),
        ("罗照弦", "antagonist"),
    ])
    write_build_report(tmp_path, built=[
        ("杨过", "yang-guo", "主角"),
        # 故意漏 小龙女 / 罗照弦
    ])
    make_skill_pkg(tmp_path, "yang-guo", "杨过")
    r = run(tmp_path)
    assert r.returncode != 0
    assert "小龙女" in r.stdout + r.stderr or "罗照弦" in r.stdout + r.stderr

def test_fail_when_supporting_cast_undecided(tmp_path):
    """phase2 supporting_cast 列出但 build-report 既不在已构建也不在未构建 → fail"""
    write_phase2_yaml(tmp_path, [
        ("杨过", "protagonist"),
        ("罗照弦", "antagonist"),
        ("沈青芜", "supporting"),
    ])
    write_build_report(tmp_path, built=[
        ("杨过", "yang-guo", "主角"),
        ("罗照弦", "luo-zhaoxian", "对手"),
        # 沈青芜 既不在已构建也不在未构建
    ])
    make_skill_pkg(tmp_path, "yang-guo", "杨过")
    make_skill_pkg(tmp_path, "luo-zhaoxian", "罗照弦")
    r = run(tmp_path)
    assert r.returncode != 0
    assert "沈青芜" in r.stdout + r.stderr
    assert "判定" in r.stdout + r.stderr or "undecided" in r.stdout.lower() + r.stderr.lower()

def test_fail_when_unbuilt_missing_skip_reason(tmp_path):
    """build-report 未构建表条目缺 skip_reason → fail"""
    write_phase2_yaml(tmp_path, [
        ("杨过", "protagonist"),
        ("罗照弦", "antagonist"),
        ("照影楼灯使", "supporting"),
    ])
    p = Path(tmp_path) / "pipeline" / "story-character-skills" / "build-report.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "# 报告\n## 已构建\n| name | slug | reason |\n| --- | --- | --- |\n"
        "| 杨过 | yang-guo | x |\n| 罗照弦 | luo-zhaoxian | x |\n"
        "## 未构建\n| name | skip_reason |\n| --- | --- |\n"
        "| 照影楼灯使 |  |\n"  # 故意空 skip_reason
    )
    make_skill_pkg(tmp_path, "yang-guo", "杨过")
    make_skill_pkg(tmp_path, "luo-zhaoxian", "罗照弦")
    r = run(tmp_path)
    assert r.returncode != 0
    assert "skip_reason" in r.stdout + r.stderr or "照影楼灯使" in r.stdout + r.stderr

def test_fail_when_build_report_hallucinates(tmp_path):
    """build-report 已构建表的 name 不在 phase2 中 → fail（防幻觉构建）"""
    write_phase2_yaml(tmp_path, [
        ("杨过", "protagonist"),
        ("罗照弦", "antagonist"),
    ])
    write_build_report(tmp_path, built=[
        ("杨过", "yang-guo", "主角"),
        ("罗照弦", "luo-zhaoxian", "对手"),
        ("段誉", "duan-yu", "幻觉角色"),  # phase2 没列
    ])
    for name, slug in [("杨过", "yang-guo"), ("罗照弦", "luo-zhaoxian"), ("段誉", "duan-yu")]:
        make_skill_pkg(tmp_path, slug, name)
    r = run(tmp_path)
    assert r.returncode != 0
    assert "段誉" in r.stdout + r.stderr
    assert "hallucin" in r.stdout.lower() + r.stderr.lower() or \
           "未授权" in r.stdout + r.stderr

def test_fail_when_state_md_missing(tmp_path):
    """角色状态仍是必需资产。"""
    write_phase2_yaml(tmp_path, [("杨过", "protagonist"), ("罗照弦", "antagonist")])
    write_build_report(tmp_path, built=[
        ("杨过", "yang-guo", "主角"),
        ("罗照弦", "luo-zhaoxian", "对手"),
    ])
    make_skill_pkg(tmp_path, "yang-guo", "杨过", skip_files=["state.md"])
    make_skill_pkg(tmp_path, "luo-zhaoxian", "罗照弦")
    r = run(tmp_path)
    assert r.returncode != 0
    assert "state.md" in r.stdout + r.stderr

def test_pass_without_adapter_and_preserve_legacy_metadata(tmp_path):
    write_phase2_yaml(tmp_path, [("杨过", "protagonist"), ("罗照弦", "antagonist")])
    write_build_report(tmp_path, built=[
        ("杨过", "yang-guo", "主角"),
        ("罗照弦", "luo-zhaoxian", "对手"),
    ])
    make_skill_pkg(tmp_path, "yang-guo", "杨过",
                   meta_overrides={"adapter_path": "pipeline/characters/杨过.md",
                                   "adapter_sha256": "legacy-value"})
    make_skill_pkg(tmp_path, "luo-zhaoxian", "罗照弦")
    r = run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (tmp_path / "pipeline" / "characters").exists()
    meta_path = tmp_path / "pipeline/story-character-skills/.claude/skills/yang-guo/build-meta.yaml"
    assert yaml.safe_load(meta_path.read_text())["adapter_sha256"] == "legacy-value"


def test_fail_when_metadata_role_differs_from_build_report(tmp_path):
    write_phase2_yaml(tmp_path, [("杨过", "protagonist")])
    write_build_report(tmp_path, built=[("杨过", "yang-guo", "主角")])
    make_skill_pkg(tmp_path, "yang-guo", "杨过", meta_overrides={
        "character_slug": "other-role",
        "character_display_name": "另一人",
    })
    result = run(tmp_path)
    assert result.returncode != 0
    assert "character_slug differs" in result.stdout
    assert "character_display_name differs" in result.stdout

def test_fail_when_phase2_yaml_missing(tmp_path):
    """没有 phase2_character.yaml 无法做应构建集反向校验"""
    write_build_report(tmp_path, built=[("杨过", "yang-guo", "主角")])
    make_skill_pkg(tmp_path, "yang-guo", "杨过")
    r = run(tmp_path)
    assert r.returncode != 0
    assert "phase2_character.yaml" in r.stdout + r.stderr

def test_fail_when_build_report_missing(tmp_path):
    """没有 build-report.md → fail（无 name→slug 映射桥梁）"""
    write_phase2_yaml(tmp_path, [("杨过", "protagonist"), ("罗照弦", "antagonist")])
    r = run(tmp_path)
    assert r.returncode != 0
    assert "build-report" in r.stdout + r.stderr


# ---------------------------------------------------------------------------
# core 字段必填校验
# ---------------------------------------------------------------------------

def test_default_still_fails_when_core_field_missing(tmp_path):
    """缺 core 字段（如 character_slug）→ fail"""
    write_phase2_yaml(tmp_path, [("杨过", "protagonist")])
    write_build_report(tmp_path, built=[("杨过", "yang-guo", "主角")])
    make_skill_pkg(tmp_path, "yang-guo", "杨过", meta_overrides={
        "character_slug": None,
    })
    r = run(tmp_path)
    assert r.returncode != 0
    assert "character_slug" in r.stdout + r.stderr


# ---------------------------------------------------------------------------
# canon_archetype hard gate
# ---------------------------------------------------------------------------

def test_canon_archetype_length_1_dominant_passes():
    """单一主要来源的有效绑定。"""
    from verify_phase2_assets import verify_canon_archetype

    p2 = {"protagonist": {"canon_archetype": [{"id": "INS-A01", "weight": "dominant"}]}}
    ledger = {"inspirations": [{"id": "INS-A01", "type": "archetype", "status": "bound", "archetype_target_slug": "protagonist"}]}
    findings = verify_canon_archetype(p2, ledger)
    assert findings == []


def test_canon_archetype_length_2_dominant_plus_secondary_with_merge_boundary_passes():
    """补充来源保留明确的融合边界。"""
    from verify_phase2_assets import verify_canon_archetype

    p2 = {"deuteragonist": {"canon_archetype": [
        {"id": "INS-A02", "weight": "dominant"},
        {"id": "INS-A03", "weight": "secondary", "merge_boundary": "只学语言节奏"},
    ]}}
    ledger = {"inspirations": [
        {"id": "INS-A02", "type": "archetype", "status": "bound", "archetype_target_slug": "deuteragonist"},
        {"id": "INS-A03", "type": "archetype", "status": "accepted", "archetype_target_slug": "deuteragonist"},
    ]}
    findings = verify_canon_archetype(p2, ledger)
    assert findings == []


def test_canon_archetype_multiple_sources_pass():
    """多个来源的数量本身不产生错误。"""
    from verify_phase2_assets import verify_canon_archetype

    p2 = {"protagonist": {"canon_archetype": [
        {"id": "INS-A01", "weight": "dominant"},
        {"id": "INS-A02", "weight": "secondary", "merge_boundary": "x"},
        {"id": "INS-A03", "weight": "secondary", "merge_boundary": "y"},
    ]}}
    ledger = {"inspirations": [
        {"id": f"INS-A0{i}", "type": "archetype", "status": "bound", "archetype_target_slug": "protagonist"}
        for i in (1, 2, 3)
    ]}
    findings = verify_canon_archetype(p2, ledger)
    assert findings == []


def test_canon_archetype_two_dominants_pass():
    """来源权重按实际作用填写，无固定配比。"""
    from verify_phase2_assets import verify_canon_archetype

    p2 = {"protagonist": {"canon_archetype": [
        {"id": "INS-A01", "weight": "dominant"},
        {"id": "INS-A02", "weight": "dominant"},
    ]}}
    ledger = {"inspirations": [
        {"id": "INS-A01", "type": "archetype", "status": "bound", "archetype_target_slug": "protagonist"},
        {"id": "INS-A02", "type": "archetype", "status": "bound", "archetype_target_slug": "protagonist"},
    ]}
    findings = verify_canon_archetype(p2, ledger)
    assert findings == []


def test_canon_archetype_secondary_missing_merge_boundary_reports_error():
    """secondary 缺 merge_boundary 报错"""
    from verify_phase2_assets import verify_canon_archetype

    p2 = {"protagonist": {"canon_archetype": [
        {"id": "INS-A01", "weight": "dominant"},
        {"id": "INS-A02", "weight": "secondary"},
    ]}}
    ledger = {"inspirations": [
        {"id": "INS-A01", "type": "archetype", "status": "bound", "archetype_target_slug": "protagonist"},
        {"id": "INS-A02", "type": "archetype", "status": "bound", "archetype_target_slug": "protagonist"},
    ]}
    findings = verify_canon_archetype(p2, ledger)
    assert any("merge_boundary" in f["message"] or "merge_boundary" in f["code"] for f in findings)


def test_canon_archetype_field_absent_passes():
    """字段不存在 -> 不报错（向后兼容）"""
    from verify_phase2_assets import verify_canon_archetype

    p2 = {"protagonist": {"display_name": "主角"}}
    ledger = {}
    findings = verify_canon_archetype(p2, ledger)
    assert findings == []


def test_cli_main_accepts_multiple_archetypes(tmp_path):
    """CLI 接受来源完整、融合边界明确的多原型绑定。"""
    write_phase2_yaml(tmp_path, [("主角", "protagonist")])
    phase2_path = Path(tmp_path) / "pipeline" / "phase2_character.yaml"
    phase2 = yaml.safe_load(phase2_path.read_text()) or {}
    phase2["protagonist"]["canon_archetype"] = [
        {"id": "INS-A01", "weight": "dominant"},
        {"id": "INS-A02", "weight": "secondary", "merge_boundary": "x"},
        {"id": "INS-A03", "weight": "secondary", "merge_boundary": "y"},
    ]
    phase2_path.write_text(yaml.safe_dump(phase2, allow_unicode=True))
    write_build_report(tmp_path, built=[("主角", "main", "主角")])
    make_skill_pkg(tmp_path, "main", "主角")
    ledger = {"inspirations": [
        {"id": f"INS-A0{i}", "type": "archetype", "status": "bound", "archetype_target_slug": "protagonist"}
        for i in (1, 2, 3)
    ]}
    (Path(tmp_path) / "pipeline" / "inspiration_ledger.yaml").write_text(
        yaml.safe_dump(ledger, allow_unicode=True)
    )
    result = run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_main_passes_without_archetype_references_or_ledger(tmp_path):
    """没有原型引用时无需 ledger。"""
    write_phase2_yaml(tmp_path, [("主角", "protagonist")])
    write_build_report(tmp_path, built=[("主角", "main", "主角")])
    make_skill_pkg(tmp_path, "main", "主角")
    result = run(tmp_path)
    assert "canon_archetype" not in (result.stdout + result.stderr)


def test_cli_main_rejects_archetype_reference_without_ledger(tmp_path):
    write_phase2_yaml(tmp_path, [("主角", "protagonist")])
    phase2_path = tmp_path / "pipeline" / "phase2_character.yaml"
    phase2 = yaml.safe_load(phase2_path.read_text())
    phase2["protagonist"]["canon_archetype"] = [{"id": "INS-A01", "weight": "dominant"}]
    phase2_path.write_text(yaml.safe_dump(phase2, allow_unicode=True))
    write_build_report(tmp_path, built=[("主角", "main", "主角")])
    make_skill_pkg(tmp_path, "main", "主角")
    result = run(tmp_path)
    assert result.returncode != 0
    assert "canon_archetype_ledger_id_missing" in result.stdout + result.stderr


from verify_phase2_assets import parse_build_report

def _write_report(tmp_path, text):
    p = tmp_path / "pipeline" / "story-character-skills"
    p.mkdir(parents=True, exist_ok=True)
    (p / "build-report.md").write_text(text, encoding="utf-8")

def test_build_report_production_five_col_built(tmp_path):
    """production 模板：已构建 5 列 + 未构建 3 列（R2-F5 表头驱动）"""
    _write_report(tmp_path,
        "# Build Report\n\n## 已构建\n\n"
        "| name | slug | 类型 | 深度 | 3 产物落盘 |\n|------|------|------|------|------------|\n"
        "| 张三 | zhang-san | protagonist | 完整 | ✅ |\n\n"
        "## 未构建\n\n| name | 类型 | skip_reason |\n|------|------|-------------|\n"
        "| 路人甲 | supporting_cast | 背景人物无独立对白 |\n")
    report = parse_build_report(tmp_path)
    assert report["built"] == [("张三", "zhang-san", "")]
    assert report["unbuilt"] == [("路人甲", "背景人物无独立对白")]

def test_build_report_legacy_three_col_same_mapping(tmp_path):
    """历史 3 列已构建表与 production 表得到相同 name→slug（向后兼容）"""
    _write_report(tmp_path,
        "# 报告\n\n## 已构建\n\n| name | slug | reason |\n| --- | --- | --- |\n"
        "| 张三 | zhang-san | 主角 |\n\n"
        "## 未构建\n\n| name | skip_reason |\n| --- | --- |\n| 路人甲 | 背景 |\n")
    report = parse_build_report(tmp_path)
    assert report["built"] == [("张三", "zhang-san", "主角")]
    assert report["unbuilt"] == [("路人甲", "背景")]
