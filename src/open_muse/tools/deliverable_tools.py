# src/open_muse/tools/deliverable_tools.py
"""Tool handlers for deliverable read/write."""
from __future__ import annotations

import yaml
from open_muse.deliverables.storage import DeliverableStore


def make_write_deliverable_handler(store: DeliverableStore):
    """Factory: returns a write_deliverable handler."""
    def handler(params: dict) -> str:
        name = params.get("name", "")
        content = params.get("content", "")
        fmt = params.get("format", "yaml")

        if fmt == "yaml":
            try:
                parsed = yaml.safe_load(content)
            except yaml.YAMLError:
                parsed = {"raw": content}
            path = store.write(name, parsed, fmt="yaml")
        else:
            path = store.write(name, content, fmt="md")

        return f"Deliverable written: {path}"

    return handler


def make_read_deliverable_handler(store: DeliverableStore):
    """Factory: returns a read_deliverable handler."""
    def handler(params: dict) -> str:
        name = params.get("name", "")
        data = store.read(name)
        if data is None:
            available = store.list_available()
            return f"Deliverable '{name}' not found. Available: {', '.join(available)}"
        if isinstance(data, dict):
            return yaml.dump(data, allow_unicode=True, default_flow_style=False)
        return data

    return handler
