"""角色上下文与候选动作示例的可解析接口检查。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _yaml_example(relative: str) -> dict:
    text = (ROOT / relative).read_text(encoding="utf-8")
    block = text.split("```yaml", 1)[1].split("```", 1)[0]
    return yaml.safe_load(block)


def test_role_view_example_has_per_character_input_shape():
    view = _yaml_example("skills/role-brief-deriver/SKILL.md")
    assert set(view) == {
        "scene_id", "character", "known_now", "observable_stimuli", "constraints_now"
    }
    for key in ("known_now", "observable_stimuli", "constraints_now"):
        assert isinstance(view[key], list)
    for stimulus in view["observable_stimuli"]:
        assert set(stimulus) == {"id", "cue"}


def test_role_move_example_preserves_string_on_key_for_yaml_consumers():
    move = _yaml_example("skills/character-rehearsal/references/output-schema.md")
    assert set(move) == {"character", "moves"}
    assert set(move["moves"][0]) == {"on", "meaning", "move", "intended_effect"}
    assert True not in move["moves"][0]
