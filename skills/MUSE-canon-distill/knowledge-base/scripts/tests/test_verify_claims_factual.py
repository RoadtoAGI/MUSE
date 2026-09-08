"""使用临时源文验证 claims 的真实定位、状态与旧 URL 格式；不联网。"""
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verify_claims_factual import build_pending_batch, check_claims_writeback, main


def fixture(tmp_path, **changes):
    role = tmp_path / "characters" / "a"
    role.mkdir(parents=True)
    (tmp_path / "full_text.md").write_text("第一行\n甲是乙之子。\n第三行\n")
    claim = {
        "id": "C1", "text": "甲是乙之子", "type": "lineage",
        "source_locators": ["full_text.md:L2-L2"],
        "verification_required": True, "verification_status": "verified",
        "verification_sources": [{"source_locator": "full_text.md:L2-L2", "quote": "甲是乙之子。"}],
    }
    claim.update(changes)
    (role / "claims.yaml").write_text(yaml.safe_dump({"claims": [claim]}, allow_unicode=True))
    return role


def test_local_source_checks_real_window(tmp_path):
    role = fixture(tmp_path)
    assert check_claims_writeback(role) == []
    (tmp_path / "full_text.md").write_text("第一行\n甲是丙之子。\n第三行\n")
    assert any("quote" in issue for issue in check_claims_writeback(role))


@pytest.mark.parametrize("locator,quote", [
    ("full_text.md:L8-L9", "甲是乙之子。"),
    ("missing.md:L1-L1", "甲是乙之子。"),
    ("../outside.md:L1-L1", "外部"),
    ("full_text.md:L1-L1", "甲是乙之子。"),
])
def test_false_or_outside_local_locator_rejected(tmp_path, locator, quote):
    (tmp_path.parent / "outside.md").write_text("外部")
    role = fixture(tmp_path, source_locators=[locator], verification_sources=[{"source_locator": locator, "quote": quote}])
    assert check_claims_writeback(role)


def test_local_locator_must_belong_to_claim(tmp_path):
    role = fixture(tmp_path, source_locators=["full_text.md:L1-L1"])
    assert any("source_locators" in issue for issue in check_claims_writeback(role))


@pytest.mark.parametrize("sources", [
    [{"url": "https://example.org/source", "quote": "目标版本中的实际摘录"}],
    [{"url": "https://example.org/a", "quote": "版本甲摘录"}, {"url": "https://example.org/b", "quote": "版本乙摘录"}],
])
def test_external_sources_have_no_domain_quota(tmp_path, sources):
    assert check_claims_writeback(fixture(tmp_path, verification_sources=sources)) == []


@pytest.mark.parametrize("source", [
    {"url": "https://example.org"},
    {"url": "invalid", "quote": "实际摘录"},
    {"source_locator": "full_text.md:L2-L2", "quote": ""},
])
def test_source_identity_and_quote_required(tmp_path, source):
    assert check_claims_writeback(fixture(tmp_path, verification_sources=[source]))


def test_unresolved_keeps_pending_and_fails_completion(tmp_path):
    role = fixture(tmp_path, verification_status="unresolved")
    assert build_pending_batch(role)[0]["id"] == "C1"
    assert any("unresolved" in issue for issue in check_claims_writeback(role))
    assert "甲是乙之子" in (role / "claims.yaml").read_text()


def test_disputed_needs_explanation(tmp_path):
    role = fixture(tmp_path, verification_status="disputed")
    assert any("resolution_note" in issue for issue in check_claims_writeback(role))
    data = yaml.safe_load((role / "claims.yaml").read_text())
    data["claims"][0]["resolution_note"] = "外部改编不同，本版本原文如引文。"
    (role / "claims.yaml").write_text(yaml.safe_dump(data, allow_unicode=True))
    assert check_claims_writeback(role) == []


def test_unconfigured_and_empty_claims_are_valid_but_malformed_are_not(tmp_path):
    assert check_claims_writeback(tmp_path) == []
    (tmp_path / "claims.yaml").write_text("claims: []\n")
    assert check_claims_writeback(tmp_path) == []
    (tmp_path / "claims.yaml").write_text("claims: [broken\n")
    assert check_claims_writeback(tmp_path)


def test_emit_clears_previous_pending_result(tmp_path):
    role = fixture(tmp_path)
    (role / "pending_verification.json").write_text('[{"id":"old"}]')
    with pytest.raises(SystemExit) as result:
        main(["--role-dir", str(role), "--emit-batch"])
    assert result.value.code == 0
    assert json.loads((role / "pending_verification.json").read_text()) == []


def test_explicit_source_root(tmp_path):
    role = fixture(tmp_path)
    relocated = tmp_path / "elsewhere" / "a"
    relocated.parent.mkdir()
    role.rename(relocated)
    assert check_claims_writeback(relocated, source_root=tmp_path) == []
