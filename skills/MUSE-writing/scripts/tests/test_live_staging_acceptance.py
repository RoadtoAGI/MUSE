"""Independent acceptance for persistent characters, design r7 §§3–9, 12.3.

Scenarios are derived from the design and runtime contracts before reading the
implementation. Run the actual stage CLI; replace only external host processes.

Given/When/Then requirements:
* Public, whispered, invisible and private thoughts reach only their observers.
* Aliases hide unknown identities; a late entrant never receives earlier events.
* Scheduling honors explicit choice, addressee, initiative and observer backlog.
* WAIT, LEAVE, budget, invalid output and host failures pause with durable state.
* Closing twice preserves diaries; interrupted closing can resume without replay.
* File memories govern sessions, flashbacks, persona changes and offstage notes.
* Invalidation/correction regenerates memories without leaking private changes.
* A requested line reconstructs its time and preserves the formal role session.
* Tryouts/interviews use forks and never change formal memories or roster.
* Both host adapters apply isolation at spawn, resume, fork and one-shot calls.
* One work admits one state writer, including overlapping processes.

Model prose quality and resistance to a real host's tools remain MANUAL.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import fcntl

import pytest
import yaml
import stage

STAGE = Path(__file__).resolve().parents[1] / "stage.py"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))


def load(path):
    return yaml.safe_load(path.read_text())


def file_snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


class Host:
    """Only the external CLI boundary is replaced; stage state/IO remain real."""

    def __init__(self):
        self.calls = []
        self.replies = {}
        self.fail = set()

    def __call__(self, cmd, **kwargs):
        assert cmd[0] in {"claude", "codex"}, cmd
        slug = Path(kwargs["cwd"]).name
        message = kwargs["input"]
        sid = f"session-{len(self.calls)}"
        self.calls.append({"slug": slug, "cmd": cmd, "message": message,
                           "env": kwargs.get("env", os.environ).copy(), "sid": sid})
        if slug in self.fail:
            return subprocess.CompletedProcess(cmd, 1, json.dumps({
                "is_error": True, "result": "authentication failed"}), "authentication failed")
        bookkeeping = any(s in message for s in (
            "这一场结束了", "在接下来的这一场之前", "这一刻先停住", "演出暂停",
            "The scene is over", "Before the next scene", "Hold this moment"))
        if bookkeeping:
            answer = f"memory-{slug}-{len(self.calls)}"
        else:
            queue = self.replies.setdefault(slug, [])
            answer = queue.pop(0) if queue else "【说】我在这里。"
        if cmd[0] == "claude":
            payload = json.dumps({"result": answer, "session_id": sid, "usage": {
                "input_tokens": 100, "output_tokens": 10}, "total_cost_usd": 0})
        else:
            payload = "\n".join(json.dumps(e) for e in [
                {"type": "thread.started", "thread_id": sid},
                {"type": "item.completed", "item": {"type": "agent_message", "text": answer}},
                {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}])
        return subprocess.CompletedProcess(cmd, 0, payload, "")


class Play:
    def __init__(self, root, capsys, host):
        self.root, self.capsys, self.host = root, capsys, host
        self.stage = root / "pipeline/stage"
        self.roles = root / "pipeline/story-character-skills/.claude/skills"
        for slug, name in (("a", "甲"), ("b", "乙"), ("c", "丙"), ("d", "丁")):
            room = self.roles / slug
            room.mkdir(parents=True)
            (room / "SKILL.md").write_text(f"---\nname: {slug}\nversion: 1\n---\n你是{name}。")
            (room / "state.md").write_text(f"{name}刚到岸边。")
            dump(room / "build-meta.yaml", {"character_display_name": name, "slug": slug})
        dump(root / "pipeline/run_state.yaml", {"language": "zh"})

    def setup(self, scene="S01", *, tryout=False, **overrides):
        value = {"scene_id": scene, "present": ["a", "b", "c"], "pov": "a",
                 "initiative": "a", "pause_every": 1, "max_turns": 8, **overrides}
        space = self.stage / (f"tryout/{scene}" if tryout else f"scene_{scene}")
        dump(space / "setup.yaml", value)
        for slug in [*value["present"], *value.get("late", [])]:
            dump(self.root / f"pipeline/scene_{scene}/role_views/{slug}.yaml", {
                "observable_stimuli": "岸边的一张木桌", "known_now": "", "constraints_now": "左手受伤"})
        return space

    def cli(self, verb, *args, scene="S01", tryout=False, code=0):
        selector = ["--tryout" if tryout else "--scene-id", scene]
        rc = stage.main([verb, "--work-dir", str(self.root), *selector, *args])
        captured = self.capsys.readouterr()
        assert rc == code, captured.out + captured.err
        return json.loads(captured.out or captured.err)

    def transcript(self, scene="S01"):
        return load(self.stage / f"scene_{scene}/transcript.yaml")["turns"]

    def diary(self, slug, scene="S01"):
        return self.roles / slug / f"diary/{scene}.md"


@pytest.fixture
def play(tmp_path, monkeypatch, capsys):
    host = Host()
    monkeypatch.setattr(subprocess, "run", host)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MUSE_CODEX_ROLE_HOME", str(tmp_path / "codex-role"))
    main_home = tmp_path / "main-codex"
    main_home.mkdir()
    (main_home / "auth.json").write_text("{}")
    (main_home / "config.toml").write_text('model = "test-model"\n')
    monkeypatch.setenv("CODEX_HOME", str(main_home))
    return Play(tmp_path / "work", capsys, host)


def test_private_layers_and_pov_are_routed_independently(play):
    """Given 私语和 POV 内心，When 旁观者行动，Then 只收到可见层。"""
    play.setup()
    play.host.replies["a"] = ["【做】把钥匙藏进袖口。\n【说】暗号是雨。\n【对】乙\n【闻】乙\n【见】丙\n【想】我不信乙。"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("run", "--next", "c")
    observed = play.host.calls[-1]["message"]
    assert "把钥匙藏进袖口" in observed
    assert "听不清" in observed
    assert "暗号是雨" not in observed
    assert "我不信乙" not in observed
    play.cli("run", "--next", "b")
    heard = play.host.calls[-1]["message"]
    assert "暗号是雨" in heard
    assert "把钥匙藏进袖口" not in heard
    assert "我不信乙" not in heard
    assert play.transcript()[0]["inner"] == "我不信乙。"


def test_aliases_and_late_entry_hide_identity_and_history(play):
    """Given 丙不知道甲的身份且丁迟到，When 两人行动，Then 不泄露姓名或此前回合。"""
    play.setup(late=["d"], known_as={"c": {"a": "灰衣人"}})
    play.host.replies["a"] = ["【说】你来晚前的秘密。"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("run", "--next", "c")
    assert "灰衣人" in play.host.calls[-1]["message"]
    assert "甲" not in play.host.calls[-1]["message"]
    play.cli("enter", "--slug", "d", "--view", "桌上只有半杯茶。")
    play.cli("run", "--next", "d")
    assert "桌上只有半杯茶" in play.host.calls[-1]["message"]
    assert "你来晚前的秘密" not in play.host.calls[-1]["message"]


def test_scheduling_explicit_then_addressed_and_accumulated_events(play):
    """Given 首发甲问乙，When 主控先指定丙再继续，Then 指定优先且积累事件只送一次。"""
    play.setup()
    play.host.replies["a"] = ["【说】你带钥匙了吗？\n【对】乙"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    assert play.transcript()[-1]["actor"] == "a"
    play.cli("run", "--next", "c")
    assert play.transcript()[-1]["actor"] == "c"
    play.cli("run")
    assert play.transcript()[-1]["actor"] == "b"
    assert "你带钥匙了吗" in play.host.calls[-1]["message"]
    play.cli("run", "--next", "b")
    assert "你带钥匙了吗" not in play.host.calls[-1]["message"]


@pytest.mark.parametrize("answers,expected,budget", [
    (["【静】", "【静】", "【静】"], "all_silent", 8),
    (["【离】"], "left", 8),
    (["【说】再说一句。"], "max_turns", 1),
])
def test_pause_states_preserve_record(play, answers, expected, budget):
    """Given 合法静/离或用尽预算，When run，Then 相应暂停且已演回合可回读。"""
    play.setup(pause_every=10, max_turns=budget)
    for slug, answer in zip(["a", "b", "c"], answers):
        play.host.replies[slug] = [answer]
    play.cli("open", "--host", "claude")
    result = play.cli("run")
    assert result["reason"] == expected
    assert len(play.transcript()) == len(answers)


def test_invalid_turn_repair_then_session_rebuild(play):
    """Given 连续两次无法解析，When 再继续，Then 暂停未记错话且会话从记录重建。"""
    play.setup()
    play.host.replies["a"] = ["格式错误一", "格式错误二", "【说】这次记下。"]
    play.cli("open", "--host", "claude")
    result = play.cli("run")
    assert result["reason"] == "invalid_turn"
    assert play.transcript() == []
    play.cli("run")
    call = play.host.calls[-1]
    assert "--resume" not in call["cmd"]
    assert "格式错误" not in call["message"]
    assert play.transcript()[0]["says"] == "这次记下。"


def test_unknown_addressee_is_repaired_instead_of_archived(play):
    """Given 对象无法对应在场人物，When 演出，Then 要求更正而不把错误回合归档。"""
    play.setup()
    play.host.replies["a"] = ["【说】钥匙呢？\n【对】根本不存在的人", "【说】钥匙呢？\n【对】乙"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    assert play.transcript()[0].get("to") == "b"
    assert "记不下来" in play.host.calls[-1]["message"]


def test_host_failure_has_nonzero_exit(play):
    """Given 乙宿主失败，When run，Then 命令返回宿主错误退出码。"""
    play.setup(pause_every=5)
    play.host.replies["a"] = ["【说】先记这一句。\n【对】乙"]
    play.host.fail.add("b")
    play.cli("open", "--host", "claude")
    play.cli("run", code=2)


def test_host_failure_keeps_completed_turn_and_is_resumable(play):
    """Given 乙宿主失败，When 失败解除继续，Then 保留甲回合且不重复执行。"""
    play.setup(pause_every=5)
    play.host.replies["a"] = ["【说】先记这一句。\n【对】乙"]
    play.host.fail.add("b")
    play.cli("open", "--host", "claude")
    stage.main(["run", "--work-dir", str(play.root), "--scene-id", "S01"])
    result = json.loads(play.capsys.readouterr().out)
    assert result["reason"] == "host_error"
    assert [e["actor"] for e in play.transcript()] == ["a"]
    play.host.fail.clear()
    play.host.replies["b"] = ["【离】"]
    play.cli("run")
    assert [e["actor"] for e in play.transcript()] == ["a", "b"]


def test_offstage_host_failure_has_nonzero_exit(play):
    """Given 场外补记发送的宿主失败，When open，Then 以宿主错误退出。"""
    play.setup()
    note = play.root / "pipeline/scene_S01/offstage/a.md"
    note.parent.mkdir(parents=True)
    note.write_text("昨夜亲眼看见桥已断。")
    play.host.fail.add("a")
    play.cli("open", "--host", "claude", code=2)


def test_close_host_failure_has_nonzero_exit(play):
    """Given 乙收日记失败，When close，Then 命令以宿主错误退出。"""
    play.setup()
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.host.fail.add("b")
    play.cli("close", code=2)


def test_partial_close_keeps_completed_diaries_when_retried(play):
    """Given 部分日记已经写入而命令报告错误，When 重试，Then 不覆盖已完成日记。"""
    play.setup()
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.host.fail.add("b")
    # Inspect the recovery independently of exit-code conformance.
    stage.main(["close", "--work-dir", str(play.root), "--scene-id", "S01"])
    play.capsys.readouterr()
    diary_before = play.diary("a").read_bytes()
    play.host.fail.clear()
    play.cli("close")
    assert play.diary("a").read_bytes() == diary_before
    roster = load(play.stage / "roster.yaml")
    assert roster["characters"]["a"]["session"]["memory"].count("S01") == 1


def test_offstage_failure_blocks_dependent_performance(play):
    """Given 必需场外记忆没送达，When 直接 run，Then 不让人物带着缺失经历演出。"""
    play.setup()
    note = play.root / "pipeline/scene_S01/offstage/a.md"
    note.parent.mkdir(parents=True)
    note.write_text("昨夜亲眼看见桥已断。")
    play.host.fail.add("a")
    stage.main(["open", "--host", "claude", "--work-dir", str(play.root), "--scene-id", "S01"])
    play.capsys.readouterr()
    play.host.fail.clear()
    play.cli("run", code=1)
    assert play.transcript() == []


def test_flashback_excludes_future_and_persona_update_rebuilds(play):
    """Given S01 已收场，When 回到此前或更新人格，Then 新建会话且不带未来日记。"""
    play.setup()
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("close")
    future = play.diary("a").read_text().strip()
    play.setup("S00", story_after=[])
    play.cli("open", "--host", "claude", scene="S00")
    play.cli("run", scene="S00")
    assert "--resume" not in play.host.calls[-1]["cmd"]
    assert future not in play.host.calls[-1]["message"]
    persona = play.roles / "a/SKILL.md"
    persona.write_text(persona.read_text().replace("version: 1", "version: 2") + "新的人格文本。")
    play.cli("run", "--next", "a", scene="S00")
    assert "--resume" not in play.host.calls[-1]["cmd"]
    assert "新的人格文本" in " ".join(play.host.calls[-1]["cmd"])


def test_invalidate_amend_rediary_filters_private_change_notes(play):
    """Given 两场连续演出，When 更正首场私语，Then 作废旧记忆、标后场待核、按可见性重建。"""
    play.setup()
    play.host.replies["a"] = ["【说】旧暗号。\n【闻】乙"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("close")
    play.setup("S02")
    play.cli("open", "--host", "claude", scene="S02")
    play.cli("run", scene="S02")
    play.cli("close", scene="S02")
    result = play.cli("invalidate", "--change", "只有作者知道的更正原因。")
    assert result["pending_review"] == ["S02"]
    assert not play.diary("a").exists()
    play.cli("amend", "--n", "1", "--says", "新暗号。")
    start = len(play.host.calls)
    play.cli("rediary")
    calls = play.host.calls[start:]
    for call in calls:
        assert "只有作者知道" not in call["message"]
        assert "旧暗号" not in call["message"]
        if call["slug"] == "b":
            assert "新暗号" in call["message"]
        if call["slug"] == "c":
            assert "新暗号" not in call["message"]


@pytest.mark.parametrize("host,ephemeral", [("claude", "--no-session-persistence"), ("codex", "--ephemeral")])
def test_line_is_ephemeral_and_does_not_change_formal_memory(play, host, ephemeral):
    """Given 正式场景已结束，When 索句，Then 重建指定时点、使用一次性实例、保留正式会话。"""
    play.setup()
    play.cli("open", "--host", host)
    play.cli("run")
    play.cli("run", "--next", "b")
    play.cli("close")
    roster_before = (play.stage / "roster.yaml").read_bytes()
    play.cli("line", "--slug", "a", "--after", "1", "--cue", "雨停了，你还想说什么？")
    assert (play.stage / "roster.yaml").read_bytes() == roster_before
    added = play.transcript()[1]
    assert added["kind"] == "line" and added["after"] == 1
    assert ephemeral in play.host.calls[-1]["cmd"]


@pytest.mark.parametrize("host,ephemeral", [("claude", "--no-session-persistence"), ("codex", "--ephemeral")])
def test_line_correction_also_uses_ephemeral_instances(play, host, ephemeral):
    """Given 索句首次格式错误，When 改一次，Then 更正成功且两次都不持久化。"""
    play.setup()
    play.cli("open", "--host", host)
    play.cli("run")
    play.host.replies["a"] = ["格式不合约", "【说】更正后的索句。"]
    start = len(play.host.calls)
    play.cli("line", "--slug", "a", "--after", "1", "--cue", "你还想说什么？")
    assert play.transcript()[1]["says"] == "更正后的索句。"
    for call in play.host.calls[start:]:
        assert ephemeral in call["cmd"]
        assert not {"--resume", "resume"}.intersection(call["cmd"])


def test_tryout_and_interview_keep_formal_files_unchanged(play):
    """Given 已有正式记忆，When 试演收场并访谈，Then 使用分叉、保留正式名册与全部人物文件。"""
    play.setup()
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("close")
    roster_before = (play.stage / "roster.yaml").read_bytes()
    identities = file_snapshot(play.roles)
    space = play.setup("branch-a", tryout=True, situation="三个人在门口争钥匙。")
    play.cli("open", "--host", "claude", scene="branch-a", tryout=True)
    play.cli("run", scene="branch-a", tryout=True)
    assert "--fork-session" in play.host.calls[-1]["cmd"]
    play.cli("close", scene="branch-a", tryout=True)
    trial_roster = (space / "roster.yaml").read_bytes()
    play.cli("interview", "--slug", "a", "--question", "为何留下？", scene="branch-a", tryout=True)
    assert "--fork-session" in play.host.calls[-1]["cmd"]
    assert (space / "roster.yaml").read_bytes() == trial_roster
    assert (play.stage / "roster.yaml").read_bytes() == roster_before
    assert file_snapshot(play.roles) == identities
    assert len(list((space / "probes").glob("*.md"))) == 3


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_host_isolation_across_spawn_resume_and_fork(play, host):
    """Given 两种宿主，When 首启/恢复/分叉，Then 每次调用都携带对应隔离配置。"""
    play.setup()
    play.cli("open", "--host", host)
    play.cli("run")
    play.cli("run", "--next", "a")
    play.cli("close")
    play.setup("branch", tryout=True, situation="人在门前。")
    play.cli("open", "--host", host, scene="branch", tryout=True)
    play.cli("run", scene="branch", tryout=True)
    for call in play.host.calls:
        cmd = call["cmd"]
        if host == "claude":
            assert cmd[cmd.index("--tools") + 1] == ""
            assert "--safe-mode" in cmd and "--system-prompt" in cmd
        else:
            role_home = Path(call["env"]["CODEX_HOME"])
            assert role_home != Path(os.environ["CODEX_HOME"])
            config = (role_home / "config.toml").read_text()
            for setting in ('sandbox_mode = "read-only"', 'web_search = "disabled"',
                            'project_doc_max_bytes = 0', 'shell_tool = false',
                            'unified_exec = false', 'memories = false'):
                assert setting in config


@pytest.mark.parametrize("field,value", [("model", "different-model"), ("host", "codex")])
def test_author_host_configuration_change_rebuilds_session(play, field, value):
    """Given 作者修改名册中的模型配置，When 再唤醒，Then 按运行时契约重建。"""
    play.setup()
    play.cli("open", "--host", "claude")
    play.cli("run")
    path = play.stage / "roster.yaml"
    roster = load(path)
    roster["characters"]["a"][field] = value
    dump(path, roster)
    play.cli("run", "--next", "a")
    assert not {"--resume", "resume"}.intersection(play.host.calls[-1]["cmd"])


def test_world_event_reaches_only_named_perceiver(play):
    """Given 世界事件只被乙感知，When 乙和丙行动，Then 内容不送丙。"""
    play.setup()
    play.cli("open", "--host", "claude")
    play.cli("event", "--text", "背后有人递来密信。", "--perceived-by", "乙")
    play.cli("run", "--next", "c")
    assert "背后有人递来密信" not in play.host.calls[-1]["message"]
    play.cli("run", "--next", "b")
    assert "背后有人递来密信" in play.host.calls[-1]["message"]


def test_two_commands_cannot_write_the_same_work(play):
    """Given 另一进程持有作品锁，When open，Then 拒绝且不生成演出状态。"""
    play.setup()
    # Hold the OS lock through a separate open file description.
    lock_path = play.stage / ".lock"
    with lock_path.open("w") as locked:
        fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
        play.cli("open", "--host", "claude", code=1)
    assert not (play.stage / "roster.yaml").exists()


def test_bad_audience_correction_keeps_only_repaired_turn(play):
    """Given 闻中写了不存在的人，When 演出，Then 更正后只归档一次。"""
    play.setup()
    play.host.replies["a"] = ["【说】不能记的版本。\n【闻】不存在的人", "【说】可记的版本。\n【闻】乙"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    assert len(play.transcript()) == 1
    assert play.transcript()[0]["says"] == "可记的版本。"
    assert play.transcript()[0]["heard_by"] == ["b"]


def test_non_pov_inner_is_not_archived(play):
    """Given 非 POV 的乙写了想，When 演出，Then 内心不进记录，只留丢弃线索。"""
    play.setup(initiative="b")
    play.host.replies["b"] = ["【说】我没事。\n【想】只有我知道的恐惧。"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    assert "inner" not in play.transcript()[0]
    assert "只有我知道的恐惧" not in str(play.transcript())


def test_offstage_memory_is_written_once_and_used_before_playing(play):
    """Given 场外经历只给甲，When 开场与再次 open，Then 先记入本人日记且不重复投递。"""
    play.setup()
    note = play.root / "pipeline/scene_S01/offstage/a.md"
    note.parent.mkdir(parents=True)
    note.write_text("亲眼看到桥断了。")
    play.cli("open", "--host", "claude")
    diary = play.diary("a", "S01.offstage")
    assert diary.exists()
    before = diary.read_bytes()
    assert not play.diary("b", "S01.offstage").exists()
    play.cli("open", "--host", "claude")
    assert diary.read_bytes() == before
    play.cli("run")
    assert "--resume" in play.host.calls[-1]["cmd"]


def test_leaver_receives_no_later_world_event_in_diary(play):
    """Given 甲已离场，When 注入后续事件再收场，Then 甲的日记请求不包含离场后的事。"""
    play.setup()
    play.host.replies["a"] = ["【离】"]
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("event", "--text", "屋里的人打开了密匣。")
    start = len(play.host.calls)
    play.cli("close")
    for call in play.host.calls[start:]:
        if call["slug"] == "a":
            assert "屋里的人打开了密匣" not in call["message"]
    assert play.diary("a").exists()


def test_reperform_archives_the_record_and_rebuilds_from_prior_memory(play):
    """Given 一场已收场，When 获准重演，Then 留存旧记录而旧日记不进入重演。"""
    space = play.setup()
    play.cli("open", "--host", "claude")
    play.cli("run")
    play.cli("close")
    old_memory = play.diary("a").read_text().strip()
    original = (space / "transcript.yaml").read_bytes()
    play.cli("open", "--reperform", "--host", "claude")
    assert (space / "takes/take-1/transcript.yaml").read_bytes() == original
    assert not play.diary("a").exists()
    play.cli("run")
    assert "--resume" not in play.host.calls[-1]["cmd"]
    assert old_memory not in play.host.calls[-1]["message"]


def test_cli_process_smoke_uses_only_stub_executable(tmp_path, capsys):
    """Given PATH 只有替身宿主，When 运行独立 stage.py 进程，Then 实际解析命令并写回合。"""
    play = Play(tmp_path / "work", capsys, Host())
    play.setup()
    binary = tmp_path / "bin/claude"
    binary.parent.mkdir()
    binary.write_text(f"#!{sys.executable}\n" +
                      "import json,sys\n" +
                      "assert '--safe-mode' in sys.argv\n" +
                      "assert sys.argv[sys.argv.index('--tools')+1] == ''\n" +
                      "sys.stdin.read()\n" +
                      "print(json.dumps({'result':'【说】独立进程。','session_id':'stub-session'}))\n")
    binary.chmod(0o755)
    env = {**os.environ, "PATH": str(binary.parent)}
    for verb, extras in (("open", ["--host", "claude"]), ("run", [])):
        result = subprocess.run([sys.executable, str(STAGE), verb, "--work-dir", str(play.root),
                                 "--scene-id", "S01", *extras],
                                env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
    assert play.transcript()[0]["says"] == "独立进程。"
