"""Optional installed evaluator; standard standalone queries need no runtime package."""
from pathlib import Path

import yaml


def settings_for(work_dir=None, output_dir=None):
    try:
        from muse_runtime import resolve_settings
    except ModuleNotFoundError as exc:
        if exc.name != "muse_runtime":
            raise
        # Inspect only the same explicit workspace contract used by the installed runtime.
        work = Path(work_dir).resolve() if work_dir is not None else None
        if work is None and output_dir is not None:
            output = Path(output_dir).resolve()
            work = next((p.parent for p in (output, *output.parents) if p.name == "pipeline"), None)
        path = work / ".muse/runtime.yaml" if work is not None else None
        if path is not None and path.is_file():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                raise ValueError("无法读取作品模式配置") from None
            if not isinstance(data, dict) or data.get("mode", "standard") not in ("standard", "jev"):
                raise ValueError("作品 mode 须为 standard 或 jev")
            if data.get("mode") == "jev":
                raise ValueError("启用 JEV 需要在执行查询的 Python 环境安装 muse-runtime")
        return None
    return resolve_settings(work_dir, output_dir=output_dir)


def rank(settings, node, task, candidates, *, must=None, request_id=None):
    from muse_runtime.evaluation import rerank
    return rerank(settings, node, task, candidates, must=must, request_id=request_id)


def record(settings, node, status, **details):
    if settings is not None:
        from muse_runtime.config import record_event
        record_event(settings, node, status, **details)


def checked_must(must):
    if must is None:
        return []
    if not isinstance(must, (list, tuple)) or any(not isinstance(x, str) or not x.strip() for x in must):
        raise ValueError("每个 --must 须为非空必要条件")
    return list(dict.fromkeys(x.strip() for x in must))
