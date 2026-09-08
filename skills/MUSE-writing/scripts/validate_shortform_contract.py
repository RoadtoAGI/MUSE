#!/usr/bin/env python3
"""validate_shortform_contract.py — 短链 shortform YAML 属主校验器。

被 hooks/shortform-contract-check.py 以 subprocess 调用，也可直接 CLI 使用。
按 basename 分派四类 schema：正向 allowlist（未知字段拒绝）+ 列表内 id 唯一性
（先于外键校验）+ 外键存在性 + outline 禁键递归拒绝（任意深度）。

用法:
    python3 validate_shortform_contract.py <path/to/pipeline/shortform/xxx.yaml>

退出码: 0=通过; 1=违规（违规清单打到 stdout）; 2=用法/IO 错误
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SCENE_ID_RE = re.compile(r"^S\d{2}$")
INS_ID_RE = re.compile(r"^INS-\d{3}$")
# task 为职责说明字符串，避免设计 marker 进入正文输入
TASK_MARKER_RE = re.compile(r"^\s*\[")

# 全链实现字段——短链 schema 中不存在，任意深度出现即拒绝
BANNED_KEYS = {
    "abstract_function",
    "physical_carrier",
    "reader_yield",
    "rendering",
    "craft_carrier",
    "beat_direction",
    "narrator_distance",
    "climax_pattern",
    "world_disclosure_plan",
    "prose_risk_contract",
    "voice_gear",
}

CONCEPTION_REQUIRED = {"premise", "core_value", "genre", "target_length"}
CONCEPTION_ALLOWED = CONCEPTION_REQUIRED | {
    "style_directives",
    "requirements",
    "reference_materials",
    "canon_reference_profile",
}

CANON_DOMAINS = {
    "world_rule",
    "reveal_structure",
    "protagonist_archetype",
    "scene_carrier",
    "prose_style_imitation",
}
CANON_PROFILE_ALLOWED = {"desired_domains", "avoid_domains", "user_reference_materials"}
CANON_MATERIAL_ALLOWED = {"work", "stance", "reason", "intended_domains", "reuse_mode"}

CHARACTER_REQUIRED = {"id", "name"}
CHARACTER_CONTEXT = {"desire", "pressure", "voice"}
CHARACTER_ALLOWED = CHARACTER_REQUIRED | CHARACTER_CONTEXT | {"voice_boundaries", "relationships"}
RELATIONSHIP_ALLOWED = {"with", "nature"}

SPINE_FIELDS = {"spine_statement", "dramatic_question", "ending_pressure"}
SCENE_REQUIRED = {
    "scene_id",
    "pov",
    "participants",
    "location_time",
    "conflict",
    "value_start",
    "value_end",
    "task",
}
SCENE_ALLOWED = SCENE_REQUIRED | {"handoff", "inspiration_refs"}

LEDGER_FIELDS = {"id", "type", "status", "source", "project_encoding"}
LEDGER_STATUS = {"candidate", "adopted"}

VALID_BASENAMES = (
    "conception.yaml",
    "characters.yaml",
    "outline.yaml",
    "inspiration_ledger.yaml",
)


def _is_filled_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_str_field(container: dict, key: str, ctx: str, errors: list[str]) -> None:
    if key not in container:
        errors.append(f"{ctx}: 缺必填字段 `{key}`")
    elif not _is_filled_str(container[key]):
        errors.append(f"{ctx}: `{key}` 必须是非空字符串")


def _check_str_list(value, ctx: str, key: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{ctx}: `{key}` 必须是非空列表")
        return
    for i, item in enumerate(value):
        if not _is_filled_str(item):
            errors.append(f"{ctx}: `{key}[{i}]` 必须是非空字符串")


def _check_unknown_keys(container: dict, allowed: set[str], ctx: str, errors: list[str]) -> None:
    unknown = set(container.keys()) - allowed
    if unknown:
        errors.append(f"{ctx}: 未知字段 {sorted(unknown)}（正向 allowlist 拒绝）")


def _scan_banned_keys(node, path: str, errors: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in BANNED_KEYS:
                errors.append(f"{path}.{key}: 禁键（全链实现字段，短链 schema 不存在）")
            _scan_banned_keys(value, f"{path}.{key}", errors)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _scan_banned_keys(item, f"{path}[{i}]", errors)


def _load_yaml(path: Path, errors: list[str]):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(f"{path.name}: YAML 解析失败——{exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path.name}: 顶层必须是 mapping（当前为 {type(data).__name__}）")
        return None
    return data


def validate_conception(data: dict) -> list[str]:
    errors: list[str] = []
    _check_unknown_keys(data, CONCEPTION_ALLOWED, "conception", errors)
    for key in ("premise", "core_value", "genre"):
        _check_str_field(data, key, "conception", errors)
    if "target_length" not in data:
        errors.append("conception: 缺必填字段 `target_length`")
    elif not isinstance(data["target_length"], int) or isinstance(data["target_length"], bool) \
            or data["target_length"] <= 0:
        errors.append("conception: `target_length` 必须是正整数（目标字数）")
    for key in ("style_directives", "requirements"):
        if key in data:
            _check_str_list(data[key], "conception", key, errors)
    if "reference_materials" in data and not _is_filled_str(data["reference_materials"]):
        errors.append("conception: `reference_materials` 必须是非空字符串")
    profile = data.get("canon_reference_profile")
    if profile is not None:
        if not isinstance(profile, dict):
            errors.append("conception: `canon_reference_profile` 必须是 mapping")
            return errors
        _check_unknown_keys(profile, CANON_PROFILE_ALLOWED, "canon_reference_profile", errors)
        for key in ("desired_domains", "avoid_domains"):
            if key in profile:
                _check_str_list(profile[key], "canon_reference_profile", key, errors)
                if isinstance(profile[key], list):
                    for domain in profile[key]:
                        if _is_filled_str(domain) and domain not in CANON_DOMAINS:
                            errors.append(f"canon_reference_profile.{key}: 未知领域 {domain!r}")
        materials = profile.get("user_reference_materials")
        if materials is not None:
            if not isinstance(materials, list) or not materials:
                errors.append("canon_reference_profile: `user_reference_materials` 必须是非空列表")
            else:
                for i, material in enumerate(materials):
                    ctx = f"canon_reference_profile.user_reference_materials[{i}]"
                    if not isinstance(material, dict):
                        errors.append(f"{ctx}: 必须是 mapping")
                        continue
                    _check_unknown_keys(material, CANON_MATERIAL_ALLOWED, ctx, errors)
                    _check_str_field(material, "work", ctx, errors)
                    _check_str_field(material, "stance", ctx, errors)
                    if material.get("stance") not in {"prefer", "avoid"}:
                        errors.append(f"{ctx}: `stance` 必须是 prefer 或 avoid")
                    if "reason" in material and not _is_filled_str(material["reason"]):
                        errors.append(f"{ctx}: `reason` 必须是非空字符串")
                    if "intended_domains" in material:
                        _check_str_list(material["intended_domains"], ctx, "intended_domains", errors)
                        if isinstance(material["intended_domains"], list):
                            for domain in material["intended_domains"]:
                                if _is_filled_str(domain) and domain not in CANON_DOMAINS:
                                    errors.append(f"{ctx}.intended_domains: 未知领域 {domain!r}")
                    if "reuse_mode" in material and material["reuse_mode"] not in {
                        "maximize_apt_reuse", "style_only"
                    }:
                        errors.append(
                            f"{ctx}: `reuse_mode` 必须是 maximize_apt_reuse 或 style_only"
                        )
    return errors


def validate_characters(data: dict) -> list[str]:
    errors: list[str] = []
    _check_unknown_keys(data, {"characters"}, "characters.yaml 顶层", errors)
    chars = data.get("characters")
    if not isinstance(chars, list) or not chars:
        errors.append("characters: `characters` 必须是非空列表")
        return errors

    # 唯一性先于外键（重复 id 下外键多目标无解）
    ids: list[str] = []
    for i, char in enumerate(chars):
        ctx = f"characters[{i}]"
        if not isinstance(char, dict):
            errors.append(f"{ctx}: 人物卡必须是 mapping")
            continue
        _check_unknown_keys(char, CHARACTER_ALLOWED, ctx, errors)
        for key in CHARACTER_REQUIRED | (CHARACTER_CONTEXT & char.keys()):
            _check_str_field(char, key, ctx, errors)
        cid = char.get("id")
        if _is_filled_str(cid):
            if not SLUG_RE.match(cid):
                errors.append(f"{ctx}: `id`={cid!r} 不是 ASCII kebab slug")
            if cid in ids:
                errors.append(f"{ctx}: `id`={cid!r} 与前文重复（列表内唯一）")
            ids.append(cid)
        if "voice_boundaries" in char:
            _check_str_list(char["voice_boundaries"], ctx, "voice_boundaries", errors)

    id_set = set(ids)
    for i, char in enumerate(chars):
        if not isinstance(char, dict) or "relationships" not in char:
            continue
        ctx = f"characters[{i}]"
        rels = char["relationships"]
        if not isinstance(rels, list) or not rels:
            errors.append(f"{ctx}: `relationships` 必须是非空列表")
            continue
        for j, rel in enumerate(rels):
            rctx = f"{ctx}.relationships[{j}]"
            if not isinstance(rel, dict):
                errors.append(f"{rctx}: 必须是 mapping")
                continue
            _check_unknown_keys(rel, RELATIONSHIP_ALLOWED, rctx, errors)
            _check_str_field(rel, "with", rctx, errors)
            _check_str_field(rel, "nature", rctx, errors)
            target = rel.get("with")
            if _is_filled_str(target) and target not in id_set:
                errors.append(f"{rctx}: `with`={target!r} 不在 characters[].id 中（外键无锚）")
    return errors


def _load_character_ids(shortform_dir: Path, errors: list[str]) -> set[str] | None:
    char_path = shortform_dir / "characters.yaml"
    if not char_path.exists():
        errors.append(
            "outline: characters.yaml 缺失——pov/participants 外键无锚（时序：Phase 1 人物卡先于大纲落盘）"
        )
        return None
    sub_errors: list[str] = []
    data = _load_yaml(char_path, sub_errors)
    if data is None:
        errors.append("outline: characters.yaml 不可解析，外键无法校验")
        return None
    chars = data.get("characters")
    if not isinstance(chars, list):
        errors.append("outline: characters.yaml 无合法 characters 列表，外键无法校验")
        return None
    return {c.get("id") for c in chars if isinstance(c, dict) and _is_filled_str(c.get("id"))}


def _load_adopted_ins(shortform_dir: Path, errors: list[str]) -> set[str] | None:
    ledger_path = shortform_dir / "inspiration_ledger.yaml"
    if not ledger_path.exists():
        errors.append(
            "outline: 引用了 inspiration_refs 但 inspiration_ledger.yaml 缺失"
            "（时序：ledger 先于 outline 落盘）"
        )
        return None
    sub_errors: list[str] = []
    data = _load_yaml(ledger_path, sub_errors)
    if data is None:
        errors.append("outline: inspiration_ledger.yaml 不可解析，INS 外键无法校验")
        return None
    items = data.get("inspirations")
    if not isinstance(items, list):
        errors.append("outline: inspiration_ledger.yaml 无合法 inspirations 列表")
        return None
    return {
        item.get("id")
        for item in items
        if isinstance(item, dict) and item.get("status") == "adopted" and _is_filled_str(item.get("id"))
    }


def validate_outline(data: dict, shortform_dir: Path) -> list[str]:
    errors: list[str] = []
    _check_unknown_keys(data, {"spine", "scenes"}, "outline 顶层", errors)
    _scan_banned_keys(data, "outline", errors)

    spine = data.get("spine")
    if not isinstance(spine, dict):
        errors.append("outline: 缺 `spine` 块（顶层脊椎，必填）")
    else:
        _check_unknown_keys(spine, SPINE_FIELDS, "spine", errors)
        for key in SPINE_FIELDS:
            _check_str_field(spine, key, "spine", errors)

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("outline: `scenes` 必须是非空列表")
        return errors

    # 唯一性先于外键
    seen_ids: list[str] = []
    uses_ins = False
    for i, scene in enumerate(scenes):
        ctx = f"scenes[{i}]"
        if not isinstance(scene, dict):
            errors.append(f"{ctx}: 场景卡必须是 mapping")
            continue
        _check_unknown_keys(scene, SCENE_ALLOWED, ctx, errors)
        sid = scene.get("scene_id")
        if not _is_filled_str(sid) or not SCENE_ID_RE.match(sid):
            errors.append(f"{ctx}: `scene_id`={sid!r} 不符合 ^S\\d{{2}}$")
        elif sid in seen_ids:
            errors.append(f"{ctx}: `scene_id`={sid!r} 与前文重复（列表内唯一）")
        else:
            seen_ids.append(sid)

        for key in ("pov", "location_time", "conflict", "value_start", "value_end"):
            _check_str_field(scene, key, ctx, errors)
        task = scene.get("task")
        if not _is_filled_str(task):
            errors.append(f"{ctx}: `task` 必须是非空职责说明字符串")
        elif TASK_MARKER_RE.match(task):
            errors.append(f"{ctx}: `task` 不应以设计 [marker] 开头")
        if "handoff" in scene and not _is_filled_str(scene["handoff"]):
            errors.append(f"{ctx}: `handoff` 若出现必须是非空字符串")

        participants = scene.get("participants")
        if not isinstance(participants, list) or not participants:
            errors.append(f"{ctx}: `participants` 必须是非空列表")
        if "inspiration_refs" in scene:
            refs = scene["inspiration_refs"]
            if not isinstance(refs, list) or not refs:
                errors.append(f"{ctx}: `inspiration_refs` 必须是非空列表")
            else:
                uses_ins = True
                for ref in refs:
                    if not _is_filled_str(ref) or not INS_ID_RE.match(ref):
                        errors.append(f"{ctx}: inspiration_refs 项 {ref!r} 不符合 ^INS-\\d{{3}}$")

    # 外键（唯一性通过后）
    char_ids = _load_character_ids(shortform_dir, errors)
    if char_ids is not None:
        for i, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                continue
            ctx = f"scenes[{i}]"
            pov = scene.get("pov")
            if _is_filled_str(pov) and pov not in char_ids and not (
                pov.startswith("narrator:") and pov.removeprefix("narrator:").strip()
            ):
                errors.append(f"{ctx}: `pov`={pov!r} 须为人物 id 或 narrator:<叙述位置>")
            participants = scene.get("participants")
            if isinstance(participants, list):
                for p in participants:
                    if not _is_filled_str(p) or p not in char_ids:
                        errors.append(f"{ctx}: participants 项 {p!r} 不在 characters[].id 中")

    if uses_ins:
        adopted = _load_adopted_ins(shortform_dir, errors)
        if adopted is not None:
            for i, scene in enumerate(scenes):
                if not isinstance(scene, dict):
                    continue
                for ref in scene.get("inspiration_refs") or []:
                    if _is_filled_str(ref) and INS_ID_RE.match(ref) and ref not in adopted:
                        errors.append(
                            f"scenes[{i}]: inspiration_refs {ref!r} 不是 ledger 中 status=adopted 的条目"
                        )
    return errors


def validate_ledger(data: dict) -> list[str]:
    errors: list[str] = []
    _check_unknown_keys(data, {"inspirations"}, "inspiration_ledger 顶层", errors)
    items = data.get("inspirations")
    if not isinstance(items, list) or not items:
        errors.append("inspiration_ledger: `inspirations` 必须是非空列表")
        return errors
    seen: list[str] = []
    for i, item in enumerate(items):
        ctx = f"inspirations[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{ctx}: 必须是 mapping")
            continue
        _check_unknown_keys(item, LEDGER_FIELDS, ctx, errors)
        for key in ("type", "source", "project_encoding"):
            _check_str_field(item, key, ctx, errors)
        iid = item.get("id")
        if not _is_filled_str(iid) or not INS_ID_RE.match(iid):
            errors.append(f"{ctx}: `id`={iid!r} 不符合 ^INS-\\d{{3}}$")
        elif iid in seen:
            errors.append(f"{ctx}: `id`={iid!r} 与前文重复（列表内唯一）")
        else:
            seen.append(iid)
        status = item.get("status")
        if status not in LEDGER_STATUS:
            errors.append(f"{ctx}: `status`={status!r} 不在 {sorted(LEDGER_STATUS)}")
    return errors


def validate_file(path: Path) -> list[str]:
    """校验单个 shortform YAML；返回违规清单（空列表 = 通过）。"""
    basename = path.name
    if basename not in VALID_BASENAMES:
        return [
            f"{basename}: 非短链契约产物名——pipeline/shortform/ 下只允许 {list(VALID_BASENAMES)}"
        ]
    errors: list[str] = []
    data = _load_yaml(path, errors)
    if data is None:
        return errors
    if basename == "conception.yaml":
        errors.extend(validate_conception(data))
    elif basename == "characters.yaml":
        errors.extend(validate_characters(data))
    elif basename == "outline.yaml":
        errors.extend(validate_outline(data, path.parent))
    elif basename == "inspiration_ledger.yaml":
        errors.extend(validate_ledger(data))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("用法: validate_shortform_contract.py <pipeline/shortform/xxx.yaml>", file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.exists():
        print(f"[shortform-contract] ERROR: 文件不存在: {path}", file=sys.stderr)
        return 2
    errors = validate_file(path)
    if errors:
        print(f"[shortform-contract] {path.name} 违规 {len(errors)} 项：")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"[shortform-contract] {path.name} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
