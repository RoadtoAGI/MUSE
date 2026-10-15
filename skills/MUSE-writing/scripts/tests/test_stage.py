"""stage.py 的确定性测试：假驱动按剧本回话，不调用真实宿主。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

import stage

# ---------------------------------------------------------------- fixtures

PEOPLE = {"lu": "卢简", "wen": "温昭", "pei": "裴相", "dar": "达然"}


class FakeDriver:
    """按人物排好的回复队列；记录每次调用的模式、会话与消息。"""

    def __init__(self) -> None:
        self.queue: dict[str, list] = {}
        self.calls: list[dict] = []
        self.count = 0

    def say(self, slug: str, *replies) -> None:
        self.queue.setdefault(slug, []).extend(replies)

    def _next(self, slug: str, message: str) -> str:
        item = self.queue[slug].pop(0)
        if isinstance(item, Exception):
            raise item
        return item(message) if callable(item) else item

    def _new_id(self, slug: str) -> str:
        self.count += 1
        return f"{slug}-{self.count}"

    def spawn(self, spec, system, message):
        sid = self._new_id(spec.slug)
        self.calls.append({"mode": "spawn", "slug": spec.slug, "sid": sid, "system": system, "message": message})
        return stage.Reply(self._next(spec.slug, message), sid, 0.0)

    def resume(self, spec, sid, system, message):
        self.calls.append({"mode": "resume", "slug": spec.slug, "sid": sid, "message": message})
        return stage.Reply(self._next(spec.slug, message), sid, 0.0)

    def fork(self, spec, sid, system, message):
        new = self._new_id(spec.slug)
        self.calls.append({"mode": "fork", "slug": spec.slug, "sid": sid, "new": new, "message": message})
        return stage.Reply(self._next(spec.slug, message), new, 0.0)

    def once(self, spec, system, message):
        self.calls.append({"mode": "once", "slug": spec.slug, "system": system, "message": message})
        return stage.Reply(self._next(spec.slug, message), None, 0.0)

    def last(self, slug: str) -> dict:
        return [c for c in self.calls if c["slug"] == slug][-1]


@pytest.fixture
def fake(monkeypatch):
    driver = FakeDriver()
    monkeypatch.setattr(stage, "get_driver", lambda host: driver)
    monkeypatch.setenv("MUSE_STAGE_HOST", "claude")
    return driver


def make_work(tmp_path: Path, people=PEOPLE) -> stage.Work:
    pipe = tmp_path / "pipeline"
    (pipe).mkdir()
    (pipe / "run_state.yaml").write_text("language: zh\n", encoding="utf-8")
    for slug, name in people.items():
        room = pipe / "story-character-skills" / ".claude" / "skills" / slug
        room.mkdir(parents=True)
        (room / "SKILL.md").write_text(
            f"---\nname: {slug}\nversion: 1\n---\n\n# {name}\n\n<!-- 来源：phase2 -->\n你是{name}。\n", encoding="utf-8")
        (room / "state.md").write_text(f"# {name}\n\n> 给流水线读者的说明\n\n入场时很累。\n", encoding="utf-8")
        (room / "build-meta.yaml").write_text(
            yaml.safe_dump({"character_slug": slug, "character_display_name": name}, allow_unicode=True),
            encoding="utf-8")
    return stage.Work(tmp_path)


def role_view(work: stage.Work, scene: str, slug: str, cues=("灯很暗",), known=(), limits=()) -> None:
    path = work.role_view_path(scene, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({
        "scene_id": scene, "character": slug, "known_now": list(known),
        "observable_stimuli": [{"id": f"cue_{i}", "cue": c} for i, c in enumerate(cues, 1)],
        "constraints_now": list(limits)}, allow_unicode=True), encoding="utf-8")


def setup(work: stage.Work, scene: str, **kw) -> None:
    data = {"scene_id": scene, "present": ["lu", "wen"], "pov": "lu", "pause_every": 10, "max_turns": 20}
    data.update(kw)
    path = work.setup_path(scene)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    for slug in [*data["present"], *(data.get("late") or [])]:
        if not work.role_view_path(scene, slug).exists():
            role_view(work, scene, slug)


def transcript(work, scene):
    return yaml.safe_load(work.transcript_path(scene).read_text(encoding="utf-8"))


def roster(work):
    return yaml.safe_load(work.roster_path.read_text(encoding="utf-8"))


def log_kinds(work, scene):
    return [e["kind"] for e in yaml.safe_load(work.log_path(scene).read_text(encoding="utf-8"))["entries"]]


def cast(people=PEOPLE, known_as=None) -> stage.Cast:
    return stage.Cast(dict(people), known_as or {})


ZH = stage.Voice("zh")
EN = stage.Voice("en")

# ---------------------------------------------------------------- role-facing text


def test_frames_have_same_keys_and_format_cleanly():
    frames = stage.load_frames()
    assert set(frames) == {"zh", "en"}
    assert set(frames["zh"]) == set(frames["en"])
    sample = {"name": "甲", "persona": "P", "index": 1, "labels": "乙", "actor": "乙", "to": "", "text": "t",
              "target": "丙", "problem": "p", "token": "x", "note": "n", "guide": "g", "question": "q"}
    for lang in frames:
        voice = stage.Voice(lang, frames)
        for key in frames[lang]:
            voice(key, **sample)


def test_persona_and_state_cleaning_drop_build_notes():
    work_text = "---\nname: a\n---\n\n# 甲\n<!-- 来源：phase2_character.yaml -->\n你是甲。\n"
    assert "来源" not in stage.clean_persona(work_text)
    assert stage.clean_persona(work_text).startswith("# 甲")
    assert stage.clean_state("# 甲\n> 给流水线的说明\n\n很累") == "# 甲\n\n很累"


def test_language_from_run_state_or_phase0(tmp_path):
    work = make_work(tmp_path)
    assert stage.work_language(work, None) == "zh"
    (work.pipeline / "run_state.yaml").write_text("run_intent: evaluation\n", encoding="utf-8")
    (work.pipeline / "phase0_conception.yaml").write_text("premise: A son comes home to a workshop.\n",
                                                          encoding="utf-8")
    assert stage.work_language(work, None) == "en"
    (work.pipeline / "phase0_conception.yaml").write_text("premise: 儿子回到作坊。\n", encoding="utf-8")
    assert stage.work_language(work, None) == "zh"
    assert stage.work_language(work, "en") == "en"


# ---------------------------------------------------------------- parsing


def test_parse_marks_with_names_and_quotes():
    text = "**【做】** 把酒杯从纸面上挪开。\n【说】“是谁雇你来的？”\n【对】温昭\n【闻】温昭\n【见】在场所有人"
    p = stage.parse_turn(text, "lu", ["lu", "wen", "pei"], "lu", cast(), ZH)
    assert p.problem is None
    e = p.entry
    assert e["does"] == "把酒杯从纸面上挪开。"
    assert e["says"] == "是谁雇你来的？"
    assert e["to"] == "wen"
    assert e["heard_by"] == ["wen"]
    assert e["seen_by"] == ["wen", "pei"]


def test_parse_english_tags_and_defaults():
    text = "[DO] reaches for the case\n[SAY] \"Give it here.\"\n[TO] wen"
    p = stage.parse_turn(text, "lu", ["lu", "wen", "pei"], None, cast(), EN)
    assert p.entry["to"] == "wen"
    assert p.entry["heard_by"] == ["wen", "pei"]
    assert p.entry["says"] == "Give it here."


def test_parse_multiline_content_and_stray_text():
    text = "我想了想。\n【说】先别动。\n那只箱子不是你的。"
    p = stage.parse_turn(text, "lu", ["lu", "wen"], None, cast(), ZH)
    assert p.entry["says"] == "先别动。\n那只箱子不是你的。"
    assert p.stray == "我想了想。"


def test_parse_multi_paragraph_speech_drops_inner_quotes():
    text = '【说】“睡得稳，被子够厚。”\n“夹袄不用翻。”\n“中午回来吃。”'
    p = stage.parse_turn(text, "lu", ["lu", "wen"], None, cast(), ZH)
    assert p.entry["says"] == "睡得稳，被子够厚。\n夹袄不用翻。\n中午回来吃。"


def test_parse_two_addressees_in_one_turn():
    text = ("【说】你答这个。\n【对】温昭\n【闻】在场所有人\n\n"
            "【说】你等一下再说。\n【对】裴相\n【闻】温昭、裴相")
    p = stage.parse_turn(text, "lu", ["lu", "wen", "pei", "dar"], None, cast(), ZH)
    assert p.problem is None
    assert p.entry["to"] == "wen" and "裴相" in p.entry["to_text"]
    assert p.entry["heard_by"] == ["wen", "pei", "dar"]


def test_parse_rejects_empty_turn():
    p = stage.parse_turn("他沉默。", "lu", ["lu", "wen"], None, cast(), ZH)
    assert p.entry is None and "既没有" in p.problem


def test_parse_rejects_unknown_audience_and_lists_labels():
    p = stage.parse_turn("【说】走\n【闻】掌柜", "lu", ["lu", "wen", "pei"], None, cast(), ZH)
    assert p.entry is None
    assert "掌柜" in p.problem and "温昭" in p.problem and "裴相" in p.problem


def test_parse_audience_none_and_lists():
    c = cast()
    p = stage.parse_turn("【做】低头\n【闻】无人\n【见】温昭和裴相", "lu", ["lu", "wen", "pei", "dar"], None, c, ZH)
    assert p.entry["heard_by"] == []
    assert p.entry["seen_by"] == ["wen", "pei"]


def test_parse_known_as_label_resolves_for_that_observer():
    c = cast(known_as={"lu": {"dar": "北边来的客人"}})
    p = stage.parse_turn("【说】您从哪儿来？\n【对】北边来的客人", "lu", ["lu", "dar"], None, c, ZH)
    assert p.entry["to"] == "dar"


def test_parse_unresolved_to_is_sent_back_for_correction():
    p = stage.parse_turn("【说】开门！\n【对】门外的人", "lu", ["lu", "wen"], None, cast(), ZH)
    assert p.entry is None
    assert "门外的人" in p.problem and "温昭" in p.problem


def test_parse_to_with_several_names_takes_first_and_keeps_text():
    p = stage.parse_turn("【说】请看\n【对】裴相，再对温昭", "lu", ["lu", "wen", "pei"], None, cast(), ZH)
    assert p.entry["to"] == "pei" and p.entry["to_text"] == "裴相，再对温昭"


def test_inner_only_kept_for_pov():
    pov = stage.parse_turn("【做】笑\n【想】他在撒谎", "lu", ["lu", "wen"], "lu", cast(), ZH)
    other = stage.parse_turn("【做】笑\n【想】他在撒谎", "wen", ["lu", "wen"], "lu", cast(), ZH)
    assert pov.entry["inner"] == "他在撒谎"
    assert "inner" not in other.entry and other.dropped_inner == "他在撒谎"


def test_wait_and_leave_marks():
    assert stage.parse_turn("【静】", "lu", ["lu", "wen"], None, cast(), ZH).entry["silent"] is True
    stare = stage.parse_turn("【静】盯着他", "lu", ["lu", "wen"], None, cast(), ZH).entry
    assert stare["does"] == "盯着他" and "silent" not in stare
    left = stage.parse_turn("【离】推门出去", "lu", ["lu", "wen"], None, cast(), ZH).entry
    assert left["leaves"] is True and left["does"] == "推门出去"


# ---------------------------------------------------------------- rendering


def _turn(**kw):
    base = {"n": 1, "kind": "turn", "actor": "lu", "heard_by": ["wen", "pei"], "seen_by": ["wen", "pei"]}
    base.update(kw)
    return base


def test_whisper_masks_speech_for_seeing_observer():
    e = _turn(does="凑近温昭耳边", says="别全信他", to="wen", heard_by=["wen"])
    assert stage.render_for(e, "wen", cast(), ZH) == ["卢简：凑近温昭耳边", "卢简（对你）：“别全信他”"]
    assert stage.render_for(e, "pei", cast(), ZH) == ["卢简：凑近温昭耳边", "卢简（对温昭）在说话，你听不清。"]


def test_hear_only_observer_gets_voice_without_action():
    e = _turn(does="放下茶杯", says="走吧", seen_by=["wen"])
    assert stage.render_for(e, "pei", cast(), ZH) == ["你听见卢简说：“走吧”"]


def test_unperceived_and_inner_never_reach_others():
    e = _turn(does="藏起信", says=None, heard_by=[], seen_by=[], inner="得快点")
    assert stage.render_for(e, "wen", cast(), ZH) == []
    assert not stage.perceives(e, "wen")


def test_observer_label_follows_known_as():
    c = cast(known_as={"wen": {"lu": "那个抄书的"}})
    assert stage.render_for(_turn(does="起身"), "wen", c, ZH) == ["那个抄书的：起身"]
    assert stage.render_for(_turn(does="起身"), "pei", c, ZH) == ["卢简：起身"]


# ---------------------------------------------------------------- performance


def test_open_run_and_resume_deliver_only_new_events(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", present=["lu", "wen", "pei"], initiative="lu", pause_every=2)
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", "【说】这首诗是我写的。\n【对】温昭")
    fake.say("wen", "【做】把卷轴收拢\n【说】你喝多了。\n【对】卢简")
    out = stage.cmd_run(work, "S01", None, None, None)
    assert out["reason"] == "checkpoint" and out["turns_this_run"] == 2
    first_lu, first_wen = fake.calls[0], fake.calls[1]
    assert first_lu["mode"] == "spawn" and "你是一名演员" in first_lu["system"] and "你是卢简" in first_lu["system"]
    assert "灯很暗" in first_lu["message"] and "入场时很累" in first_lu["message"]
    assert "给流水线读者的说明" not in first_lu["message"]
    assert "卢简（对你）：“这首诗是我写的。”" in first_wen["message"]
    fake.say("lu", "【静】")
    fake.say("pei", "【做】咳了一声")
    stage.cmd_run(work, "S01", None, None, None)
    resumed = [c for c in fake.calls if c["slug"] == "lu"][-1]
    assert resumed["mode"] == "resume"
    assert "这首诗是我写的" not in resumed["message"]
    assert "温昭：把卷轴收拢" in resumed["message"] and "灯很暗" not in resumed["message"]


def test_silent_observer_accumulates_events_until_first_turn(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", present=["lu", "wen", "pei"], initiative="lu", pause_every=3)
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", "【说】你先说。\n【对】温昭")
    fake.say("wen", "【说】凭什么。\n【对】卢简")
    fake.say("lu", "【做】拍桌")
    stage.cmd_run(work, "S01", None, None, None)
    fake.say("pei", "【说】都住口。")
    fake.say("wen", "【静】")
    fake.say("lu", "【静】")
    stage.cmd_run(work, "S01", "pei", None, None)
    msg = [c for c in fake.calls if c["slug"] == "pei"][0]["message"]
    assert "你先说" in msg and "凭什么" in msg and "拍桌" in msg and "灯很暗" in msg


def test_scheduling_order(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", present=["lu", "wen", "pei"], initiative="wen", pause_every=1)
    stage.cmd_open(work, "S01", None, False, None)
    sc = stage.Scene(work, "S01")
    assert sc.select_actor(["lu", "wen", "pei"], None) == ("wen", "initiative")
    fake.say("wen", "【说】裴相请看。\n【对】裴相")
    stage.cmd_run(work, "S01", None, None, None)
    sc = stage.Scene(work, "S01")
    assert sc.select_actor(["lu", "wen", "pei"], None) == ("pei", "addressed")
    assert sc.select_actor(["lu", "wen", "pei"], "lu") == ("lu", "designated")
    fake.say("pei", "【做】点头")
    stage.cmd_run(work, "S01", None, None, None)
    sc = stage.Scene(work, "S01")
    assert sc.select_actor(["lu", "wen", "pei"], None) == ("lu", "pending")


def test_invalid_turn_gets_one_correction(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu", pause_every=1)
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", "他笑了。", "【做】笑了一下")
    out = stage.cmd_run(work, "S01", None, None, None)
    assert out["reason"] == "checkpoint"
    assert "记不下来" in fake.calls[-1]["message"] and fake.calls[-1]["mode"] == "resume"
    assert transcript(work, "S01")["turns"][0]["does"] == "笑了一下"
    fake.say("wen", "嗯。", "还是嗯。")
    out = stage.cmd_run(work, "S01", None, None, None)
    assert out["reason"] == "invalid_turn" and out["detail"]["actor"] == "wen"
    assert len(transcript(work, "S01")["turns"]) == 1
    assert roster(work)["characters"]["wen"]["session"] is None
    fake.say("wen", "【说】好吧。")
    stage.cmd_run(work, "S01", "wen", None, None)
    rebuilt = fake.last("wen")
    assert rebuilt["mode"] == "spawn" and "笑了一下" in rebuilt["message"]


def test_pause_on_leave_silence_and_turn_limit(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu", pause_every=10, max_turns=3)
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", "【静】")
    fake.say("wen", "【静】")
    assert stage.cmd_run(work, "S01", None, None, None)["reason"] == "all_silent"
    fake.say("lu", "【说】走吧")
    assert stage.cmd_run(work, "S01", None, None, None)["reason"] == "max_turns"
    fake.say("wen", "【离】")
    out = stage.cmd_run(work, "S01", None, 1, None)
    assert out["reason"] == "left" and out["present"] == ["lu"]
    assert stage.cmd_run(work, "S01", None, None, None)["reason"] == "one_present"


def test_host_error_pauses_and_keeps_record(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu")
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", stage.DriverError("fatal", "quota"))
    out = stage.cmd_run(work, "S01", None, None, None)
    assert out["reason"] == "host_error" and out["detail"]["category"] == "fatal"


def test_late_entry_sees_only_entry_view(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu", late=["dar"], pause_every=1)
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", "【说】他不会来了。")
    stage.cmd_run(work, "S01", None, None, None)
    stage.cmd_enter(work, "S01", "dar", "厅里两个人在争执，桌上摊着卷轴。", "门帘一掀，达然进来。", None, None)
    fake.say("wen", "【做】起身行礼\n【对】达然")
    stage.cmd_run(work, "S01", "wen", None, None)
    assert "门帘一掀，达然进来。" in fake.last("wen")["message"]
    fake.say("dar", "【说】打扰了。")
    stage.cmd_run(work, "S01", "dar", None, None)
    msg = fake.last("dar")["message"]
    assert "厅里两个人在争执" in msg and "温昭：起身行礼" in msg
    assert "他不会来了" not in msg and "灯很暗" not in msg


def test_world_event_routes_to_perceivers(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", present=["lu", "wen", "pei"], initiative="lu", pause_every=1,
          world_events=[{"id": "plate", "text": "盘子落地碎了。"}])
    stage.cmd_open(work, "S01", None, False, None)
    stage.cmd_event(work, "S01", "plate", None, "温昭", None)
    fake.say("lu", "【静】")
    stage.cmd_run(work, "S01", None, None, None)
    fake.say("wen", "【做】低头看")
    stage.cmd_run(work, "S01", "wen", None, None)
    assert "盘子落地碎了" not in fake.last("lu")["message"]
    assert "盘子落地碎了" in fake.last("wen")["message"]


# ---------------------------------------------------------------- diaries and memory


def _perform(work, fake, scene, lines, **kw):
    setup(work, scene, initiative="lu", pause_every=len(lines), **kw)
    stage.cmd_open(work, scene, None, False, None)
    for slug, text in lines:
        fake.say(slug, text)
    stage.cmd_run(work, scene, None, None, None)
    people = stage.ever_present(stage.load_setup(work, scene), transcript(work, scene))
    for slug in people:
        fake.say(slug, f"{slug} 的 {scene} 日记")
    return stage.cmd_close(work, scene, None)


def test_close_writes_diaries_for_everyone_present(tmp_path, fake):
    work = make_work(tmp_path)
    out = _perform(work, fake, "S01", [("lu", "【说】嗯"), ("wen", "【说】嗯")], present=["lu", "wen", "pei"])
    assert out["status"] == "closed" and set(out["diaries"]) == {"lu", "wen", "pei"}
    assert work.diary_path("pei", "S01").read_text(encoding="utf-8").strip() == "pei 的 S01 日记"
    pei_call = fake.last("pei")
    assert pei_call["mode"] == "spawn" and "卢简：“嗯”" in pei_call["message"]
    r = roster(work)["characters"]
    assert r["lu"]["entries"] == [{"id": "S01"}] and r["lu"]["session"]["memory"] == ["S01"]
    assert r["lu"]["session"]["scene"] is None
    assert stage.scene_state(work, "S01") == "closed"


def test_next_scene_resumes_and_flashback_rebuilds_without_future(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    assert fake.last("lu")["mode"] == "resume"
    setup(work, "S03", initiative="lu", pause_every=1, story_after=["S01"])
    stage.cmd_open(work, "S03", None, False, None)
    fake.say("lu", "【说】倒叙里的话")
    stage.cmd_run(work, "S03", None, None, None)
    call = fake.last("lu")
    assert call["mode"] == "spawn"
    assert "lu 的 S01 日记" in call["message"] and "lu 的 S02 日记" not in call["message"]


def test_persona_version_change_rebuilds_session_but_copying_does_not(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    skill = work.room("lu") / "SKILL.md"
    import os
    st = skill.stat()
    os.utime(skill, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))  # 复制目录式的修改时间变化
    setup(work, "S02", initiative="lu", pause_every=1)
    stage.cmd_open(work, "S02", None, False, None)
    fake.say("lu", "【说】还是我")
    stage.cmd_run(work, "S02", None, None, None)
    assert fake.last("lu")["mode"] == "resume"
    fake.say("lu", "lu 的 S02 日记")
    fake.say("wen", "wen 的 S02 日记")
    stage.cmd_close(work, "S02", None)
    skill.write_text(skill.read_text(encoding="utf-8").replace("version: 1", "version: 2") + "\n新增一段。\n",
                     encoding="utf-8")
    setup(work, "S03", initiative="lu", pause_every=1)
    stage.cmd_open(work, "S03", None, False, None)
    fake.say("lu", "【说】又见面了")
    stage.cmd_run(work, "S03", None, None, None)
    assert fake.last("lu")["mode"] == "spawn" and "lu 的 S02 日记" in fake.last("lu")["message"]


def test_changing_model_in_roster_rebuilds_session(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    data = roster(work)
    data["characters"]["lu"]["model"] = "opus"
    work.roster_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    setup(work, "S02", initiative="lu", pause_every=1)
    stage.cmd_open(work, "S02", None, False, None)
    fake.say("lu", "【说】换了个人演")
    stage.cmd_run(work, "S02", None, None, None)
    assert fake.last("lu")["mode"] == "spawn"
    assert roster(work)["characters"]["lu"]["session"]["model"] == "opus"


def test_missing_session_is_rebuilt_once(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    setup(work, "S02", initiative="lu", pause_every=1)
    stage.cmd_open(work, "S02", None, False, None)
    fake.say("lu", stage.DriverError("missing_session", "No conversation found"), "【说】重来")
    stage.cmd_run(work, "S02", None, None, None)
    modes = [c["mode"] for c in fake.calls if c["slug"] == "lu"][-2:]
    assert modes == ["resume", "spawn"]
    assert transcript(work, "S02")["turns"][0]["says"] == "重来"


def test_offstage_note_is_delivered_before_scene(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    setup(work, "S02", initiative="lu", pause_every=1)
    note = work.offstage_path("S02", "lu")
    note.parent.mkdir(parents=True)
    note.write_text("你在码头等了一夜，船没来。", encoding="utf-8")
    fake.say("lu", "那一夜很冷。")
    out = stage.cmd_open(work, "S02", None, False, None)
    assert out["offstage_delivered"] == ["lu"]
    assert "船没来" in fake.last("lu")["message"] and fake.last("lu")["mode"] == "resume"
    assert work.diary_path("lu", "S02.offstage").read_text(encoding="utf-8").strip() == "那一夜很冷。"
    member = roster(work)["characters"]["lu"]
    assert member["session"]["memory"] == ["S01", "S02.offstage"]
    fake.say("lu", "【说】早")
    stage.cmd_run(work, "S02", None, None, None)
    assert fake.last("lu")["mode"] == "resume"


# ---------------------------------------------------------------- invalidation and correction


def test_invalidate_voids_diaries_sessions_and_marks_later(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    out = stage.cmd_invalidate(work, "S01", "卢简那句话其实没人听见")
    assert set(out["voided_diaries"]) == {"lu", "wen"} and out["pending_review"] == ["S02"]
    assert not work.diary_path("lu", "S01").exists()
    assert list((work.stage / "void" / "lu").glob("S01-*.md"))
    r = roster(work)["characters"]
    assert r["lu"]["session"] is None
    assert r["lu"]["entries"][0] == {"id": "S01", "void": True}
    assert stage.scene_state(work, "S01") == "void"
    assert stage.pending_review(work, "S02")["because"] == "S01"
    stage.cmd_review(work, "S02", "不受影响")
    assert stage.pending_review(work, "S02") is None


def test_amend_and_rediary_follow_the_corrected_record(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】那批货是我藏的。"), ("wen", "【做】走开")])
    _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    stage.cmd_invalidate(work, "S01", "卢简那句话温昭没听见")
    values = {k: None for k in (*stage.AMEND_FIELDS, *stage.AMEND_LISTS)}
    values["heard_by"] = "无人"
    stage.cmd_amend(work, "S01", 1, values, False, None)
    fake.say("lu", "lu 重写的日记")
    fake.say("wen", "wen 重写的日记")
    out = stage.cmd_rediary(work, "S01", None)
    assert out["status"] == "closed"
    wen_call = fake.last("wen")
    assert wen_call["mode"] == "spawn"
    assert "那批货是我藏的" not in wen_call["message"] and "听不清" in wen_call["message"]
    assert "wen 的 S02 日记" not in wen_call["message"]
    lu_call = fake.last("lu")
    assert "你说：“那批货是我藏的。”" in lu_call["message"]
    r = roster(work)["characters"]["wen"]
    assert r["entries"] == [{"id": "S01"}, {"id": "S02"}]
    assert r["session"]["memory"] == ["S01"]
    assert work.diary_path("wen", "S01").read_text(encoding="utf-8").strip() == "wen 重写的日记"
    assert stage.scene_state(work, "S01") == "closed"


def test_amend_requires_invalidation_first(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    values = {k: None for k in (*stage.AMEND_FIELDS, *stage.AMEND_LISTS)}
    with pytest.raises(stage.StageError, match="已收场"):
        stage.cmd_amend(work, "S01", 1, values, True, None)


def test_reperform_archives_take_and_starts_fresh(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    out = stage.cmd_open(work, "S01", None, True, None)
    assert out["take"] == 2 and out["story_after"] == []
    assert (work.scene_dir("S01") / "takes" / "take-1" / "transcript.yaml").exists()
    assert transcript(work, "S01")["turns"] == []
    fake.say("lu", "【说】重来一遍")
    fake.say("wen", "【说】好")
    stage.cmd_run(work, "S01", None, None, None)
    call = [c for c in fake.calls if c["slug"] == "lu"][-1]
    assert call["mode"] == "spawn" and "日记" not in call["message"]


# ---------------------------------------------------------------- line requests and narration


def test_line_request_rebuilds_at_that_moment_and_is_not_delivered(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】箱子呢？\n【对】温昭"), ("wen", "【说】在后院。\n【对】卢简"),
                                 ("lu", "【做】起身去后院")])
    fake.say("wen", "【说】等等，钥匙在我这儿。\n【对】卢简")
    out = stage.cmd_line(work, "S01", "wen", 2, "卢简正要起身。", None)
    call = fake.last("wen")
    assert call["mode"] == "once" and "卢简正要起身。" in call["message"]
    assert "起身去后院" not in call["message"] and "wen 的 S01 日记" not in call["message"]
    assert "你说：“在后院。”" in call["message"] or "你（对卢简）说：“在后院。”" in call["message"]
    turns = transcript(work, "S01")["turns"]
    assert [t["n"] for t in turns] == [1, 2, 4, 3]
    assert turns[2]["kind"] == "line" and turns[2]["after"] == 2
    assert "钥匙" in out["added"]
    assert all(e.get("kind") != "line" for e in stage.performance(transcript(work, "S01")))


def test_narrate_forks_the_main_session(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    guide = tmp_path / "guide.md"
    guide.write_text("写作要点", encoding="utf-8")
    fake.say("lu", "那天夜里，我说了一。")
    out = stage.cmd_narrate(work, "S01", "lu", guide, None, None)
    call = fake.last("lu")
    assert call["mode"] == "fork" and call["sid"] == roster(work)["characters"]["lu"]["session"]["id"]
    assert (work.root / out["narration"]).read_text(encoding="utf-8").startswith("那天夜里")


# ---------------------------------------------------------------- setup, lock and drivers


def test_setup_validation_lists_problems(tmp_path):
    work = make_work(tmp_path)
    path = work.setup_path("S01")
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump({"scene_id": "S01", "present": ["lu"], "pov": "x", "pause_every": 0}),
                    encoding="utf-8")
    with pytest.raises(stage.StageError) as exc:
        stage.load_setup(work, "S01")
    msg = str(exc.value)
    assert "pause_every" in msg and "max_turns" in msg and "pov" in msg


def test_stage_lock_is_exclusive(tmp_path):
    with stage.stage_lock(tmp_path):
        with pytest.raises(stage.StageError, match="另一个舞台命令"):
            with stage.stage_lock(tmp_path):
                pass


def test_classify_errors():
    assert stage.classify("API Error: 529 overloaded") == "transient"
    assert stage.classify("No conversation found with session ID x") == "missing_session"
    assert stage.classify("usage limit reached") == "fatal"


def test_transient_errors_are_retried(monkeypatch):
    monkeypatch.setattr(stage.time, "sleep", lambda s: None)
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise stage.DriverError("transient", "overloaded")
        return stage.Reply("ok", "s", 0.0)

    assert stage._retrying(flaky).text == "ok" and len(attempts) == 3
    with pytest.raises(stage.DriverError):
        stage._retrying(lambda: (_ for _ in ()).throw(stage.DriverError("fatal", "no")))


def test_claude_driver_command_and_parsing(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["input"], seen["cwd"] = cmd, kw["input"], kw["cwd"]
        out = {"type": "result", "is_error": False, "result": "【说】好", "session_id": cmd[cmd.index("--session-id") + 1],
               "total_cost_usd": 0.01, "usage": {"input_tokens": 3, "output_tokens": 4}}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")

    monkeypatch.setattr(stage.subprocess, "run", fake_run)
    spec = stage.RoleSpec("lu", "claude", "sonnet", None, tmp_path, "muse-role lu")
    reply = stage.ClaudeDriver().spawn(spec, "SYSTEM", "MESSAGE")
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "" and "--safe-mode" in cmd and "--bare" not in cmd
    assert cmd[cmd.index("--system-prompt") + 1] == "SYSTEM" and seen["input"] == "MESSAGE"
    assert reply.text == "【说】好" and reply.session_id and seen["cwd"] == tmp_path


def test_claude_driver_reports_error_category(monkeypatch, tmp_path):
    out = {"type": "result", "is_error": True, "result": "No conversation found with session ID: abc"}
    monkeypatch.setattr(stage.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, json.dumps(out), ""))
    spec = stage.RoleSpec("lu", "claude", "sonnet", None, tmp_path, "n")
    with pytest.raises(stage.DriverError) as exc:
        stage.ClaudeDriver().resume(spec, "abc", "S", "M")
    assert exc.value.category == "missing_session"


def test_codex_parse_ignores_code_mode_notice():
    lines = [
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "item.completed", "item": {"type": "error", "message": "Code Mode is unavailable"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "【说】两文钱"}},
        {"type": "turn.completed", "usage": {"input_tokens": 9, "cached_input_tokens": 5, "output_tokens": 2}},
    ]
    proc = subprocess.CompletedProcess([], 0, "\n".join(json.dumps(x) for x in lines), "")
    reply = stage.CodexDriver._parse(proc, 1.0)
    assert reply.text == "【说】两文钱" and reply.session_id == "t-1"
    assert reply.usage["cache_read_input_tokens"] == 5
    failed = subprocess.CompletedProcess([], 1, json.dumps({"type": "turn.failed",
                                                              "error": {"message": "rate limit"}}), "")
    with pytest.raises(stage.DriverError) as exc:
        stage.CodexDriver._parse(failed, 1.0)
    assert exc.value.category == "transient"


def test_codex_parse_skips_notice_lines_and_reports_broken_events():
    event = {"type": "item.completed", "item": {"type": "agent_message", "text": "【静】"}}
    out = "WARNING: proceeding\n" + json.dumps(event)
    assert stage.CodexDriver._parse(subprocess.CompletedProcess([], 0, out, ""), 1.0).text == "【静】"
    broken = json.dumps(event)[:20]
    with pytest.raises(stage.DriverError, match="无法解析"):
        stage.CodexDriver._parse(subprocess.CompletedProcess([], 0, broken, ""), 1.0)


def test_codex_role_home_has_minimal_config_and_linked_auth(monkeypatch, tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    (main / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(main))
    monkeypatch.setenv("MUSE_CODEX_ROLE_HOME", str(tmp_path / "role"))
    home = stage.ensure_codex_role_home()
    assert (home / "auth.json").is_symlink() and (home / "auth.json").resolve() == (main / "auth.json")
    cfg = (home / "config.toml").read_text(encoding="utf-8")
    assert "shell_tool = false" in cfg and "project_doc_max_bytes = 0" in cfg
    assert stage.ensure_codex_role_home() == home


def test_codex_spawn_passes_frame_file_and_cleans_up(monkeypatch, tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    (main / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(main))
    monkeypatch.setenv("MUSE_CODEX_ROLE_HOME", str(tmp_path / "role"))
    seen = {}

    def fake_run(cmd, **kw):
        frame = [c for c in cmd if c.startswith("model_instructions_file=")][0].split("=", 1)[1]
        seen["frame_text"] = Path(json.loads(frame)).read_text(encoding="utf-8")
        seen["cmd"], seen["env"] = cmd, kw["env"]
        out = [{"type": "thread.started", "thread_id": "t-9"},
               {"type": "item.completed", "item": {"type": "agent_message", "text": "【静】"}}]
        return subprocess.CompletedProcess(cmd, 0, "\n".join(json.dumps(x) for x in out), "")

    monkeypatch.setattr(stage.subprocess, "run", fake_run)
    spec = stage.RoleSpec("lu", "codex", "gpt-x", "medium", tmp_path, "n")
    reply = stage.CodexDriver().spawn(spec, "FRAME", "MSG")
    assert seen["frame_text"] == "FRAME" and seen["env"]["CODEX_HOME"] == str(tmp_path / "role")
    assert "model_reasoning_effort=medium" in seen["cmd"] and seen["cmd"][-1] == "-"
    assert reply.session_id == "t-9" and not list((tmp_path / "role" / "frames").iterdir())


# ---------------------------------------------------------------- tryouts


def tryout_setup(work, name, **kw):
    data = {"scene_id": name, "present": ["lu", "wen"], "pause_every": 2, "max_turns": 6,
            "situation": "码头上，船迟了一夜还没到。", "views": {"lu": "你口袋里有一张没兑的船票。"}}
    data.update(kw)
    path = work.tryout_dir(name) / "setup.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_tryout_forks_current_formal_session_and_never_writes_back(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    formal_before = work.roster_path.read_text(encoding="utf-8")
    lu_formal = roster(work)["characters"]["lu"]["session"]["id"]
    tryout_setup(work, "dock", initiative="lu")
    out = stage.cmd_open(work, "dock", None, False, None, tryout=True)
    assert out["tryout"] is True and out["offstage_delivered"] == []
    fake.say("lu", "【说】船呢？")
    fake.say("wen", "【静】")
    stage.cmd_run(work, "dock", None, None, None, tryout=True)
    lu_call = [c for c in fake.calls if c["slug"] == "lu"][-1]
    assert lu_call["mode"] == "fork" and lu_call["sid"] == lu_formal
    assert "码头上" in lu_call["message"] and "没兑的船票" in lu_call["message"]
    assert "lu 的 S01 日记" not in lu_call["message"]
    fake.say("lu", "我想先走。")
    fake.say("wen", "我怕他走。")
    out = stage.cmd_close(work, "dock", None, tryout=True)
    assert set(out["probes"]) == {"lu", "wen"}
    assert (work.tryout_dir("dock") / "probes" / "lu.md").read_text(encoding="utf-8").strip() == "我想先走。"
    assert work.roster_path.read_text(encoding="utf-8") == formal_before
    assert not work.diary_path("lu", "dock").exists()


def test_tryout_without_formal_session_rebuilds_from_diaries(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    data = roster(work)
    data["characters"]["lu"]["session"] = None
    work.roster_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    tryout_setup(work, "dock", initiative="lu")
    stage.cmd_open(work, "dock", None, False, None, tryout=True)
    fake.say("lu", "【说】船呢？")
    fake.say("wen", "【静】")
    stage.cmd_run(work, "dock", None, None, None, tryout=True)
    lu_call = [c for c in fake.calls if c["slug"] == "lu"][-1]
    assert lu_call["mode"] == "spawn" and "lu 的 S01 日记" in lu_call["message"]


def test_interview_forks_the_tryout_instance(tmp_path, fake):
    work = make_work(tmp_path)
    tryout_setup(work, "dock", initiative="lu")
    stage.cmd_open(work, "dock", None, False, None, tryout=True)
    fake.say("lu", "【说】船呢？")
    fake.say("wen", "【静】")
    stage.cmd_run(work, "dock", None, None, None, tryout=True)
    tryout_sid = yaml.safe_load((work.tryout_dir("dock") / "roster.yaml").read_text(encoding="utf-8"))[
        "characters"]["lu"]["session"]["id"]
    fake.say("lu", "我当时以为他在拖时间。")
    out = stage.cmd_interview(work, "dock", "lu", "你为什么先问船？", None)
    call = fake.last("lu")
    assert call["mode"] == "fork" and call["sid"] == tryout_sid and "演员" in call["message"]
    assert "你为什么先问船" in (work.root / out["interview"]).read_text(encoding="utf-8")


def test_tryout_rejects_formal_only_operations_and_needs_situation(tmp_path, fake):
    work = make_work(tmp_path)
    tryout_setup(work, "dock", situation="")
    with pytest.raises(stage.StageError, match="situation"):
        stage.cmd_open(work, "dock", None, False, None, tryout=True)


# ---------------------------------------------------------------- recovery after host failures


def test_close_retry_keeps_written_diaries_and_reperform_voids_them(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu", pause_every=2)
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", "【说】一")
    fake.say("wen", "【说】二")
    stage.cmd_run(work, "S01", None, None, None)
    fake.say("lu", "lu 的日记")
    fake.say("wen", stage.DriverError("fatal", "authentication failed"))
    out = stage.cmd_close(work, "S01", None)
    assert out["status"] == "open" and "wen" in out["errors"]
    lu_diary = work.diary_path("lu", "S01").read_bytes()
    fake.say("wen", "wen 的日记")
    out = stage.cmd_close(work, "S01", None)
    assert out["status"] == "closed" and set(out["diaries"]) == {"lu", "wen"}
    assert work.diary_path("lu", "S01").read_bytes() == lu_diary
    assert [c["slug"] for c in fake.calls[-1:]] == ["wen"]
    assert roster(work)["characters"]["lu"]["session"]["memory"] == ["S01"]
    # 部分收场后直接重演：已写的日记随之作废，新一场重新收
    setup(work, "S02", initiative="lu", pause_every=2)
    stage.cmd_open(work, "S02", None, False, None)
    fake.say("lu", "【说】三")
    fake.say("wen", "【说】四")
    stage.cmd_run(work, "S02", None, None, None)
    fake.say("lu", "lu 的 S02 日记")
    fake.say("wen", stage.DriverError("fatal", "authentication failed"))
    stage.cmd_close(work, "S02", None)
    assert work.diary_path("lu", "S02").exists()
    stage.cmd_open(work, "S02", None, True, None)
    assert not work.diary_path("lu", "S02").exists()
    assert {"id": "S02", "void": True} in roster(work)["characters"]["lu"]["entries"]


def test_run_refuses_until_offstage_note_is_delivered(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu", pause_every=1)
    note = work.offstage_path("S01", "lu")
    note.parent.mkdir(parents=True)
    note.write_text("你昨夜看见桥断了。", encoding="utf-8")
    fake.say("lu", stage.DriverError("fatal", "authentication failed"))
    out = stage.cmd_open(work, "S01", None, False, None)
    assert "lu" in out["errors"]
    with pytest.raises(stage.StageError, match="场外补记还没送达"):
        stage.cmd_run(work, "S01", None, None, None)
    fake.say("lu", "桥断了。", "【说】早")
    stage.cmd_open(work, "S01", None, False, None)
    stage.cmd_run(work, "S01", None, None, None)
    assert transcript(work, "S01")["turns"][0]["says"] == "早"


def test_main_exit_code_reports_host_failures(tmp_path, fake, capsys):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu", pause_every=1)
    assert stage.main(["open", "--work-dir", str(work.root), "--scene-id", "S01"]) == 0
    capsys.readouterr()
    fake.say("lu", stage.DriverError("fatal", "authentication failed"))
    assert stage.main(["run", "--work-dir", str(work.root), "--scene-id", "S01"]) == stage.EXIT_HOST
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "host_error"
    fake.say("lu", "【静】")
    assert stage.main(["run", "--work-dir", str(work.root), "--scene-id", "S01"]) == 0


def test_line_correction_is_a_second_one_off_instance(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】箱子呢？"), ("wen", "【说】在后院。")])
    fake.say("wen", "他点点头。", "【说】钥匙在我这儿。")
    stage.cmd_line(work, "S01", "wen", 1, "卢简问完箱子。", None)
    modes = [c["mode"] for c in fake.calls if c["slug"] == "wen"][-2:]
    assert modes == ["once", "once"]
    assert "记不下来" in fake.last("wen")["message"] and "卢简问完箱子。" in fake.last("wen")["message"]


# ---------------------------------------------------------------- gate R2: failure classes, close, rediary, invalidate


def _scene(work, fake, scene, present, lines, diaries=True):
    """按 present 开场、演完 lines、收场；diaries=False 时只演不收。"""
    setup(work, scene, present=list(present), pov=present[0], initiative=present[0], pause_every=len(lines))
    stage.cmd_open(work, scene, None, False, None)
    for slug, text in lines:
        fake.say(slug, text)
    stage.cmd_run(work, scene, None, None, None)
    if not diaries:
        return None
    for slug in stage.ever_present(stage.load_setup(work, scene), transcript(work, scene)):
        fake.say(slug, f"{slug} 的 {scene} 日记")
    return stage.cmd_close(work, scene, None)


def _drop_session(work, slug):
    data = roster(work)
    data["characters"][slug]["session"] = None
    work.roster_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def _cli(capsys, verb, work, scene):
    rc = stage.main([verb, "--work-dir", str(work.root), "--scene-id", scene])
    return rc, json.loads(capsys.readouterr().out)


def _claude_host(monkeypatch, replies):
    """真实的 ClaudeDriver，只把外部 claude 进程换成按人物回话的替身；返回被调用的人物序列。"""
    called = []

    def run(cmd, **kw):
        slug = Path(kw["cwd"]).name
        called.append(slug)
        sid = next((cmd[cmd.index(flag) + 1] for flag in ("--session-id", "--resume") if flag in cmd), "once")
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"result": replies[slug].pop(0), "session_id": sid}), "")

    monkeypatch.setattr(stage, "get_driver", lambda host: stage.ClaudeDriver())
    monkeypatch.setattr(stage.subprocess, "run", run)
    return called


def test_blank_host_reply_is_a_host_failure_on_both_drivers(monkeypatch, tmp_path):
    blank = {"type": "result", "is_error": False, "result": "  \n ", "session_id": "s"}
    monkeypatch.setattr(stage.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, json.dumps(blank), ""))
    spec = stage.RoleSpec("lu", "claude", "sonnet", None, tmp_path, "n")
    with pytest.raises(stage.DriverError) as exc:
        stage.ClaudeDriver().resume(spec, "s", "S", "M")
    assert exc.value.category == "empty_reply"
    events = [{"type": "thread.started", "thread_id": "t-1"},
              {"type": "item.completed", "item": {"type": "agent_message", "text": "\n  "}}]
    proc = subprocess.CompletedProcess([], 0, "\n".join(json.dumps(e) for e in events), "")
    with pytest.raises(stage.DriverError) as exc:
        stage.CodexDriver._parse(proc, 1.0)
    assert exc.value.category == "empty_reply"


def test_gate_r2_close_blank_reply_keeps_others_and_retry_asks_only_the_missing(tmp_path, fake, monkeypatch, capsys):
    work = make_work(tmp_path)
    _scene(work, fake, "S01", ["lu", "wen", "pei"], [("lu", "【说】嗯")], diaries=False)
    replies = {"lu": ["lu 的日记"], "wen": [" \n "], "pei": ["pei 的日记"]}
    called = _claude_host(monkeypatch, replies)
    rc, out = _cli(capsys, "close", work, "S01")
    assert rc == stage.EXIT_HOST and out["status"] == "open"
    assert out["error_kinds"] == {"wen": "host"} and "回复为空" in out["errors"]["wen"]
    assert not work.diary_path("wen", "S01").exists()
    wen = roster(work)["characters"]["wen"]
    assert wen["entries"] == [] and wen["session"] is None
    kept = {s: work.diary_path(s, "S01").read_bytes() for s in ("lu", "pei")}
    replies["wen"].append("wen 的日记")
    called.clear()
    rc, out = _cli(capsys, "close", work, "S01")
    assert rc == 0 and out["status"] == "closed" and called == ["wen"]
    assert {s: work.diary_path(s, "S01").read_bytes() for s in ("lu", "pei")} == kept
    assert work.diary_path("wen", "S01").read_text(encoding="utf-8") == "wen 的日记\n"
    assert all(m["entries"] == [{"id": "S01"}] for m in roster(work)["characters"].values())


def test_gate_r2_close_uses_command_language_and_each_own_diary_request(tmp_path, fake):
    work = make_work(tmp_path)  # 作品语言是中文
    setup(work, "S01", initiative="lu", pause_every=2)
    stage.cmd_open(work, "S01", None, False, "en")
    fake.say("lu", "[SAY] Where is the case?")
    fake.say("wen", "[SAY] Out back.")
    stage.cmd_run(work, "S01", None, None, "en")
    fake.say("lu", "lu diary")
    fake.say("wen", "wen diary")
    stage.cmd_close(work, "S01", "en")
    for slug, other in (("lu", "wen"), ("wen", "lu")):
        msg = fake.last(slug)["message"]
        assert EN("diary_prompt", name=PEOPLE[slug]) in msg
        assert ZH("diary_prompt", name=PEOPLE[slug]) not in msg
        assert EN("diary_prompt", name=PEOPLE[other]) not in msg
    assert "Out back." in fake.last("lu")["message"]  # 收日记前补上它还没看到的那一回合
    assert work.diary_path("lu", "S01").read_text(encoding="utf-8") == "lu diary\n"


def test_gate_r2_rediary_uses_command_language_and_own_diary_request(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    stage.cmd_invalidate(work, "S01", "改一处")
    fake.say("lu", "lu diary")
    fake.say("wen", "wen diary")
    stage.cmd_rediary(work, "S01", "en")
    for slug in ("lu", "wen"):
        call = fake.last(slug)
        assert call["mode"] == "spawn"
        assert call["system"].startswith(f"You are an actor playing {PEOPLE[slug]}")
        assert call["message"].rstrip().endswith(EN("diary_prompt", name=PEOPLE[slug]))
    stage.cmd_invalidate(work, "S01", "再改一处")
    fake.say("lu", "lu 的日记")
    fake.say("wen", "wen 的日记")
    stage.cmd_rediary(work, "S01", None)
    assert fake.last("lu")["message"].rstrip().endswith(ZH("diary_prompt", name="卢简"))


def test_gate_r2_close_and_rediary_do_not_tell_the_departed_who_came_later(tmp_path, fake):
    work = make_work(tmp_path)
    setup(work, "S01", initiative="lu", pause_every=2, late=["dar"])
    stage.cmd_open(work, "S01", None, False, None)
    fake.say("lu", "【说】我先走了。\n【离】")
    assert stage.cmd_run(work, "S01", None, None, None)["reason"] == "left"
    stage.cmd_enter(work, "S01", "dar", "厅里只剩温昭。", "达然推门进来。", None, None)
    fake.say("wen", "【说】你来晚了。\n【对】达然")
    fake.say("dar", "【说】路上耽搁了。")
    stage.cmd_run(work, "S01", "wen", None, None)
    for slug in ("lu", "wen", "dar"):
        fake.say(slug, f"{slug} 的日记")
    assert stage.cmd_close(work, "S01", None)["status"] == "closed"
    msg = fake.last("lu")["message"]
    assert "达然" not in msg and "【在场】" not in msg
    stage.cmd_invalidate(work, "S01", "改一处")
    for slug in ("lu", "wen", "dar"):
        fake.say(slug, f"{slug} 重写的日记")
    stage.cmd_rediary(work, "S01", None)
    msg = fake.last("lu")["message"]
    assert "我先走了" in msg and "达然" not in msg and "【在场】" not in msg


def test_gate_r2_close_first_failure_keeps_later_results_and_retry_returns_every_diary(tmp_path, fake):
    work = make_work(tmp_path)
    _scene(work, fake, "S01", ["lu", "wen", "pei"], [("lu", "【说】嗯")], diaries=False)
    fake.say("lu", stage.DriverError("fatal", "authentication failed"))
    fake.say("wen", "wen 的日记")
    fake.say("pei", "pei 的日记")
    out = stage.cmd_close(work, "S01", None)
    assert out["scene_id"] == "S01" and out["status"] == "open"
    assert out["error_kinds"] == {"lu": "host"} and set(out["errors"]) == {"lu"}
    assert out["diaries"] == {s: work.rel(work.diary_path(s, "S01")) for s in ("wen", "pei")}
    kept = {s: work.diary_path(s, "S01").read_bytes() for s in ("wen", "pei")}
    sessions = {s: roster(work)["characters"][s]["session"]["id"] for s in ("wen", "pei")}
    before = len(fake.calls)
    fake.say("lu", "lu 的日记")
    out = stage.cmd_close(work, "S01", None)
    assert out == {"scene_id": "S01", "status": "closed",
                   "diaries": {s: work.rel(work.diary_path(s, "S01")) for s in ("lu", "wen", "pei")}}
    for slug, rel in out["diaries"].items():
        assert (work.root / rel).read_text(encoding="utf-8") == f"{slug} 的日记\n"
    assert [c["slug"] for c in fake.calls[before:]] == ["lu"]
    assert {s: work.diary_path(s, "S01").read_bytes() for s in ("wen", "pei")} == kept
    r = roster(work)["characters"]
    assert {s: r[s]["session"]["id"] for s in ("wen", "pei")} == sessions
    assert all(r[s]["entries"] == [{"id": "S01"}] and r[s]["session"]["memory"] == ["S01"]
               for s in ("lu", "wen", "pei"))
    assert stage.scene_state(work, "S01") == "closed"


def test_gate_r2_close_mixed_failures_report_both_kinds(tmp_path, fake, capsys):
    work = make_work(tmp_path)
    _scene(work, fake, "S01", ["lu", "wen", "pei"], [("lu", "【说】一")])
    _scene(work, fake, "S02", ["lu", "wen", "pei"], [("lu", "【说】二")], diaries=False)
    work.diary_path("wen", "S01").unlink()
    _drop_session(work, "wen")
    fake.say("lu", "lu 的 S02 日记")
    fake.say("pei", stage.DriverError("fatal", "authentication failed"))
    rc, out = _cli(capsys, "close", work, "S02")
    assert rc == stage.EXIT_HOST and out["status"] == "open"
    assert out["error_kinds"] == {"wen": "state", "pei": "host"}
    assert out["diaries"] == {"lu": work.rel(work.diary_path("lu", "S02"))}
    fake.say("pei", "pei 的 S02 日记")
    rc, out = _cli(capsys, "close", work, "S02")
    assert rc == stage.EXIT_INPUT and out["error_kinds"] == {"wen": "state"}
    assert set(out["diaries"]) == {"lu", "pei"} and not work.diary_path("wen", "S02").exists()
    assert stage.scene_state(work, "S02") == "open"


def test_open_offstage_failures_keep_error_kinds(tmp_path, fake, capsys):
    work = make_work(tmp_path)
    _scene(work, fake, "S01", ["lu", "wen", "pei"], [("lu", "【说】一")])
    setup(work, "S02", present=["lu", "wen", "pei"], initiative="lu", pause_every=1)
    for slug in ("lu", "wen", "pei"):
        note = work.offstage_path("S02", slug)
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(f"{slug} 在码头等了一夜。", encoding="utf-8")
    work.diary_path("lu", "S01").unlink()
    _drop_session(work, "lu")
    fake.say("wen", stage.DriverError("fatal", "authentication failed"))
    fake.say("pei", "pei 记下了")
    rc, out = _cli(capsys, "open", work, "S02")
    assert rc == stage.EXIT_HOST and out["error_kinds"] == {"lu": "state", "wen": "host"}
    assert out["offstage_delivered"] == ["pei"]
    pei_note = work.diary_path("pei", "S02.offstage").read_bytes()
    fake.say("wen", "wen 记下了")
    rc, out = _cli(capsys, "open", work, "S02")
    assert rc == stage.EXIT_INPUT and out["error_kinds"] == {"lu": "state"}
    assert out["offstage_delivered"] == ["wen"]
    assert work.diary_path("pei", "S02.offstage").read_bytes() == pei_note


def test_gate_r2_rediary_covers_void_and_missing_diaries_and_resumes_after_failure(tmp_path, fake, capsys):
    work = make_work(tmp_path)
    _scene(work, fake, "S01", ["lu", "wen", "pei"], [("lu", "【说】嗯")], diaries=False)
    fake.say("lu", "lu 的日记")
    fake.say("wen", stage.DriverError("fatal", "authentication failed"))
    fake.say("pei", stage.DriverError("fatal", "authentication failed"))
    stage.cmd_close(work, "S01", None)
    stage.cmd_invalidate(work, "S01", "温昭其实没进门")  # 收场没完成就作废
    r = roster(work)["characters"]
    assert r["lu"]["entries"] == [{"id": "S01", "void": True}] and r["wen"]["entries"] == []
    fake.say("lu", stage.DriverError("fatal", "authentication failed"))
    fake.say("wen", "wen 重写的日记")
    fake.say("pei", "pei 重写的日记")
    rc, out = _cli(capsys, "rediary", work, "S01")
    assert rc == stage.EXIT_HOST
    assert out["scene_id"] == "S01" and out["status"] == "void"
    assert out["error_kinds"] == {"lu": "host"} and set(out["errors"]) == {"lu"}
    assert out["diaries"] == {s: work.rel(work.diary_path(s, "S01")) for s in ("wen", "pei")}
    assert stage.scene_state(work, "S01") == "void" and log_kinds(work, "S01")[-1] == "rediary_failed"
    assert not work.diary_path("lu", "S01").exists()
    kept = {s: work.diary_path(s, "S01").read_bytes() for s in ("wen", "pei")}
    sessions = {s: roster(work)["characters"][s]["session"]["id"] for s in ("wen", "pei")}
    before = len(fake.calls)
    fake.say("lu", "lu 重写的日记")
    out = stage.cmd_rediary(work, "S01", None)
    assert out["status"] == "closed" and out["errors"] == {} and set(out["diaries"]) == {"lu"}
    assert [c["slug"] for c in fake.calls[before:]] == ["lu"]
    assert "lu 的日记" not in fake.last("lu")["message"]
    assert {s: work.diary_path(s, "S01").read_bytes() for s in ("wen", "pei")} == kept
    r = roster(work)["characters"]
    assert {s: r[s]["session"]["id"] for s in ("wen", "pei")} == sessions
    assert all(r[s]["entries"] == [{"id": "S01"}] for s in ("lu", "wen", "pei"))
    assert stage.scene_state(work, "S01") == "closed"


def test_gate_r2_rediary_mixed_failures_keep_kinds_and_finish_later(tmp_path, fake, capsys):
    work = make_work(tmp_path)
    _scene(work, fake, "S01", ["lu", "wen", "pei"], [("lu", "【说】一")])
    _scene(work, fake, "S02", ["lu", "wen", "pei"], [("lu", "【说】二")])
    stage.cmd_invalidate(work, "S02", "改一处")
    lu_s01 = work.diary_path("lu", "S01")
    saved = lu_s01.read_bytes()
    lu_s01.unlink()
    fake.say("wen", stage.DriverError("fatal", "authentication failed"))
    fake.say("pei", "pei 重写的日记")
    rc, out = _cli(capsys, "rediary", work, "S02")
    assert rc == stage.EXIT_HOST and out["error_kinds"] == {"lu": "state", "wen": "host"}
    assert set(out["diaries"]) == {"pei"} and out["status"] == "void"
    fake.say("wen", "wen 重写的日记")
    rc, out = _cli(capsys, "rediary", work, "S02")
    assert rc == stage.EXIT_INPUT and out["error_kinds"] == {"lu": "state"} and set(out["diaries"]) == {"wen"}
    lu_s01.write_bytes(saved)
    fake.say("lu", "lu 重写的日记")
    rc, out = _cli(capsys, "rediary", work, "S02")
    assert rc == 0 and out["status"] == "closed" and set(out["diaries"]) == {"lu"}
    assert "lu 的 S01 日记" in fake.last("lu")["message"]


def test_gate_r2_rediary_keeps_offstage_memory_and_next_scene_resumes(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    note = work.offstage_path("S02", "lu")
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("你在码头等了一夜，船没来。", encoding="utf-8")
    fake.say("lu", "那一夜很冷。")
    _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    assert roster(work)["characters"]["lu"]["entries"] == [{"id": "S01"}, {"id": "S02.offstage"}, {"id": "S02"}]
    stage.cmd_invalidate(work, "S02", "温昭那句没说")
    fake.say("lu", "lu 重写的 S02 日记")
    fake.say("wen", "wen 重写的 S02 日记")
    stage.cmd_rediary(work, "S02", None)
    call = fake.last("lu")
    session = roster(work)["characters"]["lu"]["session"]
    assert call["mode"] == "spawn" and "那一夜很冷。" in call["message"]
    assert session["id"] == call["sid"] and session["memory"] == ["S01", "S02.offstage", "S02"]
    setup(work, "S03", initiative="lu", pause_every=1)
    stage.cmd_open(work, "S03", None, False, None)
    fake.say("lu", "【说】五")
    stage.cmd_run(work, "S03", None, None, None)
    assert fake.last("lu")["mode"] == "resume" and fake.last("lu")["sid"] == session["id"]


def test_gate_r2_invalidate_keeps_both_archives_from_the_same_second(tmp_path, fake, monkeypatch):
    import datetime
    import types

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 16, 2, 30, 0)

    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    monkeypatch.setattr(stage, "_dt", types.SimpleNamespace(datetime=Frozen))
    stage.cmd_invalidate(work, "S01", "第一次")
    fake.say("lu", "lu 重写的日记")
    fake.say("wen", "wen 重写的日记")
    stage.cmd_rediary(work, "S01", None)
    stage.cmd_invalidate(work, "S01", "第二次")
    archived = list((work.stage / "void" / "lu").glob("S01-20261016-023000*.md"))
    assert len(archived) == 2
    assert {p.read_text(encoding="utf-8").strip() for p in archived} == {"lu 的 S01 日记", "lu 重写的日记"}


def test_gate_r2_invalidate_marks_the_union_of_valid_later_scenes_only(tmp_path, fake):
    work = make_work(tmp_path)
    _scene(work, fake, "S00", ["lu", "pei"], [("lu", "【说】零")])
    _scene(work, fake, "S01", ["lu", "wen", "pei"], [("lu", "【说】一")])
    _scene(work, fake, "S02", ["lu", "dar"], [("lu", "【说】二")])
    _scene(work, fake, "S03", ["wen", "dar"], [("wen", "【说】三")])
    _scene(work, fake, "S04", ["lu", "dar"], [("lu", "【说】四")])
    stage.cmd_invalidate(work, "S04", "这一场重写")
    out = stage.cmd_invalidate(work, "S01", "温昭不在场")
    assert sorted(out["voided_diaries"]) == ["lu", "pei", "wen"] and out["pending_review"] == ["S02", "S03"]
    assert stage.pending_review(work, "S00") is None and stage.pending_review(work, "S04") is None
    assert stage.pending_review(work, "S02")["because"] == "S01"
    # 重演时再作废一次：已作废的条目不再算新的作废，也不重复标待核
    pending_s02 = log_kinds(work, "S02").count("pending_review")
    stage.cmd_open(work, "S01", None, True, None)
    archived = yaml.safe_load((work.scene_dir("S01") / "takes" / "take-1" / "log.yaml").read_text(encoding="utf-8"))
    last = [e for e in archived["entries"] if e["kind"] == "invalidate"][-1]
    assert last["change"] == "重演" and last["voided"] == [] and last["pending"] == []
    assert log_kinds(work, "S02").count("pending_review") == pending_s02


def test_gate_r2_invalidate_after_offstage_reperform_keeps_order_and_skips_itself(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    note = work.offstage_path("S01", "lu")
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("你在门外站了很久。", encoding="utf-8")
    fake.say("lu", "门外很冷。")
    assert stage.cmd_open(work, "S01", None, True, None)["offstage_delivered"] == ["lu"]
    fake.say("lu", "【说】再来")
    fake.say("wen", "【说】好")
    stage.cmd_run(work, "S01", None, None, None)
    fake.say("lu", "lu 的第二次日记")
    fake.say("wen", "wen 的第二次日记")
    stage.cmd_close(work, "S01", None)
    lu = roster(work)["characters"]["lu"]
    assert lu["entries"] == [{"id": "S01.offstage"}, {"id": "S01"}]
    assert lu["session"]["memory"] == ["S01.offstage", "S01"]
    out = _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    assert out["status"] == "closed"
    assert [c["mode"] for c in fake.calls if c["slug"] == "lu"][-2:] == ["resume", "resume"]
    out = stage.cmd_invalidate(work, "S01", "门外那段删掉")
    assert out["pending_review"] == ["S02"] and "pending_review" not in log_kinds(work, "S01")


def test_gate_r2_invalidate_open_scene_drops_only_its_sessions(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    _scene(work, fake, "S02", ["lu", "wen", "pei"], [("lu", "【说】三")], diaries=False)
    before = roster(work)["characters"]
    lu_sid, wen_session = before["lu"]["session"]["id"], before["wen"]["session"]
    assert before["lu"]["session"]["scene"]["id"] == "S02" and before["pei"]["session"] is None
    assert wen_session["scene"] is None and "S02" not in wen_session["memory"]
    out = stage.cmd_invalidate(work, "S02", "裴相其实不在")
    assert out == {"scene_id": "S02", "voided_diaries": [], "pending_review": [],
                   "invalidated_sessions": [{"actor": "lu", "session": lu_sid}]}
    after = roster(work)["characters"]
    assert after["lu"]["session"] is None and after["wen"]["session"] == wen_session
    assert after["pei"]["session"] is None
    assert stage.scene_state(work, "S02") == "void" and stage.scene_state(work, "S01") == "closed"


def test_gate_r2_invalidate_appends_to_each_log_and_keeps_the_change_from_roles(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    sids = {s: roster(work)["characters"][s]["session"]["id"] for s in ("lu", "wen")}
    logs = {s: yaml.safe_load(work.log_path(s).read_text(encoding="utf-8"))["entries"] for s in ("S01", "S02")}
    change = "卢简那句话温昭没听见"
    out = stage.cmd_invalidate(work, "S01", change)
    assert out["invalidated_sessions"] == [{"actor": "lu", "session": sids["lu"]},
                                           {"actor": "wen", "session": sids["wen"]}]
    for scene, kind in (("S01", "invalidate"), ("S02", "pending_review")):
        entries = yaml.safe_load(work.log_path(scene).read_text(encoding="utf-8"))["entries"]
        assert entries[:len(logs[scene])] == logs[scene]
        added = entries[len(logs[scene]):]
        assert [e["kind"] for e in added] == [kind] and added[0]["change"] == change
    status = stage.cmd_status(work)
    assert status["scenes"]["S02"]["pending_review"] == {"because": "S01", "change": change}
    assert status["scenes"]["S01"]["state"] == "void"
    before = len(fake.calls)
    fake.say("lu", "lu 重写的日记")
    fake.say("wen", "wen 重写的日记")
    stage.cmd_rediary(work, "S01", None)
    assert len(fake.calls) > before and all(change not in c["message"] for c in fake.calls[before:])


def _legacy_set_entry(member, entry_id):
    """a750800 及之前的写法：重演时新送达的补记追加在本场条目之后。旧名册里可能留着这种顺序。"""
    for e in member.setdefault("entries", []):
        if e["id"] == entry_id:
            e.pop("void", None)
            return
    member["entries"].append({"id": entry_id})


def test_gate_r3_invalidate_legacy_offstage_order_skips_itself(tmp_path, fake, monkeypatch):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    note = work.offstage_path("S01", "lu")
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("你在门外站了很久。", encoding="utf-8")
    with monkeypatch.context() as legacy:
        legacy.setattr(stage, "_set_entry", _legacy_set_entry)
        fake.say("lu", "门外很冷。")
        stage.cmd_open(work, "S01", None, True, None)
        fake.say("lu", "【说】再来")
        fake.say("wen", "【说】好")
        stage.cmd_run(work, "S01", None, None, None)
        fake.say("lu", "lu 的第二次日记")
        fake.say("wen", "wen 的第二次日记")
        stage.cmd_close(work, "S01", None)
        _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    lu = roster(work)["characters"]["lu"]
    assert lu["entries"] == [{"id": "S01"}, {"id": "S01.offstage"}, {"id": "S02"}]
    assert "S01" in lu["session"]["memory"]
    offstage = work.diary_path("lu", "S01.offstage").read_bytes()
    s02_log = yaml.safe_load(work.log_path("S02").read_text(encoding="utf-8"))["entries"]
    out = stage.cmd_invalidate(work, "S01", "门外那段删掉")
    assert out["pending_review"] == ["S02"] and sorted(out["voided_diaries"]) == ["lu", "wen"]
    assert "pending_review" not in log_kinds(work, "S01")
    status = stage.cmd_status(work)["scenes"]
    assert status["S01"]["pending_review"] is None and status["S01"]["state"] == "void"
    assert status["S02"]["pending_review"] == {"because": "S01", "change": "门外那段删掉"}
    entries = yaml.safe_load(work.log_path("S02").read_text(encoding="utf-8"))["entries"]
    assert entries[:len(s02_log)] == s02_log and [e["kind"] for e in entries[len(s02_log):]] == ["pending_review"]
    lu = roster(work)["characters"]["lu"]
    assert lu["entries"] == [{"id": "S01", "void": True}, {"id": "S01.offstage"}, {"id": "S02"}]
    assert lu["session"] is None and not work.diary_path("lu", "S01").exists()
    archived = sorted(p.read_text(encoding="utf-8").strip() for p in (work.stage / "void" / "lu").glob("S01-*.md"))
    assert archived == ["lu 的 S01 日记", "lu 的第二次日记"]  # 第一版在重演时归档
    assert work.diary_path("lu", "S01.offstage").read_bytes() == offstage


def test_gate_r3_invalidate_repeated_archive_collisions_finish(tmp_path, fake, monkeypatch):
    import datetime
    import multiprocessing
    import types

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 16, 2, 30, 0)

    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    monkeypatch.setattr(stage, "_dt", types.SimpleNamespace(datetime=Frozen))
    for take in ("二", "三"):
        fake.say("lu", f"lu 的第{take}版日记")
        fake.say("wen", f"wen 的第{take}版日记")

    def three_invalidations():
        stage.cmd_invalidate(work, "S01", "第一次")
        stage.cmd_rediary(work, "S01", None)
        stage.cmd_invalidate(work, "S01", "第二次")
        stage.cmd_rediary(work, "S01", None)
        stage.cmd_invalidate(work, "S01", "第三次")

    # 归档命名出错会让第三次作废停不下来：放进 fork 出的子进程（沿用已载入的 stage 与时钟），有界等待
    child = multiprocessing.get_context("fork").Process(target=three_invalidations)
    child.start()
    child.join(timeout=10)
    if child.is_alive():
        child.kill()
        child.join()
        pytest.fail("同一秒内第三次作废没有结束")
    assert child.exitcode == 0
    for slug in ("lu", "wen"):
        archived = list((work.stage / "void" / slug).glob("S01-20261016-023000*.md"))
        assert sorted(p.read_text(encoding="utf-8").strip() for p in archived) == sorted(
            [f"{slug} 的 S01 日记", f"{slug} 的第二版日记", f"{slug} 的第三版日记"])
        assert not work.diary_path(slug, "S01").exists()
        member = roster(work)["characters"][slug]
        assert member["entries"] == [{"id": "S01", "void": True}] and member["session"] is None
    assert stage.scene_state(work, "S01") == "void"


def test_gate_r3_invalidate_registered_diary_missing_file_still_voids(tmp_path, fake):
    work = make_work(tmp_path)
    _perform(work, fake, "S01", [("lu", "【说】一"), ("wen", "【说】二")])
    _perform(work, fake, "S02", [("lu", "【说】三"), ("wen", "【说】四")])
    lu_sid = roster(work)["characters"]["lu"]["session"]["id"]
    work.diary_path("lu", "S01").unlink()
    out = stage.cmd_invalidate(work, "S01", "改一处")
    assert sorted(out["voided_diaries"]) == ["lu", "wen"] and out["pending_review"] == ["S02"]
    assert {"actor": "lu", "session": lu_sid} in out["invalidated_sessions"]
    lu = roster(work)["characters"]["lu"]
    assert lu["entries"][0] == {"id": "S01", "void": True} and lu["session"] is None
    assert not (work.stage / "void" / "lu").exists()
    archived = list((work.stage / "void" / "wen").glob("S01-*.md"))
    assert [p.read_text(encoding="utf-8").strip() for p in archived] == ["wen 的 S01 日记"]
