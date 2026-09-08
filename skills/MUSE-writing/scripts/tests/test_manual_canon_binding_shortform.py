"""手选名著绑定在既有短链契约中的最小回归测试。"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_shortform_contract import validate_conception  # noqa: E402


def _conception() -> dict:
    return {
        "premise": "感染暴发后，保安护送一名伤者穿过封锁区",
        "core_value": "互助↔自保",
        "genre": "末世",
        "target_length": 8000,
    }


def test_short_conception_accepts_manual_reference_binding():
    data = _conception()
    data["canon_reference_profile"] = {
        "desired_domains": ["world_rule", "scene_carrier"],
        "user_reference_materials": [
            {
                "work": "狂病",
                "stance": "prefer",
                "intended_domains": ["world_rule", "scene_carrier"],
                "reuse_mode": "maximize_apt_reuse",
            }
        ],
    }

    assert validate_conception(data) == []


def test_short_conception_rejects_invented_reference_domain():
    data = _conception()
    data["canon_reference_profile"] = {
        "user_reference_materials": [
            {
                "work": "狂病",
                "stance": "prefer",
                "intended_domains": ["apocalypse_special_case"],
            }
        ]
    }

    errors = validate_conception(data)
    assert any("apocalypse_special_case" in error for error in errors)


def test_short_conception_keeps_legacy_reference_hint_compatible():
    data = _conception()
    data["canon_reference_profile"] = {
        "user_reference_materials": [
            {"work": "狂病", "stance": "prefer", "reason": "题材接近"}
        ]
    }

    assert validate_conception(data) == []


