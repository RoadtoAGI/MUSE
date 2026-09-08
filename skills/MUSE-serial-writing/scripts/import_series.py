#!/usr/bin/env python3
"""import_series.py — 接管导入 gate（serial-distill 出口 B 交付 → works root）

serial-distill 拆解出口 B 产出的交换格式交付物在进入创作循环前，须经本 gate 校验 +
迁移；产物定位为"经 import gate 才可用的交换格式交付物"，不是直接可写的工作区
（design §1）。

校验顺序（任一步失败即拒收，不落 --works-root 目标目录）：
  1. schema_version 窗口校验：递归扫描 --from 下全部 *.yaml，其中**顶层含
     `schema_version` 键**的每份都要求命中当前窗口 {1}；顶层缺该键的辅助 yaml
     （如 audit/skip_review.yaml）不参与校验——缺键不是版本漂移；命中更高/未知值
     → 拒收并提示升级 serial-distill（不静默降级、不尝试兼容读取）。
  2. 必备文件齐全（workspace-schema.md 权威路径）：
     series/series_state.yaml, series/story_bible.yaml,
     series/ledgers/{threads,world_facts}.yaml,
     published/manifest.yaml, series/volumes/ 下至少一个 V*.yaml。
     facts_current.yaml 是派生视图，不要求随交付——导入时在暂存目录重建
     （交付带了也会被重建覆盖，保证与台账一致）。
  3. published/ 与 manifest.entries 一一对应：manifest 登记的每个 file 都要在
     published/ 下找到对应 .md；published/ 下每个 .md 都要有 manifest 条目登记，
     禁止孤儿文件或孤儿登记；发布文件章 ID/卷号与卷纲唯一归属一致。
  4. 拷入临时暂存目录（works-root 同级文件系统，保证最终 rename 是原子操作）后，
     子进程在暂存目录上跑 `serial_lint.py --check all`；PASS 才 rename 暂存目录
     为最终工作区（`--works-root/<work_slug>/`，slug 取自 series_state.yaml 的
     `work_slug` 字段）；FAIL 则丢弃暂存目录，目标目录始终不出现半成品。

用法：
    python3 import_series.py --from <serial-distill 出口 B 交付目录> --works-root works/

stdout 末行输出最终工作区绝对路径。

退出码：
    0 — 接管导入完成
    1 — 数据错：既有 YAML 解析失败
    2 — 阻断：--from 不存在 / schema_version 超出窗口 / 必备文件缺失 /
        published↔manifest 不一致 / 目标工作区已存在 / serial_lint --check all 未通过
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCHEMA_WINDOW = {1}

REQUIRED_RELATIVE_FILES = [
    Path("series/series_state.yaml"),
    Path("series/story_bible.yaml"),
    Path("series/ledgers/threads.yaml"),
    Path("series/ledgers/world_facts.yaml"),
    Path("published/manifest.yaml"),
]


class UsageError(Exception):
    """阻断性前置条件不满足：交付物结构/版本/一致性不合法。"""


class DataError(Exception):
    """既有 YAML 内容解析失败。"""


# ---------------------------------------------------------------------------
# 通用 IO（自含，风格仿 ledger_tools.py）
# ---------------------------------------------------------------------------


def load_yaml_or_none(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


def run_subprocess(cmd: list[str], label: str) -> int:
    result = subprocess.run(cmd, capture_output=True, text=True)
    for stream in (result.stdout, result.stderr):
        if stream:
            sys.stderr.write(f"[{label}] " + (stream if stream.endswith("\n") else stream + "\n"))
    return result.returncode


# ---------------------------------------------------------------------------
# 校验步骤
# ---------------------------------------------------------------------------


def check_schema_versions(from_dir: Path) -> None:
    for yml in sorted(from_dir.rglob("*.yaml")):
        data = load_yaml_or_none(yml)
        if not isinstance(data, dict) or "schema_version" not in data:
            # 顶层无 schema_version 键的 yaml（辅助文件，如 audit/skip_review.yaml）
            # 不参与窗口校验——缺键不视为版本漂移
            continue
        version = data["schema_version"]
        if version in SCHEMA_WINDOW:
            continue
        if isinstance(version, int) and version > max(SCHEMA_WINDOW):
            raise UsageError(
                f"{yml}: schema_version={version} 超出当前支持窗口 {sorted(SCHEMA_WINDOW)}，"
                "请升级 serial-distill 后重新拆解出口 B 交付物"
            )
        raise UsageError(
            f"{yml}: schema_version={version!r} 不在当前支持窗口 {sorted(SCHEMA_WINDOW)}"
        )


def check_required_files(from_dir: Path) -> None:
    missing = [str(rel) for rel in REQUIRED_RELATIVE_FILES if not (from_dir / rel).is_file()]
    volumes_dir = from_dir / "series" / "volumes"
    if not (volumes_dir.is_dir() and any(volumes_dir.glob("V*.yaml"))):
        missing.append("series/volumes/V*.yaml（至少一个卷纲文件）")
    if missing:
        raise UsageError(f"必备文件缺失: {missing}")


def check_manifest_published_consistency(from_dir: Path) -> None:
    manifest = load_yaml_or_none(from_dir / "published" / "manifest.yaml") or {}
    entries = manifest.get("entries") or []
    entry_files = {e.get("file") for e in entries if isinstance(e, dict) and e.get("file")}

    published_dir = from_dir / "published"
    actual_files = {p.name for p in published_dir.glob("*.md")} if published_dir.is_dir() else set()

    missing_on_disk = sorted(entry_files - actual_files)
    orphan_files = sorted(actual_files - entry_files)
    if missing_on_disk or orphan_files:
        raise UsageError(
            "published/ 与 manifest.entries 不一一对应："
            f"manifest 登记但文件缺失={missing_on_disk}，文件存在但 manifest 未登记={orphan_files}"
        )
    chapter_volumes: dict[str, list[str]] = {}
    for path in sorted((from_dir / "series" / "volumes").glob("V*.yaml")):
        volume = load_yaml_or_none(path) or {}
        for chapter in volume.get("chapters") or []:
            if isinstance(chapter, dict) and chapter.get("chapter_id"):
                chapter_volumes.setdefault(chapter["chapter_id"], []).append(volume.get("volume_id") or path.stem)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        match = re.fullmatch(r"(V\d+)(C\d+)\.md", str(entry.get("file", "")))
        cid = entry.get("chapter_id")
        if not match or match.group(2) != cid or chapter_volumes.get(cid) != [match.group(1)]:
            raise UsageError(f"manifest 章 {cid}: 发布文件卷号与卷纲所属卷不一致或章条目缺失/重复")


def resolve_slug(from_dir: Path) -> str:
    state = load_yaml_or_none(from_dir / "series" / "series_state.yaml") or {}
    slug = state.get("work_slug")
    if not slug:
        raise UsageError("series/series_state.yaml 缺 work_slug，无法确定目标工作区目录名")
    return slug


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run(from_dir: Path, works_root: Path, script_dir: Path) -> int:
    if not from_dir.is_dir():
        raise UsageError(f"--from 不存在或不是目录: {from_dir}")
    if works_root.resolve().is_relative_to(from_dir.resolve()):
        raise UsageError(
            "--works-root 必须在 --from 交付目录之外；目标位于源目录内会递归复制自身"
        )

    check_schema_versions(from_dir)
    check_required_files(from_dir)
    check_manifest_published_consistency(from_dir)

    slug = resolve_slug(from_dir)
    works_root.mkdir(parents=True, exist_ok=True)
    dest = works_root / slug
    if dest.exists():
        raise UsageError(f"目标工作区已存在: {dest}")

    staging = Path(tempfile.mkdtemp(prefix=f".import-{slug}-", dir=str(works_root)))
    try:
        shutil.copytree(from_dir, staging, dirs_exist_ok=True)

        # facts_current 派生视图由导入方重建（拆解侧不携带重建算法，防跨包漂移）
        rc = run_subprocess(
            [sys.executable, str(script_dir / "ledger_tools.py"),
             "rebuild-current", "--work-dir", str(staging)],
            "ledger_tools rebuild-current",
        )
        if rc != 0:
            raise DataError("facts_current 派生视图重建失败——检查 world_facts.yaml 台账数据")

        rc = run_subprocess(
            [sys.executable, str(script_dir / "serial_lint.py"),
             "--work-dir", str(staging), "--check", "all"],
            "serial_lint",
        )
        if rc == 1:
            raise DataError("serial_lint --check all 数据错（exit 1），拒收导入")
        if rc != 0:
            raise UsageError(f"serial_lint --check all 未通过（exit {rc}），拒收导入")

        staging.rename(dest)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise

    print(f"[import_series] 接管导入完成: {dest}", file=sys.stderr)
    print(dest)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--from", dest="from_dir", required=True, type=Path,
        help="serial-distill 出口 B 交付目录（交换格式，非直接可写工作区）",
    )
    parser.add_argument("--works-root", required=True, type=Path, help="目标 works 根目录")
    args = parser.parse_args()

    from_dir: Path = args.from_dir.resolve()
    works_root: Path = args.works_root.resolve()
    script_dir = Path(__file__).resolve().parent

    try:
        return run(from_dir, works_root, script_dir)
    except UsageError as exc:
        print(f"[import_series ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[import_series ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
