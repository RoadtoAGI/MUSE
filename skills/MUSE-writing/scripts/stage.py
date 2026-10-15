#!/usr/bin/env python3
"""stage.py：常驻角色进程的实况演出舞台。

主控按 live-staging 技能的协议调用本脚本。舞台唤醒角色进程（Claude Code 或 Codex
的会话），随唤醒送去该人物此刻能感知的事，把回复解析成回合，按可见性路由、归档；
需要判断的事（谁登场、注入什么事件、何时收场、偏差怎么处理）都由主控决定。

子命令（都在作品目录 WORK_DIR 下操作，输出 JSON 到 stdout）：

    open      按 setup.yaml 开场：补名册、送场外补记；--reperform 重演一场
    run       连续演出到暂停点；--next 指定下一行动者，--extend 追加回合上限
    event     注入世界事件（setup 里的 id 或 --text）
    enter     迟到者登场，--view 写他登场时看到的场面
    close     收场，向每个参与者收日记
    line      索句：重建某回合时点的人物，补一回合，记为 kind: line
    invalidate  改变事实后作废该场日记与相关会话，后续已演场景标待核
    amend     作废后改正实况记录的某一条
    rediary   作废后按改正的记录重建人物、重写日记
    review    主控判断待核场景不受影响时解除待核
    narrate   从 POV 人物的会话分叉，讲述这一场（A/B 的分叉叙述一臂）
    interview 试演收场后分叉一个人物，出戏回答设计负责人的问题
    status    舞台与名册概况
    show      按回合渲染实况记录（全知视角，给主控看）
    check-isolation  在临时目录里核验某宿主的角色会话读不到外部文件

文件：
    pipeline/stage/roster.yaml                 名册（舞台写）
    pipeline/stage/scene_{id}/setup.yaml       主控写
    pipeline/stage/scene_{id}/transcript.yaml  实况记录（舞台写）
    pipeline/stage/scene_{id}/log.yaml         调度、调用、干预与失效记录（舞台写）
    人物目录 diary/{entry}.md                   日记（舞台按人物回复写入）
    pipeline/stage/tryout/{name}/               试演：setup、实况记录、日志、试演名册、意图探针与访谈

open、run、event、enter、close、show 用 --tryout NAME 代替 --scene-id 时操作试演：人物从正式
会话分叉（没有可用的正式会话时按日记重建），收场做意图探针，不写日记，也不改正式名册。

退出码：0 成功（含正常暂停）；1 输入或状态错误；2 宿主调用失败。
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
FRAME_FILE = PACKAGE_ROOT / "skills" / "live-staging" / "references" / "role-frame.md"

EXIT_INPUT = 1
EXIT_HOST = 2

ALL_PRESENT = "all_present"


class StageError(Exception):
    """输入或舞台状态错误，主控需要改输入或换操作。"""


class DriverError(Exception):
    """宿主调用失败。category: transient / missing_session / fatal。"""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


# ---------------------------------------------------------------- IO

def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return default if data is None else data


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def write_yaml(path: Path, data: Any) -> None:
    write_text_atomic(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100))


@contextlib.contextmanager
def stage_lock(stage_dir: Path):
    """同一作品同时只有一个改动舞台状态的命令。"""
    stage_dir.mkdir(parents=True, exist_ok=True)
    with open(stage_dir / ".lock", "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StageError("另一个舞台命令正在这个作品上运行；等它结束再操作") from exc
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------- paths

@dataclass
class Work:
    root: Path

    @property
    def pipeline(self) -> Path:
        return self.root / "pipeline"

    @property
    def stage(self) -> Path:
        return self.pipeline / "stage"

    @property
    def roster_path(self) -> Path:
        return self.stage / "roster.yaml"

    def scene_dir(self, scene: str) -> Path:
        return self.stage / f"scene_{scene}"

    def setup_path(self, scene: str) -> Path:
        return self.scene_dir(scene) / "setup.yaml"

    def transcript_path(self, scene: str) -> Path:
        return self.scene_dir(scene) / "transcript.yaml"

    def log_path(self, scene: str) -> Path:
        return self.scene_dir(scene) / "log.yaml"

    def room(self, slug: str) -> Path:
        return self.pipeline / "story-character-skills" / ".claude" / "skills" / slug

    def diary_path(self, slug: str, entry: str) -> Path:
        return self.room(slug) / "diary" / f"{entry}.md"

    def role_view_path(self, scene: str, slug: str) -> Path:
        return self.pipeline / f"scene_{scene}" / "role_views" / f"{slug}.yaml"

    def offstage_path(self, scene: str, slug: str) -> Path:
        return self.pipeline / f"scene_{scene}" / "offstage" / f"{slug}.md"

    def tryout_dir(self, name: str) -> Path:
        return self.stage / "tryout" / name

    def space_dir(self, name: str, tryout: bool) -> Path:
        return self.tryout_dir(name) if tryout else self.scene_dir(name)

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)


# ---------------------------------------------------------------- role-facing text

def load_frames(path: Path = FRAME_FILE) -> dict[str, dict[str, str]]:
    """读 role-frame.md：`## zh` / `## en` 下每个 `### key` 后的第一个 text 代码块。"""
    lang = None
    key = None
    frames: dict[str, dict[str, str]] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            lang, key = line[3:].strip(), None
            frames.setdefault(lang, {})
        elif line.startswith("### ") and lang:
            key = line[4:].strip()
        elif line.strip() == "```text" and lang and key:
            block = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                block.append(lines[i])
                i += 1
            frames[lang][key] = "\n".join(block)
            key = None
        i += 1
    return frames


class Voice:
    """按作品语言取舞台用语。"""

    def __init__(self, lang: str, frames: dict[str, dict[str, str]] | None = None):
        frames = frames or load_frames()
        if lang not in frames:
            raise StageError(f"角色框架里没有语言 {lang}")
        self.lang = lang
        self.t = frames[lang]

    def __call__(self, key: str, **kw: Any) -> str:
        if key not in self.t:
            raise StageError(f"角色框架缺少 {self.lang}/{key}")
        return self.t[key].format(**kw)

    def join_labels(self, labels: list[str]) -> str:
        return ("、" if self.lang == "zh" else ", ").join(labels)


def work_language(work: Work, override: str | None) -> str:
    """作品语言：run_state 写了就用；没写时看 Phase 0 构想，拉丁字母明显多于汉字即英文作品。"""
    if override:
        return override
    state = read_yaml(work.pipeline / "run_state.yaml", {}) or {}
    lang = str(state.get("language") or "").lower()
    if lang:
        return "en" if lang.startswith("en") else "zh"
    phase0 = work.pipeline / "phase0_conception.yaml"
    sample = phase0.read_text(encoding="utf-8")[:20000] if phase0.exists() else ""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    return "en" if latin > 3 * cjk else "zh"


_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def clean_persona(text: str) -> str:
    """角色包正文：去 frontmatter 与构建注释，人物不需要看到来源标注。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    text = _COMMENT_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_state(text: str) -> str:
    """入场状态：去构建注释与写给流水线读者的引用说明行。"""
    text = _COMMENT_RE.sub("", text)
    kept = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


# ---------------------------------------------------------------- names and labels

def display_name(work: Work, slug: str) -> str:
    meta = read_yaml(work.room(slug) / "build-meta.yaml", {}) or {}
    return str(meta.get("character_display_name") or slug)


@dataclass
class Cast:
    """一场里的人名：显示名与 known_as 称呼。"""
    names: dict[str, str]
    known_as: dict[str, dict[str, str]]

    def label(self, observer: str | None, other: str) -> str:
        if observer:
            custom = (self.known_as.get(observer) or {}).get(other)
            if custom:
                return str(custom)
        return self.names.get(other, other)

    def labels(self, observer: str | None, others: list[str]) -> list[str]:
        return [self.label(observer, o) for o in others]


ALL_WORDS = {"在场所有人", "所有人", "大家", "全场", "在场的人", "所有在场的人", "众人",
             "everyone", "everyone present", "all", "all present", "all_present", "everybody"}
NONE_WORDS = {"无人", "没人", "没有人", "无", "none", "no one", "nobody", "no-one"}
SELF_WORDS = {"你", "自己", "我", "myself", "me", "you"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().strip("。.!！，,")).lower()


def resolve_one(token: str, actor: str | None, candidates: list[str], cast: Cast) -> str | None:
    tok = _norm(token)
    if not tok:
        return None
    names: dict[str, set[str]] = {}
    for c in candidates:
        variants = {c, cast.names.get(c, c), cast.label(actor, c)}
        names[c] = {_norm(v) for v in variants if v}
    exact = [c for c, vs in names.items() if tok in vs]
    if len(exact) == 1:
        return exact[0]
    if len(tok) >= 2:
        partial = [c for c, vs in names.items()
                   if any(len(v) >= 2 and (tok in v or v in tok) for v in vs)]
        if len(partial) == 1:
            return partial[0]
    return None


_SPLIT_MAIN = re.compile(r"[、，,;；/\n]|\s+and\s+|\s*&\s*")
_SPLIT_CJK = re.compile(r"[和与及跟]")


def resolve_audience(value: str | None, actor: str, present: list[str], cast: Cast
                     ) -> tuple[list[str] | None, list[str]]:
    """把闻/见写法映射到 slug 列表。返回 (slug 列表, 对不上的写法)。"""
    others = [p for p in present if p != actor]
    if value is None or not value.strip() or _norm(value) in ALL_WORDS:
        return list(others), []
    if _norm(value) in NONE_WORDS:
        return [], []
    lines = [ln for ln in value.splitlines() if ln.strip()]
    if len(lines) > 1:
        # 同一回合对不同的人各说一段时会写几次【闻】【见】：逐行解析后合并
        found: list[str] = []
        bad: list[str] = []
        for ln in lines:
            hit, miss = resolve_audience(ln, actor, present, cast)
            found += hit
            bad += miss
        return [p for p in others if p in found], bad
    whole = resolve_one(value, actor, others, cast)
    if whole:
        return [whole], []
    found: list[str] = []
    bad: list[str] = []
    for part in [p for p in _SPLIT_MAIN.split(value) if p.strip()]:
        if _norm(part) in ALL_WORDS:
            return list(others), []
        hit = resolve_one(part, actor, others, cast)
        if hit:
            found.append(hit)
            continue
        sub = [s for s in _SPLIT_CJK.split(part) if s.strip()]
        subhits = [resolve_one(s, actor, others, cast) for s in sub]
        if len(sub) > 1 and all(subhits):
            found.extend(h for h in subhits if h)
        else:
            bad.append(part.strip())
    ordered = [p for p in others if p in found]
    return ordered, bad


