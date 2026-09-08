"""
KB 文风层标注（prepare/ingest 两段式；本脚本零 LLM 调用）。

语义标注由订阅原生会话（Claude Code subagent / Codex）完成——脚本只做确定性两端：
  --prepare  装配任务包（场景原文 + 字段说明 + 输出契约）落 JSON 文件
  --ingest   校验会话产出的标注文件，原子写回每书 scene_index.json

用法::

    python annotate_style_profile.py --prepare --novel 神雕 --limit 30 \
        --out tmp/annotation-tasks/style_profile.task.json
    # （订阅原生会话读任务包 → 产出标注文件，结构见任务包内 output_contract）
    python annotate_style_profile.py --ingest tmp/annotation-tasks/style_profile.out.json

写回点：每作品权威索引——novels 为 scene_index.json，dramas 为 dramatic_scene_index.jsonl
（并存时 JSONL 优先，legacy JSON 不写回；全局 embeddings 索引纯检索，不写）。
字段集按 medium 分叉（novel/drama 各 5 维），任务包内嵌对应 instructions。
prepare 默认只把缺 style_profile 的 entry 放进任务包（断点续标）；--force 重标。
ingest 逐条校验，拒收条目计入退出码（exit 1），已接受条目照常落盘。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import kb_index
except ImportError:
    import kb_index

KB_ROOT = Path(__file__).resolve().parent.parent  # knowledge-base/

MAX_SCENE_CHARS = 6000  # 任务包预览窗口；完整原文由 source_path 可达

PROFILE_FIELDS_BY_MEDIUM = {
    "novel": ["narration_voice", "diction", "rhetoric_density", "dialogue_mode", "pacing"],
    "drama": ["dialogue_voice", "diction", "rhetoric_density", "stage_direction_style", "pacing"],
}
PROFILE_FIELDS = PROFILE_FIELDS_BY_MEDIUM["novel"]
RHETORIC_ENUM = {"low", "medium", "high"}

INSTRUCTIONS_BY_MEDIUM = {
    "novel": """为 medium=novel 的场景生成 style_profile，5 个字段：

- narration_voice: 叙事语态一句话——全知说书 / 限知贴身 / 档案冷感 / 不可靠第一人称等定性 + 关键特征（如「叙述者是否直评人物」）
- diction: 词汇质地一句话——文白比例 / 口语度 / 时代感 / 修辞质地
- rhetoric_density: 只能取 low / medium / high——比喻、意象、通感的密度
- dialogue_mode: 对白形态一句话——对白推进还是叙述推进 / 归属方式（如「某某道」高频）/ 对白密度
- pacing: 节奏与留白一句话——句长节奏 / 段落呼吸 / 习惯省略什么

描述原作可观察的选择及成立条件，篇幅以解释清楚为准。缺某种表达时照实说明，不补造手法。text_truncated 为 true 时，预览只含开头；沿 source_path 回读会影响判断的后段，再概括本场。原作特征由采用者判断如何迁移，不写成无条件模仿命令。""",
    "drama": """为 medium=drama 的场景生成 style_profile，5 个字段：

- dialogue_voice: 台词声口一句话——身份化口语 / 诗化韵文 / 机锋攻防等定性 + 关键特征（如「人物声口是否按身份分层」）
- diction: 措辞质地一句话——文白雅俗 / 时代腔 / 翻译腔 / 韵散比例
- rhetoric_density: 只能取 low / medium / high——比喻、意象、双关的密度
- stage_direction_style: 舞台指示笔致一句话——小说化工笔 / 极简标记 / 抒情氛围 / 调度指令为主
- pacing: 节奏一句话——对白回合密度 / 独白停驻 / 上下场推进速度

