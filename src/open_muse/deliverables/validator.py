# src/open_muse/deliverables/validator.py
"""Deliverable validation against Skill's required-deliverables."""
from __future__ import annotations

from typing import Any


def validate_deliverable(data: Any, required_fields: list[str]) -> list[str]:
    """Validate that data contains all required fields with non-empty values.
    Returns list of error messages (empty = valid).
    """
    errors = []
    if not isinstance(data, dict):
        return [f"Expected dict, got {type(data).__name__}"]

    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
        elif not data[field]:
            errors.append(f"Empty required field: {field}")

    return errors