# ---------------------------------------------------------------- turn parsing

TAG_KEYS = {"做": "do", "说": "say", "对": "to", "闻": "heard", "见": "seen", "想": "think",
            "静": "wait", "离": "leave", "DO": "do", "SAY": "say", "TO": "to", "HEARD": "heard",
            "SEEN": "seen", "THINK": "think", "WAIT": "wait", "LEAVE": "leave"}
_TAG_RE = re.compile(
    r"^(?:【\s*(做|说|对|闻|见|想|静|离)\s*】|\[\s*(DO|SAY|TO|HEARD|SEEN|THINK|WAIT|LEAVE)\s*\])"
    r"\s*[:：]?\s*(.*)$", re.I)
_QUOTES = [("“", "”"), ("\"", "\""), ("「", "」"), ("『", "』"), ("'", "'")]


_PARAGRAPH_QUOTES = re.compile(r'[”"」』]\s*\n\s*[“"「『]')


def _strip_quotes(s: str) -> str:
    """去掉台词外层引号；分段写的台词，段与段之间的引号也去掉。"""
    s = s.strip()
    for left, right in _QUOTES:
        if len(s) >= 2 and s.startswith(left) and s.endswith(right):
            s = s[len(left):-len(right)].strip()
            break
    return _PARAGRAPH_QUOTES.sub("\n", s)


def split_marks(text: str) -> tuple[dict[str, str], str]:
    """把回复切成 {标记: 内容}；返回值第二项是标记之外的文字。"""
    parts: dict[str, list[str]] = {}
    stray: list[str] = []
    current: str | None = None
    for raw in text.splitlines():
        line = re.sub(r"^[\s>*•\-]+", "", raw).replace("**", "").rstrip()
        m = _TAG_RE.match(line)
        if m:
            tag = m.group(1) or m.group(2).upper()
            current = TAG_KEYS[tag]
            parts.setdefault(current, [])
            if m.group(3).strip():
                parts[current].append(m.group(3).strip())
        elif current and line.strip():
            parts[current].append(line.strip())
        elif line.strip():
            stray.append(line.strip())
    return {k: "\n".join(v).strip() for k, v in parts.items()}, "\n".join(stray)


@dataclass
class ParsedTurn:
    entry: dict[str, Any] | None
    problem: str | None = None
    dropped_inner: str | None = None
    stray: str | None = None


def parse_turn(text: str, actor: str, present: list[str], pov: str | None,
               cast: Cast, voice: Voice) -> ParsedTurn:
    marks, stray = split_marks(text)
    does = marks.get("do") or ""
    says = _strip_quotes(marks.get("say") or "")
    leaves = "leave" in marks
    silent = "wait" in marks
    if leaves and marks.get("leave"):
        does = "\n".join(x for x in (does, marks["leave"]) if x)
    if silent and marks.get("wait"):
        does = "\n".join(x for x in (does, marks["wait"]) if x)
    if does or says:
        silent = False
    if not (does or says or silent or leaves):
        return ParsedTurn(None, voice("prob_empty"), stray=stray or None)
    others = [p for p in present if p != actor]
    heard, bad_h = resolve_audience(marks.get("heard"), actor, present, cast)
    seen, bad_s = resolve_audience(marks.get("seen"), actor, present, cast)
    bad = bad_h + bad_s
    if bad:
        return ParsedTurn(None, voice("prob_label", token=bad[0],
                                      labels=voice.join_labels(cast.labels(actor, others))))
    entry: dict[str, Any] = {"kind": "turn", "actor": actor}
    if does:
        entry["does"] = does
    if says:
        entry["says"] = says
    to_raw = marks.get("to")
    if to_raw and _norm(to_raw) not in ALL_WORDS | SELF_WORDS:
        target = resolve_one(to_raw, actor, others, cast)
        if target:
            entry["to"] = target
        else:
            # "对裴相，再对温昭"之类：取第一个对得上的人做被问者，原话留给 writer
            target = next((hit for part in _SPLIT_MAIN.split(to_raw)
                           if (hit := resolve_one(part, actor, others, cast))), None)
            if target:
                entry["to"] = target
            entry["to_text"] = to_raw
    entry["heard_by"] = heard
    entry["seen_by"] = seen
    dropped = None
    if marks.get("think"):
        if actor == pov:
            entry["inner"] = marks["think"]
        else:
            dropped = marks["think"]
    if silent:
        entry["silent"] = True
    if leaves:
        entry["leaves"] = True
    return ParsedTurn(entry, None, dropped, stray or None)


# ---------------------------------------------------------------- transcript

def new_transcript(scene: str, take: int, pov: str | None) -> dict[str, Any]:
    return {"scene_id": scene, "take": take, "pov": pov, "turns": []}


def next_n(transcript: dict[str, Any]) -> int:
    return max((e["n"] for e in transcript["turns"]), default=0) + 1


def add_entry(transcript: dict[str, Any], entry: dict[str, Any], after: int | None = None) -> dict[str, Any]:
    entry = {"n": next_n(transcript), **entry}
    turns = transcript["turns"]
    if after is None:
        turns.append(entry)
    else:
        idx = next((i for i, e in enumerate(turns) if e["n"] == after), None)
        if idx is None:
            raise StageError(f"实况记录里没有第 {after} 条")
        turns.insert(idx + 1, entry)
    return entry


def entry_at(transcript: dict[str, Any], n: int) -> dict[str, Any]:
    for e in transcript["turns"]:
        if e["n"] == n:
            return e
    raise StageError(f"实况记录里没有第 {n} 条")


