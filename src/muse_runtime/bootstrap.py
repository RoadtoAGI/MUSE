"""Snapshot an explicitly configured workbench default when creating a work."""
from __future__ import annotations

import os
from pathlib import Path

from .config import CONFIG_FILE, MODES, RuntimeConfigError, read_mapping, set_mode


def initialize_new_work(work_dir: str | Path) -> None:
    """Called only for newly created directories; queries never inherit this file."""
    template = os.environ.get("MUSE_NEW_WORK_TEMPLATE")
    work = Path(work_dir).resolve()
    if not template or (work / CONFIG_FILE).exists():
        return
    path = Path(template)
    if not path.is_absolute():
        raise RuntimeConfigError("MUSE_NEW_WORK_TEMPLATE 必须是绝对路径")
    data = read_mapping(path)
    if set(data) != {"mode"} or data["mode"] not in MODES:
        raise RuntimeConfigError("新作品模板仅支持 mode: standard|jev")
    set_mode(work, data["mode"])
