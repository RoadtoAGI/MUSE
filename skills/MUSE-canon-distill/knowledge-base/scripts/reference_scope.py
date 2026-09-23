"""Author-selected source permissions shared by retrieval adapters."""
from pathlib import Path

import yaml

INTENDED_DOMAINS = (
    "world_rule", "reveal_structure", "protagonist_archetype",
    "scene_carrier", "prose_style_imitation",
)


def _reference_scope(result: dict, reuse_mode: str | None = None,
                     intended_domains: list[str] | None = None) -> tuple[str | None, list[str] | None]:
    """本次共同限制与逐来源限制取交集。空领域列表沿旧契约表示未绑定。"""
    modes = [m for m in (reuse_mode, result.get("reuse_mode")) if m is not None]
    if any(m not in {"maximize_apt_reuse", "style_only"} for m in modes):
        raise ValueError(f"不支持的 reuse_mode: {modes}")
    mode = "style_only" if "style_only" in modes else (modes[0] if modes else None)
    domains = [list(dict.fromkeys(ds)) for ds in
               (intended_domains, result.get("intended_domains")) if ds]
    if any(set(ds) - set(INTENDED_DOMAINS) for ds in domains):
        raise ValueError(f"不支持的 intended_domains: {domains}")
    shared = [d for d in domains[0] if all(d in ds for ds in domains[1:])] if domains else None
    return mode, shared


def bind_reference_profile(results: list[dict], path: str) -> list[dict]:
    """从现有 Phase 0 按作品名精确绑定用途，保留逐来源差异。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Phase 0 必须是 YAML mapping")
    profile = data.get("canon_reference_profile") or {}
    if not isinstance(profile, dict):
        raise ValueError("canon_reference_profile 必须是 mapping")
    materials = profile.get("user_reference_materials") or []
    by_work = {}
    for material in materials:
        if not isinstance(material, dict):
            raise ValueError("user_reference_materials 条目必须是 mapping")
        work = material.get("work")
        if not isinstance(work, str) or not work:
            raise ValueError("参考来源缺 work")
        if work in by_work:
            raise ValueError(f"参考来源重复，需明确当前用途: {work}")
        by_work[work] = material
    bound = []
    for result in results:
        material = by_work.get(result.get("novel"))
        if material is None:
            bound.append(dict(result))
            continue
        if material.get("stance") == "avoid":
            continue
        mode, domains = _reference_scope(result, material.get("reuse_mode"),
                                          material.get("intended_domains"))
        if domains == []:
            continue
        current = dict(result)
        if mode is not None:
            current["reuse_mode"] = mode
        if domains is not None:
            current["intended_domains"] = domains
        bound.append(current)
    return bound