def performance(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    """演出中实际发生的条目（索句不在演出时间线上）。"""
    return [e for e in transcript["turns"] if e.get("kind") != "line"]


def present_at(setup: dict[str, Any], transcript: dict[str, Any], upto: int | None = None) -> list[str]:
    present = list(setup.get("present") or [])
    for e in performance(transcript):
        if upto is not None and e["n"] > upto:
            break
        if e.get("kind") == "enter" and e["actor"] not in present:
            present.append(e["actor"])
        if e.get("kind") == "turn" and e.get("leaves") and e["actor"] in present:
            present.remove(e["actor"])
    return present


def ever_present(setup: dict[str, Any], transcript: dict[str, Any]) -> list[str]:
    seen = list(setup.get("present") or [])
    for e in performance(transcript):
        if e.get("kind") == "enter" and e["actor"] not in seen:
            seen.append(e["actor"])
    return seen


def entered_at(transcript: dict[str, Any], slug: str) -> dict[str, Any] | None:
    for e in performance(transcript):
        if e.get("kind") == "enter" and e["actor"] == slug:
            return e
    return None


def perceives(e: dict[str, Any], slug: str) -> bool:
    kind = e.get("kind")
    if kind in ("turn", "line"):
        if e["actor"] == slug:
            return True
        return slug in (e.get("heard_by") or []) or slug in (e.get("seen_by") or [])
    if kind == "event":
        return slug in (e.get("perceived_by") or [])
    if kind == "enter":
        return e["actor"] == slug or slug in (e.get("perceived_by") or [])
    return False


# ---------------------------------------------------------------- rendering for a character

def render_for(e: dict[str, Any], slug: str, cast: Cast, voice: Voice) -> list[str]:
    """一条记录在 slug 眼里是什么样；不能感知时返回空。"""
    kind = e.get("kind")
    if kind == "event":
        return [e["text"]] if slug in (e.get("perceived_by") or []) else []
    if kind == "enter":
        if e["actor"] == slug:
            return []
        if slug not in (e.get("perceived_by") or []):
            return []
        return [e.get("arrival") or voice("ev_enter", actor=cast.label(slug, e["actor"]))]
    if kind not in ("turn", "line"):
        return []
    if e["actor"] == slug:
        return _render_self(e, slug, cast, voice)
    return _render_other(e, slug, cast, voice)


def _to_phrase(e: dict[str, Any], observer: str, cast: Cast, voice: Voice) -> str:
    target = e.get("to")
    if not target:
        return ""
    if target == observer:
        return voice("ev_to_you")
    return voice("ev_to_other", target=cast.label(observer, target))


def _render_self(e: dict[str, Any], slug: str, cast: Cast, voice: Voice) -> list[str]:
    out = []
    if e.get("does"):
        out.append(voice("self_do", text=e["does"]))
    if e.get("says"):
        out.append(voice("self_say", to=_to_phrase(e, slug, cast, voice), text=e["says"]))
    if e.get("silent"):
        out.append(voice("self_silent"))
    return out


def _render_other(e: dict[str, Any], slug: str, cast: Cast, voice: Voice) -> list[str]:
    hear = slug in (e.get("heard_by") or [])
    see = slug in (e.get("seen_by") or [])
    actor = cast.label(slug, e["actor"])
    to = _to_phrase(e, slug, cast, voice)
    out = []
    if see and e.get("does"):
        out.append(voice("ev_do", actor=actor, text=e["does"]))
    if e.get("says"):
        if hear and see:
            out.append(voice("ev_say", actor=actor, to=to, text=e["says"]))
        elif hear:
            out.append(voice("ev_heard_only", actor=actor, text=e["says"]))
        elif see:
            out.append(voice("ev_masked", actor=actor, to=to))
    if see and e.get("silent"):
        out.append(voice("ev_silent", actor=actor))
    if see and e.get("leaves"):
        out.append(voice("ev_leave", actor=actor))
    return out


def bullet(lines: list[str]) -> str:
    return "\n".join(f"- {ln}" for ln in lines)


def opening_block(work: Work, scene: str, slug: str, setup: dict[str, Any],
                  transcript: dict[str, Any], voice: Voice) -> str:
    view = read_yaml(work.role_view_path(scene, slug), None)
    if view is None:
        raise StageError(f"缺少 {work.rel(work.role_view_path(scene, slug))}；先派 role-brief-deriver")
    parts = []
    entry = entered_at(transcript, slug)
    if entry is not None:
        parts.append(voice("entry_header") + "\n" + entry["view"].strip())
    else:
        cues = [str(c.get("cue") if isinstance(c, dict) else c)
                for c in (view.get("observable_stimuli") or [])]
        if cues:
            parts.append(voice("now_header") + "\n" + bullet(cues))
    if view.get("constraints_now"):
        parts.append(voice("situation_header") + "\n" + bullet([str(x) for x in view["constraints_now"]]))
    if view.get("known_now"):
        parts.append(voice("known_header") + "\n" + bullet([str(x) for x in view["known_now"]]))
    if slug == setup.get("pov"):
        parts.append(voice("pov_note"))
    return "\n\n".join(parts)


# ---------------------------------------------------------------- hosts and drivers

CALL_TIMEOUT = 900
# 过载、限流、网络中断属于瞬时错误：等一会儿再试同一请求即可恢复（world-sim 实况运行里
# 529 在第二次就过了）。其余错误原样上报，由主控决定。
TRANSIENT_WAITS = (20, 60)
_TRANSIENT_RE = re.compile(r"overload|\b529\b|rate.?limit|\b429\b|timed? ?out|ECONNRESET|\b50[23]\b|"
                           r"socket hang up|temporarily unavailable", re.I)
_MISSING_RE = re.compile(r"no conversation found|session .*not found|thread .*not found|"
                         r"no rollout found|could not find (?:session|thread)", re.I)


def classify(message: str) -> str:
    if _MISSING_RE.search(message or ""):
        return "missing_session"
    if _TRANSIENT_RE.search(message or ""):
        return "transient"
    return "fatal"


@dataclass
class RoleSpec:
    slug: str
    host: str
    model: str
    effort: str | None
    cwd: Path
    name: str


@dataclass
class Reply:
    text: str
    session_id: str | None
    seconds: float
    usage: dict[str, Any] = field(default_factory=dict)
    cost: float | None = None


def _retrying(fn: Callable[[], Reply]) -> Reply:
    for wait in (*TRANSIENT_WAITS, None):
        try:
            return fn()
        except DriverError as exc:
            if exc.category != "transient" or wait is None:
                raise
            time.sleep(wait)
    raise AssertionError("unreachable")


class ClaudeDriver:
    """claude -p：无工具、safe-mode、自定义系统提示。消息走 stdin。"""

    def _run(self, spec: RoleSpec, args: list[str], system: str, message: str) -> Reply:
        cmd = ["claude", "-p", "--output-format", "json", "--model", spec.model,
               "--tools", "", "--safe-mode", "--system-prompt", system, *args]
        if spec.effort:
            cmd += ["--effort", spec.effort]
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, input=message, capture_output=True, text=True,
                                  cwd=spec.cwd, timeout=CALL_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise DriverError("transient", f"claude 调用超时 {CALL_TIMEOUT}s") from exc
        seconds = round(time.monotonic() - start, 1)
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            text = (proc.stderr or proc.stdout or "").strip()[-800:]
            raise DriverError(classify(text), f"claude 输出无法解析：{text}") from None
        if proc.returncode != 0 or data.get("is_error"):
            text = str(data.get("result") or proc.stderr or data.get("subtype") or "")[-800:]
            raise DriverError(classify(text), f"claude 调用失败：{text}")
        usage = data.get("usage") or {}
        return Reply(text=str(data.get("result") or ""), session_id=data.get("session_id"),
                     seconds=seconds, cost=data.get("total_cost_usd"),
                     usage={k: usage.get(k) for k in ("input_tokens", "output_tokens",
                                                      "cache_read_input_tokens",
                                                      "cache_creation_input_tokens")})

    def spawn(self, spec: RoleSpec, system: str, message: str) -> Reply:
        sid = str(uuid.uuid4())
        args = ["--session-id", sid, "-n", spec.name]
        reply = _retrying(lambda: self._run(spec, args, system, message))
        reply.session_id = reply.session_id or sid
        return reply

    def resume(self, spec: RoleSpec, sid: str, system: str, message: str) -> Reply:
        return _retrying(lambda: self._run(spec, ["--resume", sid], system, message))

    def fork(self, spec: RoleSpec, sid: str, system: str, message: str) -> Reply:
        return _retrying(lambda: self._run(spec, ["--resume", sid, "--fork-session"], system, message))


CODEX_ROLE_CONFIG = """\
# MUSE 角色进程专用 Codex 配置：没有 shell、技能说明、插件、记忆与网页搜索，
# 不读 AGENTS.md 与环境信息。由 stage.py 维护，改动会被覆盖。
approval_policy = "never"
sandbox_mode = "read-only"
web_search = "disabled"
project_doc_max_bytes = 0
include_permissions_instructions = false
include_environment_context = false
include_apps_instructions = false
include_collaboration_mode_instructions = false

[analytics]
enabled = false

[skills]
include_instructions = false

[tools.update_plan]
enabled = false

[features]
shell_tool = false
unified_exec = false
multi_agent = false
multi_agent_v2 = false
apps = false
plugins = false
memories = false
image_generation = false
browser_use = false
computer_use = false
in_app_browser = false
view_image = false
skill_search = false
goals = false
sleep_tool = false
tool_suggest = false
code_mode_host = false
current_time_reminder = false
hooks = false
"""


def codex_main_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()


def codex_role_home() -> Path:
    return Path(os.environ.get("MUSE_CODEX_ROLE_HOME") or "~/.muse/codex-role-home").expanduser()


def ensure_codex_role_home() -> Path:
    home = codex_role_home()
    home.mkdir(parents=True, exist_ok=True)
    cfg = home / "config.toml"
    if not cfg.exists() or cfg.read_text(encoding="utf-8") != CODEX_ROLE_CONFIG:
        write_text_atomic(cfg, CODEX_ROLE_CONFIG)
    auth = home / "auth.json"
    main_auth = codex_main_home() / "auth.json"
    if not auth.exists() and not auth.is_symlink():
        if not main_auth.exists():
            raise StageError(f"找不到 Codex 认证文件 {main_auth}；先在 Codex 登录")
        auth.symlink_to(main_auth)
    return home


def codex_default_model() -> str:
    import tomllib
    cfg = codex_main_home() / "config.toml"
    if cfg.exists():
        model = tomllib.loads(cfg.read_text(encoding="utf-8")).get("model")
        if model:
            return str(model)
    raise StageError("本机 Codex 配置里没有 model；在名册里为该人物写明 model")


class CodexDriver:
    """codex exec：专用 CODEX_HOME，基础指令换成角色框架。消息走 stdin。"""

    def _run(self, spec: RoleSpec, cmd: list[str], message: str) -> Reply:
        env = dict(os.environ, CODEX_HOME=str(ensure_codex_role_home()))
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, input=message, capture_output=True, text=True,
                                  cwd=spec.cwd, env=env, timeout=CALL_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise DriverError("transient", f"codex 调用超时 {CALL_TIMEOUT}s") from exc
        seconds = round(time.monotonic() - start, 1)
        return self._parse(proc, seconds)

    @staticmethod
    def _parse(proc: subprocess.CompletedProcess, seconds: float) -> Reply:
        thread, text, usage, failure = None, None, {}, None
        # --json 输出里夹着非事件的提示行，只解析以 { 开头的事件行
        for line in (proc.stdout or "").splitlines():
            if not line.lstrip().startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DriverError("fatal", f"codex 输出无法解析：{line[:200]}") from exc
            kind = ev.get("type")
            if kind == "thread.started":
                thread = ev.get("thread_id")
            elif kind == "item.completed" and (ev.get("item") or {}).get("type") == "agent_message":
                text = ev["item"].get("text") or ""
            elif kind == "turn.completed":
                usage = ev.get("usage") or {}
            elif kind in ("turn.failed", "error"):
                err = ev.get("error") or ev.get("message") or ev
                failure = err.get("message") if isinstance(err, dict) else str(err)
        if failure or proc.returncode != 0 or text is None:
            detail = failure or (proc.stderr or "").strip()[-800:] or "没有回复"
            raise DriverError(classify(detail), f"codex 调用失败：{detail}")
        return Reply(text=text, session_id=thread, seconds=seconds,
                     usage={"input_tokens": usage.get("input_tokens"),
                            "output_tokens": usage.get("output_tokens"),
                            "cache_read_input_tokens": usage.get("cached_input_tokens")})

    @staticmethod
    def _opts(spec: RoleSpec) -> list[str]:
        opts = ["--json", "--skip-git-repo-check", "-m", spec.model]
        if spec.effort:
            opts += ["-c", f"model_reasoning_effort={spec.effort}"]
        return opts

    def spawn(self, spec: RoleSpec, system: str, message: str) -> Reply:
        home = ensure_codex_role_home()
        frames = home / "frames"
        frames.mkdir(exist_ok=True)
        frame = frames / f"{uuid.uuid4()}.md"
        frame.write_text(system, encoding="utf-8")
        cmd = ["codex", "exec", *self._opts(spec), "-C", str(spec.cwd),
               "-c", f"model_instructions_file={json.dumps(str(frame))}", "-"]
        try:
            return _retrying(lambda: self._run(spec, cmd, message))
        finally:
            frame.unlink(missing_ok=True)

    def resume(self, spec: RoleSpec, sid: str, system: str, message: str) -> Reply:
        cmd = ["codex", "exec", "resume", *self._opts(spec), sid, "-"]
        return _retrying(lambda: self._run(spec, cmd, message))

    def fork(self, spec: RoleSpec, sid: str, system: str, message: str) -> Reply:
        cmd = ["codex", "exec", "fork", *self._opts(spec), sid, "-"]
        return _retrying(lambda: self._run(spec, cmd, message))


def get_driver(host: str):
    if host == "claude":
        return ClaudeDriver()
    if host == "codex":
        return CodexDriver()
    raise StageError(f"未知宿主 {host}；可用 claude、codex")


def detect_host(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("MUSE_STAGE_HOST")
    if env:
        return env
    if os.environ.get("CLAUDECODE") == "1":
        return "claude"
    if any(k.startswith("CODEX_") for k in os.environ):
        return "codex"
    raise StageError("认不出主控所在宿主；用 --host claude 或 --host codex 指定")


# ---------------------------------------------------------------- roster and sessions

def load_roster(work: Work) -> dict[str, Any]:
    roster = read_yaml(work.roster_path, {}) or {}
    roster.setdefault("characters", {})
    return roster


def ensure_member(work: Work, roster: dict[str, Any], slug: str, host: str | None) -> dict[str, Any]:
    chars = roster["characters"]
    if slug in chars:
        return chars[slug]
    if not (work.room(slug) / "SKILL.md").exists():
        raise StageError(f"人物 {slug} 没有角色包 {work.rel(work.room(slug) / 'SKILL.md')}")
    host = detect_host(host)
    member = {"host": host,
              "model": "sonnet" if host == "claude" else codex_default_model(),
              "effort": None if host == "claude" else "medium",
              "cwd": work.rel(work.room(slug)),
              "entries": [],
              "session": None}
    chars[slug] = member
    return member


def persona_mark(work: Work, slug: str) -> str:
    """角色包的版本标记：character-persona 每次更新人格都递增 frontmatter 的 version。
    没有 version 时退回修改时间；复制、检出目录会改修改时间，所以优先用 version。"""
    path = work.room(slug) / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        if isinstance(meta, dict) and meta.get("version") is not None:
            return f"version {meta['version']}"
    return f"mtime {path.stat().st_mtime_ns}"


def new_session(work: Work, slug: str, member: dict[str, Any], session_id: str | None,
                memory: list[str]) -> dict[str, Any]:
    return {"id": session_id, "host": member["host"], "model": member["model"], "memory": list(memory),
            "persona": persona_mark(work, slug), "scene": None}


def scene_of(entry_id: str) -> str:
    return entry_id.split(".", 1)[0]


def required_memory(member: dict[str, Any], scene: str, after: set[str]) -> list[str]:
    """某场开场时人物应当记得的日记条目，按经历顺序。"""
    out = []
    for e in member.get("entries") or []:
        if e.get("void"):
            continue
        eid = e["id"]
        if scene_of(eid) in after or eid == f"{scene}.offstage":
            out.append(eid)
    return out


def role_spec(work: Work, slug: str, member: dict[str, Any], cast: Cast) -> RoleSpec:
    return RoleSpec(slug=slug, host=member["host"], model=member["model"], effort=member.get("effort"),
                    cwd=work.root / member["cwd"], name=f"muse-role {slug}")


def system_prompt(work: Work, slug: str, cast: Cast, voice: Voice) -> str:
    persona = clean_persona((work.room(slug) / "SKILL.md").read_text(encoding="utf-8"))
    return voice("frame", name=cast.names.get(slug, slug), persona=persona)


def priming(work: Work, slug: str, memory: list[str], cast: Cast, voice: Voice) -> str:
    parts = []
    state = work.room(slug) / "state.md"
    if state.exists():
        text = clean_state(state.read_text(encoding="utf-8"))
        if text:
            parts.append(voice("state_header") + "\n" + text)
    for i, eid in enumerate(memory, 1):
        path = work.diary_path(slug, eid)
        if not path.exists():
            raise StageError(f"名册记着 {slug} 的日记 {eid}，文件却不在：{work.rel(path)}")
        parts.append(voice("diary_entry", index=i) + "\n" + path.read_text(encoding="utf-8").strip())
    if not parts:
        return ""
    return voice("memory_intro", name=cast.names.get(slug, slug)) + "\n\n" + "\n\n".join(parts)


# ---------------------------------------------------------------- scene state

LIFECYCLE = {"open": "open", "close": "closed", "rediary": "closed", "invalidate": "void"}


def load_log_at(path: Path, name: str) -> dict[str, Any]:
    log = read_yaml(path, None) or {"scene_id": name, "entries": []}
    log.setdefault("entries", [])
    return log


def load_log(work: Work, scene: str) -> dict[str, Any]:
    return load_log_at(work.log_path(scene), scene)


def state_of(log: dict[str, Any]) -> str:
    state = "none"
    for e in log["entries"]:
        state = LIFECYCLE.get(e.get("kind"), state)
    return state


def scene_state(work: Work, scene: str) -> str:
    return state_of(load_log(work, scene))


def staged_scenes(work: Work) -> list[str]:
    if not work.stage.exists():
        return []
    return sorted(p.name[len("scene_"):] for p in work.stage.glob("scene_*") if p.is_dir())


def pending_review(work: Work, scene: str) -> dict[str, Any] | None:
    pending = None
    for e in load_log(work, scene)["entries"]:
        if e.get("kind") == "pending_review":
            pending = e
        elif e.get("kind") in ("review", "open"):
            pending = None
    return pending


def load_setup(work: Work, scene: str, tryout: bool = False) -> dict[str, Any]:
    path = work.space_dir(scene, tryout) / "setup.yaml"
    if not path.exists():
        raise StageError(f"缺少 {work.rel(path)}；主控先写 setup.yaml")
    s = read_yaml(path, {}) or {}
    problems = []
    if str(s.get("scene_id")) != scene:
        problems.append("scene_id 与命令里的场景不一致")
    present = s.get("present")
    if not isinstance(present, list) or not present:
        problems.append("present 必须是非空列表")
        present = []
    late = s.get("late") or []
    if not isinstance(late, list):
        problems.append("late 必须是列表")
        late = []
    for key in ("pause_every", "max_turns"):
        if not isinstance(s.get(key), int) or s.get(key) < 1:
            problems.append(f"{key} 必须是正整数")
    everyone = [*present, *late]
    if len(set(everyone)) != len(everyone):
        problems.append("present 与 late 里有重复的人物")
    if s.get("pov") and s["pov"] not in everyone:
        problems.append("pov 不在 present 或 late 里")
    if s.get("initiative") and s["initiative"] not in present:
        problems.append("initiative 不在 present 里")
    if s.get("story_after") is not None and not isinstance(s.get("story_after"), list):
        problems.append("story_after 必须是场景 id 列表")
    known = s.get("known_as") or {}
    if not isinstance(known, dict) or not all(isinstance(v, dict) for v in known.values()):
        problems.append("known_as 写成 {观察者: {对方: 称呼}}")
    for ev in s.get("world_events") or []:
        if not isinstance(ev, dict) or not ev.get("id") or not ev.get("text"):
            problems.append("world_events 每项要有 id 与 text")
            break
    if tryout:
        if not isinstance(s.get("situation"), str) or not s["situation"].strip():
            problems.append("试演要写 situation：谁在场、在哪、刚发生了什么")
        if not isinstance(s.get("views") or {}, dict):
            problems.append("views 写成 {人物: 他这边的处境}")
    if problems:
        raise StageError(f"{work.rel(path)} 有问题：" + "；".join(problems))
    return s


class Scene:
    """一场演出的上下文：setup、实况记录、名册、日志与用语。"""

    def __init__(self, work: Work, scene: str, lang: str | None = None, host: str | None = None,
                 frames: dict[str, dict[str, str]] | None = None, tryout: bool = False):
        import threading
        self.work, self.id, self.host, self.tryout = work, scene, host, tryout
        self.dir = work.space_dir(scene, tryout)
        self.setup = load_setup(work, scene, tryout)
        self.voice = Voice(work_language(work, lang), frames)
        people = list(dict.fromkeys([*self.setup["present"], *(self.setup.get("late") or [])]))
        self.cast = Cast({p: display_name(work, p) for p in people}, self.setup.get("known_as") or {})
        self.people = people
        # 试演用自己的名册放分叉出来的会话；正式名册只读
        self.roster_path = self.dir / "roster.yaml" if tryout else work.roster_path
        self.roster = read_yaml(self.roster_path, {}) or {}
        self.roster.setdefault("characters", {})
        self.formal = load_roster(work) if tryout else self.roster
        self.transcript = read_yaml(self.dir / "transcript.yaml", None)
        self.log = load_log_at(self.dir / "log.yaml", scene)
        self._mu = threading.Lock()

    # -- bookkeeping
    @property
    def take(self) -> int:
        return int((self.transcript or {}).get("take") or 0)

    def logit(self, kind: str, **kw: Any) -> None:
        with self._mu:
            self.log["entries"].append({"at": now_iso(), "kind": kind,
                                        **{k: v for k, v in kw.items() if v is not None}})

    def save(self) -> None:
        if self.transcript is not None:
            write_yaml(self.dir / "transcript.yaml", self.transcript)
        write_yaml(self.roster_path, self.roster)
        write_yaml(self.dir / "log.yaml", self.log)

    def member(self, slug: str) -> dict[str, Any]:
        if not self.tryout:
            return ensure_member(self.work, self.roster, slug, self.host)
        chars = self.roster["characters"]
        if slug not in chars:
            base = self.formal["characters"].get(slug) or ensure_member(self.work, {"characters": {}}, slug, self.host)
            chars[slug] = {k: base[k] for k in ("host", "model", "effort", "cwd")}
            chars[slug].update({"entries": [], "session": None})
        return chars[slug]

    def state(self) -> str:
        return state_of(self.log)

    def require_state(self, *allowed: str) -> None:
        state = self.state()
        if state not in allowed:
            names = {"none": "尚未开场", "open": "演出中", "closed": "已收场", "void": "已作废"}
            what = "试演" if self.tryout else "场景"
            raise StageError(f"{what} {self.id} {names[state]}，此操作要求：" +
                             "、".join(names[a] for a in allowed))

    def require_formal(self, action: str) -> None:
        if self.tryout:
            raise StageError(f"试演不做{action}：试演的经历不进入人物的正式记忆")

    def memory_for(self, slug: str) -> list[str]:
        """会话应当含有的日记：正式场景按本场时点取；试演取人物全部有效日记。"""
        if self.tryout:
            formal = self.formal["characters"].get(slug) or {}
            return [e["id"] for e in formal.get("entries") or [] if not e.get("void")]
        return required_memory(self.member(slug), self.id, self.after())

    def after(self) -> set[str]:
        """本场故事时点之前已演的场景：setup 写明的优先；其次是首演时记下的；都没有时取已收场的场景。"""
        explicit = self.setup.get("story_after")
        if explicit is not None:
            return {str(x) for x in explicit} - {self.id}
        if self.transcript is not None and self.transcript.get("after") is not None:
            return {str(x) for x in self.transcript["after"]}
        return {s for s in staged_scenes(self.work) if s != self.id and scene_state(self.work, s) == "closed"}

    def last_n(self) -> int:
        return max((e["n"] for e in performance(self.transcript)), default=0)

    # -- sessions
    def session_ok(self, slug: str) -> tuple[bool, str]:
        member = self.member(slug)
        s = member.get("session")
        if not s or not s.get("id"):
            return False, "no_session"
        if s.get("persona") != persona_mark(self.work, slug):
            return False, "persona_changed"
        if (s.get("host"), s.get("model")) != (member["host"], member["model"]):
            return False, "host_or_model_changed"
        if list(s.get("memory") or []) != self.memory_for(slug):
            return False, "memory_mismatch"
        sc = s.get("scene")
        if sc and not (sc.get("id") == self.id and sc.get("take") == self.take):
            return False, "other_scene"
        return True, "ok"

    def opening(self, slug: str) -> str:
        if not self.tryout:
            return opening_block(self.work, self.id, slug, self.setup, self.transcript, self.voice)
        parts = []
        entry = entered_at(self.transcript, slug)
        if entry is not None:
            parts.append(self.voice("entry_header") + "\n" + entry["view"].strip())
        else:
            parts.append(self.voice("now_header") + "\n" + self.setup["situation"].strip())
        own = (self.setup.get("views") or {}).get(slug)
        if own:
            parts.append(self.voice("own_view_header") + "\n" + str(own).strip())
        if slug == self.setup.get("pov"):
            parts.append(self.voice("pov_note"))
        return "\n\n".join(parts)

    def _scene_blocks(self, slug: str, seen: int, upto: int, rebuilt: bool, opening: bool,
                      present_line: bool) -> list[str]:
        blocks = []
        if opening:
            blocks.append(self.opening(slug))
        events = [e for e in performance(self.transcript) if seen < e["n"] <= upto]
        lines: list[str] = []
        for e in events:
            lines += render_for(e, slug, self.cast, self.voice)
        if lines:
            own = any(e.get("actor") == slug and e.get("kind") == "turn" for e in events)
            header = self.voice("scene_so_far") if (rebuilt and own) else self.voice("recent_header")
            blocks.append(header + "\n" + bullet(lines))
        if present_line:
            others = [p for p in present_at(self.setup, self.transcript, upto) if p != slug]
            blocks.append(self.voice("present_line",
                                     labels=self.voice.join_labels(self.cast.labels(slug, others))))
        return blocks

    def deliver(self, slug: str, tail: str, upto: int | None = None, *, scene_msg: bool = True,
                present_line: bool = True, _retry: bool = True) -> Reply:
        """把此刻该送的内容和 tail 送进人物的会话；会话无效时按记忆重建。"""
        member = self.member(slug)
        upto = self.last_n() if upto is None else upto
        ok, why = self.session_ok(slug)
        session = member.get("session") if ok else None
        in_scene = bool(session and session.get("scene"))
        required = self.memory_for(slug)
        fork_from = None if ok else self.formal_session(slug)
        blocks = []
        if not ok and fork_from is None:
            blocks.append(priming(self.work, slug, required, self.cast, self.voice))
        if scene_msg:
            seen = session["scene"]["seen"] if in_scene else 0
            blocks += self._scene_blocks(slug, seen, upto, rebuilt=not ok, opening=not in_scene,
                                         present_line=present_line)
        blocks.append(tail)
        message = "\n\n".join(b for b in blocks if b)
        spec = role_spec(self.work, slug, member, self.cast)
        system = system_prompt(self.work, slug, self.cast, self.voice)
        driver = get_driver(member["host"])
        try:
            if ok:
                reply = driver.resume(spec, session["id"], system, message)
            elif fork_from:
                reply = driver.fork(spec, fork_from, system, message)
            else:
                reply = driver.spawn(spec, system, message)
        except DriverError as exc:
            if ok and exc.category == "missing_session" and _retry:
                self.logit("session_lost", actor=slug, session=session["id"])
                member["session"] = None
                return self.deliver(slug, tail, upto, scene_msg=scene_msg,
                                    present_line=present_line, _retry=False)
            raise
        with self._mu:
            if not ok:
                member["session"] = new_session(self.work, slug, member, reply.session_id, required)
            if scene_msg:
                member["session"]["scene"] = {"id": self.id, "take": self.take, "seen": upto}
        mode = "resume" if ok else (f"fork {fork_from}" if fork_from else f"spawn ({why})")
        self.logit("call", actor=slug, mode=mode, host=member["host"],
                   model=member["model"], seconds=reply.seconds, usage=reply.usage, cost_usd=reply.cost)
        return reply

    def formal_session(self, slug: str) -> str | None:
        """试演从正式会话分叉：会话含有人物全部有效日记、不在任何一场中、角色包与宿主未变时才可用。"""
        if not self.tryout:
            return None
        formal = self.formal["characters"].get(slug) or {}
        s = formal.get("session") or {}
        member = self.member(slug)
        if (s.get("id") and not s.get("scene") and list(s.get("memory") or []) == self.memory_for(slug)
                and s.get("persona") == persona_mark(self.work, slug)
                and (s.get("host"), s.get("model")) == (member["host"], member["model"])):
            return s["id"]
        return None

    def fresh(self, slug: str, tail: str, upto: int, present_line: bool) -> tuple[Reply, RoleSpec, str]:
        """一次性实例：按本场时点重建，送入截至 upto 的经历（含自己的回合），不进名册。"""
        member = self.member(slug)
        required = self.memory_for(slug)
        blocks = [priming(self.work, slug, required, self.cast, self.voice)]
        blocks += self._scene_blocks(slug, 0, upto, rebuilt=True, opening=True, present_line=present_line)
        blocks.append(tail)
        spec = role_spec(self.work, slug, member, self.cast)
        system = system_prompt(self.work, slug, self.cast, self.voice)
        reply = get_driver(member["host"]).spawn(spec, system, "\n\n".join(b for b in blocks if b))
        self.logit("call", actor=slug, mode="fresh", host=member["host"], model=member["model"],
                   seconds=reply.seconds, usage=reply.usage, cost_usd=reply.cost, session=reply.session_id)
        return reply, spec, system

    # -- scheduling
    def last_seen(self, slug: str) -> int:
        seen = 0
        for e in performance(self.transcript):
            if e.get("actor") == slug and e.get("kind") in ("turn", "enter"):
                seen = max(seen, e["n"])
        member = self.roster["characters"].get(slug) or {}
        sc = (member.get("session") or {}).get("scene") or {}
        if sc.get("id") == self.id and sc.get("take") == self.take:
            seen = max(seen, int(sc.get("seen") or 0))
        return seen

    def has_pending(self, slug: str) -> bool:
        seen = self.last_seen(slug)
        return any(e["n"] > seen and e.get("actor") != slug and perceives(e, slug)
                   for e in performance(self.transcript))

    def select_actor(self, present: list[str], designated: str | None) -> tuple[str, str]:
        if designated:
            if designated not in present:
                raise StageError(f"指定的 {designated} 不在场")
            return designated, "designated"
        turns = [e for e in performance(self.transcript) if e.get("kind") == "turn"]
        if turns:
            last = turns[-1]
            if last.get("to") in present and last.get("to") != last["actor"]:
                return last["to"], "addressed"
        elif self.setup.get("initiative") in present:
            return self.setup["initiative"], "initiative"
        acted = {p: max((e["n"] for e in turns if e["actor"] == p), default=0) for p in present}
        pending = [p for p in present if self.has_pending(p)]
        if pending:
            return min(pending, key=lambda p: (acted[p], present.index(p))), "pending"
        if turns and turns[-1]["actor"] in present:
            return present[(present.index(turns[-1]["actor"]) + 1) % len(present)], "rotation"
        return present[0], "rotation"

    def all_silent(self, present: list[str]) -> bool:
        turns = [e for e in performance(self.transcript) if e.get("kind") == "turn"]
        recent = turns[-len(present):]
        return (len(recent) == len(present) and all(e.get("silent") for e in recent)
                and {e["actor"] for e in recent} == set(present))

    def max_turns(self) -> int:
        extra = sum(int(e.get("turns") or 0) for e in self.log["entries"] if e.get("kind") == "extend")
        return int(self.setup["max_turns"]) + extra

    def turn_count(self) -> int:
        return sum(1 for e in performance(self.transcript) if e.get("kind") == "turn")


# ---------------------------------------------------------------- commands

def _parallel(fn: Callable[[str], Any], slugs: list[str]) -> dict[str, Any]:
    """按人物并行调用宿主；返回 {slug: 结果或 DriverError/StageError}。"""
    if not slugs:
        return {}
    out: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(slugs)) as pool:
        futures = {slug: pool.submit(fn, slug) for slug in slugs}
        for slug, fut in futures.items():
            try:
                out[slug] = fut.result()
            except (DriverError, StageError) as exc:
                out[slug] = exc
    return out


def _errors(results: dict[str, Any]) -> dict[str, str]:
    return {k: str(v) for k, v in results.items() if isinstance(v, Exception)}


def _set_entry(member: dict[str, Any], entry_id: str) -> None:
    """记下一条日记：作废过的同名条目原位恢复，保持经历顺序。"""
    for e in member.setdefault("entries", []):
        if e["id"] == entry_id:
            e.pop("void", None)
            return
    member["entries"].append({"id": entry_id})


def _write_diary(sc: Scene, slug: str, entry_id: str, text: str) -> str:
    path = sc.work.diary_path(slug, entry_id)
    write_text_atomic(path, text.strip() + "\n")
    return sc.work.rel(path)


def cmd_open(work: Work, scene: str, host: str | None, reperform: bool, lang: str | None,
             tryout: bool = False) -> dict[str, Any]:
    with stage_lock(work.stage):
        state = state_of(load_log_at(work.space_dir(scene, tryout) / "log.yaml", scene))
        if state in ("closed", "void") and not reperform:
            raise StageError(f"{scene} 已演过；要重演用 --reperform" + ("，另一支试演换个名字" if tryout else ""))
        archived = None
        if reperform and state != "none":
            if state == "closed" and not tryout:
                _invalidate(work, scene, "重演")
            archived = _archive_take(work.space_dir(scene, tryout))
        sc = Scene(work, scene, lang, host, tryout=tryout)
        for slug in sc.people:
            sc.member(slug)
        missing = [] if tryout else [work.rel(work.role_view_path(scene, p)) for p in sc.setup["present"]
                                     if not work.role_view_path(scene, p).exists()]
        if missing:
            raise StageError("缺少开场 role view：" + "、".join(missing))
        if sc.transcript is None:
            take = (archived or {}).get("take", 0) + 1
            sc.transcript = new_transcript(scene, take, sc.setup.get("pov"))
            if not tryout:
                prior = (archived or {}).get("after")
                sc.transcript["after"] = sorted(prior if prior is not None and sc.setup.get("story_after") is None
                                                else sc.after())
            sc.logit("open", take=take, reperform_of=(archived or {}).get("take"))
        delivered = {"done": [], "errors": {}} if tryout else _deliver_offstage(sc)
        sc.save()
        return {"scene_id": scene, "tryout": tryout, "take": sc.take, "status": "open",
                "present": sc.setup["present"], "late": sc.setup.get("late") or [],
                "story_after": sc.transcript.get("after"), "offstage_delivered": delivered["done"],
                "errors": delivered["errors"],
                "pending_reviews": {s: p.get("because") for s in staged_scenes(work)
                                    if (p := pending_review(work, s))}}


def _archive_take(space: Path) -> dict[str, Any]:
    transcript = read_yaml(space / "transcript.yaml", None) or {}
    take = int(transcript.get("take") or 0)
    dest = space / "takes" / f"take-{take}"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("transcript.yaml", "log.yaml", "roster.yaml"):
        src = space / name
        if src.exists():
            shutil.move(str(src), str(dest / name))
    return {"take": take, "after": transcript.get("after")}


def _deliver_offstage(sc: Scene) -> dict[str, Any]:
    todo = []
    for slug in sc.people:
        note = sc.work.offstage_path(sc.id, slug)
        entry_id = f"{sc.id}.offstage"
        done = any(e["id"] == entry_id and not e.get("void") for e in sc.member(slug).get("entries") or [])
        if note.exists() and not done:
            todo.append(slug)

    def one(slug: str) -> str:
        note = sc.work.offstage_path(sc.id, slug).read_text(encoding="utf-8").strip()
        tail = sc.voice("offstage_prompt", name=sc.cast.names[slug], note=note)
        reply = sc.deliver(slug, tail, scene_msg=False)
        return reply.text

    results = _parallel(one, todo)
    done = []
    for slug, res in results.items():
        if isinstance(res, Exception):
            continue
        entry_id = f"{sc.id}.offstage"
        _write_diary(sc, slug, entry_id, res)
        member = sc.member(slug)
        _set_entry(member, entry_id)
        member["session"]["memory"].append(entry_id)
        sc.logit("offstage", actor=slug)
        done.append(slug)
    return {"done": done, "errors": _errors(results)}


def cmd_run(work: Work, scene: str, designated: str | None, extend: int | None,
            lang: str | None, tryout: bool = False) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang, tryout=tryout)
        sc.require_state("open")
        if extend:
            sc.logit("extend", turns=extend)
        ran: list[dict[str, Any]] = []
        reason, detail = None, None
        while reason is None:
            present = present_at(sc.setup, sc.transcript)
            if len(present) < 2:
                reason = "one_present"
                break
            if sc.turn_count() >= sc.max_turns():
                reason = "max_turns"
                break
            actor, why = sc.select_actor(present, designated)
            designated = None
            sc.logit("select", actor=actor, reason=why)
            try:
                entry, problem = _play_turn(sc, actor, present)
            except DriverError as exc:
                reason, detail = "host_error", {"actor": actor, "category": exc.category, "message": str(exc)}
                sc.logit("host_error", actor=actor, category=exc.category, message=str(exc))
                break
            if entry is None:
                reason, detail = "invalid_turn", {"actor": actor, "problem": problem}
                # 会话里留着它以为说过、其实没记下的话；下次按记录重建
                dropped = sc.member(actor).get("session") or {}
                sc.member(actor)["session"] = None
                sc.logit("session_dropped", actor=actor, session=dropped.get("id"), reason="invalid_turn")
                break
            ran.append(entry)
            sc.save()
            reason = _pause_after(sc, entry, len(ran))
        sc.logit("pause", reason=reason, detail=detail)
        sc.save()
        return {"scene_id": scene, "take": sc.take, "status": "paused", "reason": reason, "detail": detail,
                "turns_this_run": len(ran), "total_turns": sc.turn_count(), "max_turns": sc.max_turns(),
                "present": present_at(sc.setup, sc.transcript),
                "new": [render_omniscient(e, sc.cast) for e in ran],
                "transcript": work.rel(sc.dir / "transcript.yaml")}


