"""同一包现行发布线的 Claude/Codex manifest 与 marketplace 版本保持一致。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGES = ["MUSE-writing", "MUSE-serial-writing",
            "MUSE-canon-distill", "MUSE-serial-distill"]


@pytest.mark.parametrize("pkg", PACKAGES)
def test_versions_consistent(pkg):
    root = REPO_ROOT / "skills" / pkg / ".claude-plugin"
    if not (root / "plugin.json").exists():
        pytest.skip(f"{pkg} 无 .claude-plugin（本机未检出）")
    plugin = json.loads((root / "plugin.json").read_text())
    versions = {"plugin.json": plugin["version"]}
    codex_path = root.parent / ".codex-plugin" / "plugin.json"
    if codex_path.exists():
        versions["codex.plugin.json"] = json.loads(codex_path.read_text())["version"]
    mp_path = root / "marketplace.json"
    if mp_path.exists():
        mp = json.loads(mp_path.read_text())
        if "version" in mp.get("metadata", {}):
            versions["marketplace.metadata"] = mp["metadata"]["version"]
        if mp.get("plugins"):
            versions["marketplace.plugins[0]"] = mp["plugins"][0].get("version", plugin["version"])
    assert len(set(versions.values())) == 1, f"{pkg} 版本面不一致: {versions}"
