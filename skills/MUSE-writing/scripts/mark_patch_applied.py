#!/usr/bin/env python3
"""
mark_patch_applied.py — reviser 成功后（status=complete）原子改名
pipeline/scene_{scene_id}/patch_directive.yaml → patch_directive.applied.yaml

幂等保证：dispatcher 按 patch_directive.yaml 存在性判定 PATCH 触发；改名后
rerun 同场景不会重触发 reviser。

status=partial 场景下**不调用**本脚本——reviser 自己 Edit patch_directive.yaml
移除已 applied 条目保留 not_applied 条目（下轮重试清单）。
status=failed / dispatch 失败场景下也**不调用**——走 ESCALATED 路径保留现状。

用法：
    python ${CLAUDE_PLUGIN_ROOT}/scripts/mark_patch_applied.py --scene-id S02 --work-dir <pipeline 根目录>

失败：
    - patch_directive.yaml 不存在 → stderr + exit 1（不 silent fallback）
    - patch_directive.applied.yaml 已存在（幂等冲突）→ stderr + exit 1

本脚本不调 LLM（原子 rename）。
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    pending = work_dir / "pipeline" / f"scene_{args.scene_id}" / "patch_directive.yaml"
    applied = work_dir / "pipeline" / f"scene_{args.scene_id}" / "patch_directive.applied.yaml"

    if not pending.exists():
        print(f"[mark_patch_applied] ERROR: {pending} not found", file=sys.stderr)
        return 1

    if applied.exists():
        print(
            f"[mark_patch_applied] ERROR: {applied} already exists "
            f"(幂等冲突——前一轮 applied 未清理？)",
            file=sys.stderr,
        )
        return 1

    pending.rename(applied)  # POSIX 原子 rename
    print(f"✅ marked applied: {pending} → {applied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