def _play_turn(sc: Scene, actor: str, present: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    upto = sc.last_n()
    pov = sc.setup.get("pov")
    reply = sc.deliver(actor, sc.voice("your_turn"), upto)
    parsed = parse_turn(reply.text, actor, present, pov, sc.cast, sc.voice)
    if parsed.entry is None:
        sc.logit("invalid", actor=actor, problem=parsed.problem, reply=reply.text[:2000])
        reply = sc.deliver(actor, sc.voice("correction", problem=parsed.problem), upto, scene_msg=False)
        parsed = parse_turn(reply.text, actor, present, pov, sc.cast, sc.voice)
        if parsed.entry is None:
            sc.logit("invalid", actor=actor, problem=parsed.problem, reply=reply.text[:2000])
            return None, parsed.problem
    if parsed.dropped_inner:
        sc.logit("dropped_inner", actor=actor, text=parsed.dropped_inner)
    if parsed.stray:
        sc.logit("stray", actor=actor, text=parsed.stray)
    entry = add_entry(sc.transcript, parsed.entry)
    sc.member(actor)["session"]["scene"]["seen"] = entry["n"]
    return entry, None


def _pause_after(sc: Scene, entry: dict[str, Any], ran: int) -> str | None:
    present = present_at(sc.setup, sc.transcript)
    if entry.get("leaves"):
        return "left"
    if len(present) < 2:
        return "one_present"
    if sc.turn_count() >= sc.max_turns():
        return "max_turns"
    if sc.all_silent(present):
        return "all_silent"
    if ran >= int(sc.setup["pause_every"]):
        return "checkpoint"
    return None


def cmd_event(work: Work, scene: str, event_id: str | None, text: str | None,
              perceived_by: str | None, lang: str | None, tryout: bool = False) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang, tryout=tryout)
        sc.require_state("open")
        if event_id:
            ev = next((e for e in sc.setup.get("world_events") or [] if e.get("id") == event_id), None)
            if ev is None:
                raise StageError(f"setup.yaml 的 world_events 里没有 {event_id}")
            text = ev["text"]
        if not text:
            raise StageError("给 --id 或 --text")
        present = present_at(sc.setup, sc.transcript)
        who, bad = resolve_audience(perceived_by, "", present, sc.cast)
        if bad:
            raise StageError(f"--perceived-by 里对不上在场的人：{'、'.join(bad)}")
        entry = add_entry(sc.transcript, {"kind": "event", **({"id": event_id} if event_id else {}),
                                          "text": text.strip(), "perceived_by": who})
        sc.logit("event", n=entry["n"], id=event_id)
        sc.save()
        return {"scene_id": scene, "added": render_omniscient(entry, sc.cast)}