描述原作可观察的选择、媒介约定与成立条件，篇幅以解释清楚为准。无舞台指示或某类表达时照实说明。text_truncated 为 true 时沿 source_path 回读有关后段，不用开头代表全场。原作特征由采用者判断如何迁移。""",
}


def iter_novel_indexes(novel_filter: str | None = None) -> list[Path]:
    """Return per-work authoritative index paths under novels/ and dramas/."""
    return kb_index.iter_work_indexes(KB_ROOT, novel_filter)


def load_index(index_path: Path) -> list[dict]:
    return kb_index.load_index(index_path)


def save_index(index_path: Path, index: list[dict]) -> None:
    kb_index.save_index(index_path, index)


def read_scene_text(novel_dir: Path, rel_file: str) -> str:
    text = (novel_dir / rel_file).read_text(encoding="utf-8")
    return text


def collect_todo(
    novel: str | None = None,
    scene_id: str | None = None,
    force: bool = False,
    limit: int = 10,
) -> list[tuple[Path, list[dict], dict]]:
    todo: list[tuple[Path, list[dict], dict]] = []
    for index_path in iter_novel_indexes(novel):
        index = load_index(index_path)
        for entry in index:
            if scene_id and entry.get("scene_id") != scene_id:
                continue
            if not force and entry.get("style_profile"):
                continue
            todo.append((index_path, index, entry))
            if len(todo) >= limit:
                return todo
    return todo


def validate_profile(profile: dict, medium: str = "novel") -> dict:
    fields = PROFILE_FIELDS_BY_MEDIUM[medium]
    missing = [f for f in fields if not profile.get(f)]
    if missing:
        raise ValueError(f"缺字段 {missing}（medium={medium}）")
    if profile["rhetoric_density"] not in RHETORIC_ENUM:
        raise ValueError(f"rhetoric_density 非法值: {profile['rhetoric_density']}")
    return {f: profile[f] for f in fields}


def find_index_path(novel: str) -> Path | None:
    """按作品名精确定位每作品权威索引（目录名全等）。"""
    return kb_index.find_index_path(KB_ROOT, novel)


def prepare(args: argparse.Namespace) -> int:
    todo = collect_todo(args.novel, args.scene_id, args.force, args.limit)
    if not todo:
        print("无待标注 entry（已全标注或过滤为空）")
        return 0
    entries = []
    mediums: set[str] = set()
    for index_path, _index, entry in todo:
        novel_dir = index_path.parent
        medium = kb_index.medium_of(index_path)
        mediums.add(medium)
        source_path = (novel_dir / entry["file"]).resolve()
        text = read_scene_text(novel_dir, entry["file"])
        entries.append(
            {
                "novel": novel_dir.name,
                "medium": medium,
                "scene_id": entry.get("scene_id"),
                "text": text[:MAX_SCENE_CHARS],
                "source_path": str(source_path),
                "text_truncated": len(text) > MAX_SCENE_CHARS,
            }
        )
    task = {
        "layer": "style_profile",
        "instructions": {m: INSTRUCTIONS_BY_MEDIUM[m] for m in sorted(mediums)},
        "output_contract": {
            "说明": "把标注产物写为一个 JSON 文件（UTF-8），结构如下；随后用 --ingest 校验写回。"
                  "style_profile 字段集按该 entry 的 medium 取对应 instructions",
            "annotated_by": "<执行标注的模型名>",
            "profiles": [
                {
                    "novel": "<与任务包一致>",
                    "scene_id": "<与任务包一致，原样照抄禁止改写格式>",
                    "style_profile": {f: "..." for f in PROFILE_FIELDS},
                }
            ],
        },
        "entries": entries,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"任务包已写入: {out}（{len(entries)} 场）")
    return 0


def ingest(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.ingest).read_text(encoding="utf-8"))
    annotated_by = data.get("annotated_by") or "unknown"
    items = data.get("profiles") or []
    if not items:
        print("[annotate INGEST_ERROR] 产出文件无 profiles", file=sys.stderr)
        return 2

    loaded: dict[Path, list[dict]] = {}
    touched: set[Path] = set()
    accepted = rejected = 0
    for item in items:
        novel, sid = item.get("novel"), item.get("scene_id")
        index_path = find_index_path(novel) if novel else None
        if index_path is None:
            print(f"  ✗ {novel}·{sid}: 找不到每书索引", file=sys.stderr)
            rejected += 1
            continue
        if index_path not in loaded:
            loaded[index_path] = load_index(index_path)
        entry = next((e for e in loaded[index_path] if e.get("scene_id") == sid), None)
        if entry is None:
            print(f"  ✗ {novel}·{sid}: 索引内无此 scene_id", file=sys.stderr)
            rejected += 1
            continue
        try:
            profile = validate_profile(item.get("style_profile") or {}, kb_index.medium_of(index_path))
        except ValueError as e:
            print(f"  ✗ {novel}·{sid}: {e}", file=sys.stderr)
            rejected += 1
            continue
        entry["style_profile"] = profile
        entry["style_profile_by"] = annotated_by
        touched.add(index_path)
        accepted += 1

    if not args.dry_run:
        for index_path in touched:
            save_index(index_path, loaded[index_path])
    print(f"接受 {accepted} / 拒收 {rejected}{'（dry-run 未写回）' if args.dry_run else ''}")
    return 0 if rejected == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="KB 文风层标注（prepare/ingest，零 LLM 调用）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="装配任务包")
    mode.add_argument("--ingest", type=str, metavar="FILE", help="校验并写回标注产出文件")
    parser.add_argument("--novel", type=str, default=None, help="书名子串过滤（prepare）")
    parser.add_argument("--scene-id", type=str, default=None, help="精确场景（prepare，需配 --novel）")
    parser.add_argument("--limit", type=int, default=10, help="任务包最多条数（prepare）")
    parser.add_argument("--force", action="store_true", help="重标已有 style_profile 的 entry（prepare）")
    parser.add_argument("--out", type=str, default="tmp/annotation-tasks/style_profile.task.json",
                        help="任务包输出路径（prepare）")
    parser.add_argument("--dry-run", action="store_true", help="ingest 只校验不写回")
    args = parser.parse_args()

    if args.prepare:
        return prepare(args)
    return ingest(args)


if __name__ == "__main__":
    sys.exit(main())
