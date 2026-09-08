# src/open_muse/deliverables/storage.py
"""Deliverable storage: read/write YAML and Markdown files."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml


class DeliverableStore:
    """Manages deliverable files under {output_dir}/pipeline/."""

    def __init__(self, output_dir: Path):
        self._base = Path(output_dir) / "pipeline"
        self._base.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, name: str, ext: str) -> Path:
        """Resolve path and ensure it stays within deliverables directory."""
        path = (self._base / f"{name}{ext}").resolve()
        if not str(path).startswith(str(self._base.resolve())):
            raise ValueError(f"Path traversal rejected: {name}")
        return path

    def write(self, name: str, content: Any, fmt: str = "yaml") -> Path:
        """Write a deliverable. fmt='yaml' for structured, 'md' for text."""
        ext = ".yaml" if fmt == "yaml" else ".md"
        path = self._safe_path(name, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "yaml":
            path.write_text(yaml.dump(content, allow_unicode=True, default_flow_style=False), encoding="utf-8")
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def read(self, name: str) -> Any | None:
        """Read a deliverable. Returns parsed YAML dict or Markdown string."""
        for ext in (".yaml", ".md"):
            path = self._safe_path(name, ext)
            if path.exists():
                text = path.read_text(encoding="utf-8")
                if ext == ".yaml":
                    return yaml.safe_load(text)
                return text
        return None

    def list_available(self) -> list[str]:
        """List all available deliverable names (without extension)."""
        names = []
        for path in sorted(self._base.rglob("*")):
            if path.is_file() and path.suffix in (".yaml", ".md"):
                rel = path.relative_to(self._base)
                names.append(str(rel.with_suffix("")))
        return names