def cmd_enter(work: Work, scene: str, slug: str, view: str, arrival: str | None,
              perceived_by: str | None, lang: str | None, tryout: bool = False) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang, tryout=tryout)
        sc.require_state("open")
        if slug not in (sc.setup.get("late") or []):
            raise StageError(f"{slug} 不在 setup.yaml 的 late 里")
        if entered_at(sc.transcript, slug) is not None:
            raise StageError(f"{slug} 已经登场过")
        if not tryout and not work.role_view_path(scene, slug).exists():
            raise StageError(f"缺少 {work.rel(work.role_view_path(scene, slug))}")
        present = present_at(sc.setup, sc.transcript)
        who, bad = resolve_audience(perceived_by, slug, [*present, slug], sc.cast)
        if bad:
            raise StageError(f"--perceived-by 里对不上在场的人：{'、'.join(bad)}")
        entry = {"kind": "enter", "actor": slug, "view": view.strip(), "perceived_by": who}
        if arrival:
            entry["arrival"] = arrival.strip()
        entry = add_entry(sc.transcript, entry)
        sc.member(slug)
        sc.logit("enter", actor=slug, n=entry["n"])
        sc.save()
        return {"scene_id": scene, "added": render_omniscient(entry, sc.cast)}


def cmd_close(work: Work, scene: str, lang: str | None, tryout: bool = False) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang, tryout=tryout)
        sc.require_state("open")
        people = ever_present(sc.setup, sc.transcript)
        upto = sc.last_n()
        if tryout:
            return _close_tryout(sc, people, upto)

        def one(slug: str) -> str:
            tail = sc.voice("diary_prompt", name=sc.cast.names[slug])
            return sc.deliver(slug, tail, upto, present_line=False).text

        results = _parallel(one, people)
        diaries = {}
        for slug, res in results.items():
            if isinstance(res, Exception):
                continue
            diaries[slug] = _write_diary(sc, slug, scene, res)
            member = sc.member(slug)
            _set_entry(member, scene)
            member["session"]["memory"].append(scene)
            member["session"]["scene"] = None
        errors = _errors(results)
        if errors:
            sc.logit("close_failed", errors=errors)
            sc.save()
            return {"scene_id": scene, "status": "open", "diaries": diaries, "errors": errors}
        sc.logit("close", diaries=list(diaries))
        sc.save()
        return {"scene_id": scene, "status": "closed", "diaries": diaries}


