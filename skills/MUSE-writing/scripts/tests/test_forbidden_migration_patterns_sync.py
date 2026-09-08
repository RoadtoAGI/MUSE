"""Sync checks for semantic migration pattern SSOT."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REFS_DIR = Path(__file__).parent.parent.parent / "skills" / "prose-craft" / "references"


def test_pattern_source_is_reachable_without_copying_every_regex_into_prose():
    """Runtime review can reach the same source loaded by the detector."""
    from post_revision_gate import FORBIDDEN_MIGRATION_PATTERNS

    source = REFS_DIR / "forbidden_migration_patterns.yaml"
    yaml_data = yaml.safe_load(source.read_text())
    md_text = (REFS_DIR / "ai-cliche-patterns.md").read_text()
    assert source.name in md_text
    assert set(FORBIDDEN_MIGRATION_PATTERNS) == set(yaml_data)
    for function, patterns in yaml_data.items():
        assert set(FORBIDDEN_MIGRATION_PATTERNS[function]) == set(patterns)


def test_forbidden_migration_patterns_yaml_loadable_by_post_revision_gate():
    """YAML regex values must compile before post_revision_gate imports them."""
    yaml_data = yaml.safe_load((REFS_DIR / "forbidden_migration_patterns.yaml").read_text())
    for patterns in yaml_data.values():
        for pattern in patterns.values():
            re.compile(pattern)