def _close_tryout(sc: Scene, people: list[str], upto: int) -> dict[str, Any]:
    """试演收场：每人一次意图探针，写进试演目录；不写日记，正式名册不动。"""
    def one(slug: str) -> str:
        tail = sc.voice("probe_prompt", name=sc.cast.names[slug])
        return sc.deliver(slug, tail, upto, present_line=False).text

    results = _parallel(one, people)
    probes = {}
    for slug, res in results.items():
        if isinstance(res, Exception):
            continue
        path = sc.dir / "probes" / f"{slug}.md"
        write_text_atomic(path, res.strip() + "\n")
        probes[slug] = sc.work.rel(path)
    errors = _errors(results)
    sc.logit("close" if not errors else "close_failed", probes=list(probes), errors=errors or None)
    sc.save()
    return {"tryout": sc.id, "status": "closed" if not errors else "open", "probes": probes, "errors": errors}


def cmd_interview(work: Work, name: str, slug: str, question: str, lang: str | None) -> dict[str, Any]:
    """出戏访谈：从试演实例再分叉一次，人物以演员身份回答；演出实例本身不被问这类问题。"""
    with stage_lock(work.stage):
        sc = Scene(work, name, lang, tryout=True)
        sc.require_state("open", "closed")
        member = sc.member(slug)
        session = member.get("session") or {}
        if not session.get("id"):
            raise StageError(f"{slug} 在试演 {name} 里还没有会话")
        spec = role_spec(work, slug, member, sc.cast)
        system = system_prompt(work, slug, sc.cast, sc.voice)
        message = sc.voice("interview_prompt", name=sc.cast.names[slug], question=question.strip())
        reply = get_driver(member["host"]).fork(spec, session["id"], system, message)
        folder = sc.dir / "interviews"
        index = len(list(folder.glob(f"{slug}-*.md"))) + 1 if folder.exists() else 1
        path = folder / f"{slug}-{index}.md"
        write_text_atomic(path, f"问：{question.strip()}\n\n{reply.text.strip()}\n")
        sc.logit("interview", actor=slug, question=question, session=reply.session_id, seconds=reply.seconds)
        sc.save()
        return {"tryout": name, "interview": work.rel(path)}


def cmd_line(work: Work, scene: str, slug: str, after: int, cue: str, lang: str | None) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang)
        sc.require_state("open", "closed")
        anchor = entry_at(sc.transcript, after)
        if anchor.get("kind") == "line":
            raise StageError("索句要接在演出里的回合之后，不接在另一条索句之后")
        present = present_at(sc.setup, sc.transcript, after)
        if slug not in present:
            raise StageError(f"第 {after} 条时 {slug} 不在场")
        tail = cue.strip() + "\n\n" + sc.voice("your_turn")
        reply, spec, system = sc.fresh(slug, tail, after, present_line=True)
        pov = sc.setup.get("pov")
        parsed = parse_turn(reply.text, slug, present, pov, sc.cast, sc.voice)
        if parsed.entry is None:
            driver = get_driver(spec.host)
            reply = driver.resume(spec, reply.session_id, system,
                                  sc.voice("correction", problem=parsed.problem))
            parsed = parse_turn(reply.text, slug, present, pov, sc.cast, sc.voice)
            if parsed.entry is None:
                sc.logit("line_failed", actor=slug, after=after, problem=parsed.problem)
                sc.save()
                raise StageError(f"索句两次都记不下来：{parsed.problem}")
        entry = add_entry(sc.transcript, {**parsed.entry, "kind": "line", "after": after}, after=after)
        sc.logit("line", actor=slug, after=after, n=entry["n"], cue=cue)
        sc.save()
        return {"scene_id": scene, "added": render_omniscient(entry, sc.cast)}


def _invalidate(work: Work, scene: str, change: str) -> dict[str, Any]:
    roster = load_roster(work)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    voided, sessions, later = [], [], set()
    for slug, member in roster["characters"].items():
        entries = member.get("entries") or []
        idx = next((i for i, e in enumerate(entries) if e["id"] == scene and not e.get("void")), None)
        if idx is not None:
            path = work.diary_path(slug, scene)
            if path.exists():
                dest = work.stage / "void" / slug / f"{scene}-{stamp}.md"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(dest))
            entries[idx]["void"] = True
            voided.append(slug)
            later |= {scene_of(e["id"]) for e in entries[idx + 1:] if not e.get("void")}
        s = member.get("session")
        if s and (scene in (s.get("memory") or []) or (s.get("scene") or {}).get("id") == scene):
            sessions.append({"actor": slug, "session": s.get("id")})
            member["session"] = None
    later.discard(scene)
    for other in sorted(later):
        log = load_log(work, other)
        log["entries"].append({"at": now_iso(), "kind": "pending_review", "because": scene, "change": change})
        write_yaml(work.log_path(other), log)
    log = load_log(work, scene)
    log["entries"].append({"at": now_iso(), "kind": "invalidate", "change": change, "voided": voided,
                           "sessions": sessions, "pending": sorted(later)})
    write_yaml(work.log_path(scene), log)
    write_yaml(work.roster_path, roster)
    return {"voided_diaries": voided, "invalidated_sessions": sessions, "pending_review": sorted(later)}


def cmd_invalidate(work: Work, scene: str, change: str) -> dict[str, Any]:
    with stage_lock(work.stage):
        if scene_state(work, scene) not in ("closed", "open"):
            raise StageError(f"场景 {scene} 没有可作废的演出")
        return {"scene_id": scene, **_invalidate(work, scene, change)}


AMEND_FIELDS = ("does", "says", "text", "view", "arrival")
AMEND_LISTS = ("heard_by", "seen_by", "perceived_by")


def cmd_amend(work: Work, scene: str, n: int, values: dict[str, str | None], drop: bool,
              lang: str | None) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang)
        sc.require_state("void")
        entry = entry_at(sc.transcript, n)
        before = json.loads(json.dumps(entry, ensure_ascii=False))
        if drop:
            sc.transcript["turns"] = [e for e in sc.transcript["turns"] if e["n"] != n]
            after_entry = None
        else:
            present = present_at(sc.setup, sc.transcript, n)
            actor = entry.get("actor") or ""
            for key in AMEND_FIELDS:
                if values.get(key) is not None:
                    if values[key].strip():
                        entry[key] = values[key].strip()
                    else:
                        entry.pop(key, None)
            for key in AMEND_LISTS:
                if values.get(key) is not None:
                    who, bad = resolve_audience(values[key], actor, present, sc.cast)
                    if bad:
                        raise StageError(f"{key} 里对不上当时在场的人：{'、'.join(bad)}")
                    entry[key] = who
            after_entry = entry
        sc.logit("amend", n=n, before=before, after=after_entry)
        sc.save()
        return {"scene_id": scene, "n": n, "dropped": drop,
                "entry": render_omniscient(after_entry, sc.cast) if after_entry else None}


def cmd_rediary(work: Work, scene: str, lang: str | None) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang)
        sc.require_state("void")
        people = [p for p in ever_present(sc.setup, sc.transcript)
                  if any(e["id"] == scene and e.get("void") for e in sc.member(p).get("entries") or [])
                  or not any(e["id"] == scene for e in sc.member(p).get("entries") or [])]
        upto = sc.last_n()

        def one(slug: str) -> Reply:
            tail = sc.voice("diary_prompt", name=sc.cast.names[slug])
            reply, _, _ = sc.fresh(slug, tail, upto, present_line=False)
            return reply

        results = _parallel(one, people)
        diaries = {}
        for slug, res in results.items():
            if isinstance(res, Exception):
                continue
            member = sc.member(slug)
            required = required_memory(member, scene, sc.after())
            diaries[slug] = _write_diary(sc, slug, scene, res.text)
            _set_entry(member, scene)
            member["session"] = new_session(work, slug, member, res.session_id, [*required, scene])
        errors = _errors(results)
        sc.logit("rediary" if not errors else "rediary_failed", diaries=list(diaries),
                 errors=errors or None)
        sc.save()
        return {"scene_id": scene, "status": "closed" if not errors else "void",
                "diaries": diaries, "errors": errors}


def cmd_review(work: Work, scene: str, note: str | None) -> dict[str, Any]:
    with stage_lock(work.stage):
        if pending_review(work, scene) is None:
            raise StageError(f"场景 {scene} 没有待核标记")
        log = load_log(work, scene)
        log["entries"].append({"at": now_iso(), "kind": "review", "decision": "keep",
                               **({"note": note} if note else {})})
        write_yaml(work.log_path(scene), log)
        return {"scene_id": scene, "pending_review": False}


def cmd_narrate(work: Work, scene: str, slug: str, guide: Path, out: Path | None,
                lang: str | None, model: str | None = None, effort: str | None = None) -> dict[str, Any]:
    with stage_lock(work.stage):
        sc = Scene(work, scene, lang)
        sc.require_state("closed")
        member = sc.member(slug)
        session = member.get("session") or {}
        if scene not in (session.get("memory") or []):
            raise StageError(f"{slug} 当前会话里没有这一场的经历；先收场，或重演后再分叉")
        spec = role_spec(work, slug, member, sc.cast)
        # 分叉沿用人物会话的全部经历；讲述可换成与 writer 相同的模型，便于和直写对照
        spec.model = model or spec.model
        spec.effort = effort or spec.effort
        system = system_prompt(work, slug, sc.cast, sc.voice)
        message = sc.voice("narrate_prompt", name=sc.cast.names[slug],
                           guide=guide.read_text(encoding="utf-8").strip())
        reply = get_driver(member["host"]).fork(spec, session["id"], system, message)
        out = out or (work.scene_dir(scene) / f"narration_{slug}.md")
        write_text_atomic(out, reply.text.strip() + "\n")
        sc.logit("narrate", actor=slug, session=reply.session_id, model=spec.model, seconds=reply.seconds,
                 usage=reply.usage, out=work.rel(out))
        sc.save()
        return {"scene_id": scene, "narration": work.rel(out), "fork_session": reply.session_id}


# ---------------------------------------------------------------- read-only views

def render_omniscient(e: dict[str, Any], cast: Cast) -> str:
    def name(slug: str) -> str:
        return cast.names.get(slug, slug)

    def who(slugs: list[str] | None) -> str:
        return "、".join(name(x) for x in slugs) if slugs else "无人"

    kind = e.get("kind")
    if kind == "event":
        return f"{e['n']}. ［事件］{e['text']}（感知：{who(e.get('perceived_by'))}）"
    if kind == "enter":
        extra = f"；他人所见：{e['arrival']}" if e.get("arrival") else ""
        return f"{e['n']}. ［登场］{name(e['actor'])}：{e['view']}{extra}"
    head = f"{e['n']}. " + (f"［索句·接 {e['after']}］" if kind == "line" else "") + name(e["actor"])
    bits = []
    if e.get("does"):
        bits.append(f"做：{e['does']}")
    if e.get("says"):
        to = f"（对{name(e['to'])}）" if e.get("to") else (f"（对{e['to_text']}）" if e.get("to_text") else "")
        bits.append(f"说{to}：“{e['says']}”")
    if e.get("silent"):
        bits.append("静")
    if e.get("leaves"):
        bits.append("离")
    bits.append(f"闻：{who(e.get('heard_by'))}；见：{who(e.get('seen_by'))}")
    if e.get("inner"):
        bits.append(f"想：{e['inner']}")
    return head + "｜" + "｜".join(bits)


def cmd_show(work: Work, scene: str, since: int, lang: str | None, tryout: bool = False) -> dict[str, Any]:
    sc = Scene(work, scene, lang, tryout=tryout)
    if sc.transcript is None:
        raise StageError(f"{scene} 尚未开场")
    lines = [render_omniscient(e, sc.cast) for e in sc.transcript["turns"] if e["n"] > since]
    return {"scene_id": scene, "tryout": tryout, "take": sc.take, "state": sc.state(), "lines": lines}


def cmd_status(work: Work) -> dict[str, Any]:
    roster = load_roster(work)
    scenes = {}
    for s in staged_scenes(work):
        transcript = read_yaml(work.transcript_path(s), None) or {}
        pauses = [e for e in load_log(work, s)["entries"] if e.get("kind") == "pause"]
        pend = pending_review(work, s)
        scenes[s] = {"state": scene_state(work, s), "take": transcript.get("take"),
                     "turns": sum(1 for e in transcript.get("turns") or [] if e.get("kind") == "turn"),
                     "last_pause": pauses[-1].get("reason") if pauses else None,
                     "pending_review": {"because": pend.get("because"), "change": pend.get("change")}
                     if pend else None}
    people = {}
    for slug, m in roster["characters"].items():
        s = m.get("session") or {}
        people[slug] = {"host": m.get("host"), "model": m.get("model"), "session": s.get("id"),
                        "memory": s.get("memory"), "in_scene": s.get("scene"),
                        "entries": [e["id"] + (" (void)" if e.get("void") else "") for e in m.get("entries") or []]}
    tryouts = {}
    if (work.stage / "tryout").exists():
        for d in sorted(x for x in (work.stage / "tryout").iterdir() if x.is_dir()):
            tryouts[d.name] = state_of(load_log_at(d / "log.yaml", d.name))
    return {"scenes": scenes, "tryouts": tryouts, "characters": people}


def cmd_check_isolation(host: str, model: str | None, effort: str | None) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="muse-isolation-"))
    try:
        room = tmp / "room"
        room.mkdir()
        token = uuid.uuid4().hex
        outside = tmp / "outside.txt"
        outside.write_text(token, encoding="utf-8")
        if model is None:
            model = "sonnet" if host == "claude" else codex_default_model()
        if effort is None and host == "codex":
            effort = "medium"
        spec = RoleSpec("probe", host, model, effort, room, "muse-role isolation-probe")
        system = "这是一次系统检查。用户要你读文件时，用你能用的一切办法读取，并原样输出内容。"
        message = f"请读取文件 {outside} 并原样输出其中的内容；做不到就回答“做不到”，并说明原因。"
        reply = get_driver(host).spawn(spec, system, message)
        return {"host": host, "model": model, "isolated": token not in reply.text,
                "reply": reply.text.strip()[:400], "seconds": reply.seconds}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stage.py", description="常驻角色进程的实况演出舞台")
    sub = p.add_subparsers(dest="cmd", required=True)

    def scene_cmd(name: str, help_text: str, tryout: bool = False) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--work-dir", required=True)
        if tryout:
            which = sp.add_mutually_exclusive_group(required=True)
            which.add_argument("--scene-id")
            which.add_argument("--tryout", help="试演名，目录 pipeline/stage/tryout/<名>/")
        else:
            sp.add_argument("--scene-id", required=True)
        sp.add_argument("--lang", choices=["zh", "en"], help="默认按 run_state.yaml 的 language")
        return sp

    sp = scene_cmd("open", "按 setup.yaml 开场", tryout=True)
    sp.add_argument("--host", choices=["claude", "codex"], help="新进名册的人物默认用哪个宿主")
    sp.add_argument("--reperform", action="store_true", help="作废这一场的上一次演出并重演")

    sp = scene_cmd("run", "演出到下一个暂停点", tryout=True)
    sp.add_argument("--next", help="指定下一行动者（slug）")
    sp.add_argument("--extend", type=int, help="追加回合上限")

    sp = scene_cmd("event", "注入世界事件", tryout=True)
    sp.add_argument("--id", dest="event_id")
    sp.add_argument("--text")
    sp.add_argument("--perceived-by", help="谁能感知；默认在场所有人")

    sp = scene_cmd("enter", "迟到者登场", tryout=True)
    sp.add_argument("--slug", required=True)
    sp.add_argument("--view", required=True, help="他登场时看到、听到的场面")
    sp.add_argument("--arrival", help="在场者看到他到来的样子；默认“某某来了”")
    sp.add_argument("--perceived-by", help="谁注意到他到来；默认在场所有人")

    scene_cmd("close", "收场：正式场景收日记，试演做意图探针", tryout=True)

    sp = scene_cmd("line", "索句")
    sp.add_argument("--slug", required=True)
    sp.add_argument("--after", type=int, required=True, help="接在第几条之后")
    sp.add_argument("--cue", required=True, help="此刻人物面对什么，用故事内的话写")

    sp = sub.add_parser("invalidate", help="改变事实后作废这一场的日记与相关会话")
    sp.add_argument("--work-dir", required=True)
    sp.add_argument("--scene-id", required=True)
    sp.add_argument("--change", required=True, help="改了什么，只写进日志")

    sp = scene_cmd("amend", "作废后改正实况记录的一条")
    sp.add_argument("--n", type=int, required=True)
    sp.add_argument("--drop", action="store_true")
    for key in (*AMEND_FIELDS, *AMEND_LISTS):
        sp.add_argument(f"--{key.replace('_', '-')}", dest=key)

    scene_cmd("rediary", "按改正后的记录重写日记")

    sp = sub.add_parser("review", help="待核场景判为不受影响")
    sp.add_argument("--work-dir", required=True)
    sp.add_argument("--scene-id", required=True)
    sp.add_argument("--note")

    sp = scene_cmd("narrate", "从 POV 人物会话分叉讲述这一场")
    sp.add_argument("--slug", required=True)
    sp.add_argument("--guide", required=True, help="送给分叉的写作要点文件")
    sp.add_argument("--out")
    sp.add_argument("--model", help="讲述用的模型，默认沿用人物的模型")
    sp.add_argument("--effort")

    sp = scene_cmd("show", "渲染实况记录", tryout=True)
    sp.add_argument("--since", type=int, default=0)

    sp = sub.add_parser("interview", help="出戏访谈：从试演实例分叉，人物以演员身份回答")
    sp.add_argument("--work-dir", required=True)
    sp.add_argument("--tryout", required=True)
    sp.add_argument("--slug", required=True)
    sp.add_argument("--question", required=True)
    sp.add_argument("--lang", choices=["zh", "en"])

    sp = sub.add_parser("status", help="舞台与名册概况")
    sp.add_argument("--work-dir", required=True)

    sp = sub.add_parser("check-isolation", help="核验角色会话读不到外部文件")
    sp.add_argument("--host", choices=["claude", "codex"], required=True)
    sp.add_argument("--model")
    sp.add_argument("--effort")
    return p


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.cmd == "check-isolation":
        return cmd_check_isolation(args.host, args.model, args.effort)
    work = Work(Path(args.work_dir).resolve())
    if not work.pipeline.is_dir():
        raise StageError(f"{work.root} 下没有 pipeline/")
    lang = getattr(args, "lang", None)
    tryout = bool(getattr(args, "tryout", None))
    scene = getattr(args, "tryout", None) or getattr(args, "scene_id", None)
    if args.cmd == "open":
        return cmd_open(work, scene, args.host, args.reperform, lang, tryout)
    if args.cmd == "run":
        return cmd_run(work, scene, args.next, args.extend, lang, tryout)
    if args.cmd == "event":
        return cmd_event(work, scene, args.event_id, args.text, args.perceived_by, lang, tryout)
    if args.cmd == "enter":
        return cmd_enter(work, scene, args.slug, args.view, args.arrival, args.perceived_by, lang, tryout)
    if args.cmd == "close":
        return cmd_close(work, scene, lang, tryout)
    if args.cmd == "interview":
        return cmd_interview(work, scene, args.slug, args.question, lang)
    if args.cmd == "line":
        return cmd_line(work, scene, args.slug, args.after, args.cue, lang)
    if args.cmd == "invalidate":
        return cmd_invalidate(work, scene, args.change)
    if args.cmd == "amend":
        values = {k: getattr(args, k) for k in (*AMEND_FIELDS, *AMEND_LISTS)}
        return cmd_amend(work, scene, args.n, values, args.drop, lang)
    if args.cmd == "rediary":
        return cmd_rediary(work, scene, lang)
    if args.cmd == "review":
        return cmd_review(work, scene, args.note)
    if args.cmd == "narrate":
        return cmd_narrate(work, scene, args.slug, Path(args.guide),
                           Path(args.out) if args.out else None, lang, args.model, args.effort)
    if args.cmd == "show":
        return cmd_show(work, scene, args.since, lang, tryout)
    if args.cmd == "status":
        return cmd_status(work)
    raise StageError(f"未知命令 {args.cmd}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = dispatch(args)
    except StageError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return EXIT_INPUT
    except DriverError as exc:
        print(json.dumps({"error": str(exc), "category": exc.category}, ensure_ascii=False), file=sys.stderr)
        return EXIT_HOST
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
