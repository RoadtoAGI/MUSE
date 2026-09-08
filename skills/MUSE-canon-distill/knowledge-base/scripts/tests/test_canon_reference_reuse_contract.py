import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[5]
INSPIRATION = ROOT / "skills" / "MUSE-canon-distill" / "knowledge-base" / "inspiration"
FORBIDDEN_PHRASES = ("不要照抄", "不要照搬", "不要复制", "不要")
BAD_ACTION_CANDIDATES = {
    "把仪式写成治愈完成",
    "把镜像写成说教",
    "把一端写成纯反派",
    "在象征后补主题解释",
}
QUOTED_REFERENCE = "「不要回答」三连警告原文"


def _has_legacy_leading_prefix(item):
    normalized = item.strip()
    return any(normalized.startswith(phrase) for phrase in FORBIDDEN_PHRASES)


def _assert_candidates(payload, source):
    assert "do_not_copy" not in payload, source
    candidates = payload.get("reuse_candidates")
    assert isinstance(candidates, list) and candidates, source
    assert all(isinstance(item, str) for item in candidates), source
    assert all(item.strip() for item in candidates), source
    assert not any(_has_legacy_leading_prefix(item) for item in candidates), source


def test_public_cards_use_reuse_candidates():
    paths = sorted(INSPIRATION.glob("*.yaml"))
    assert paths
    for path in paths:
        _assert_candidates(yaml.safe_load(path.read_text(encoding="utf-8")), path)


def test_nominations_use_reuse_candidates():
    paths = sorted((INSPIRATION / "_nominations").glob("*.json"))
    assert len(paths) == 31
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for nomination in payload["nominations"]:
            _assert_candidates(nomination, path)


def test_corpus_removes_bad_actions_and_preserves_quoted_reference():
    public_candidates = []
    for path in sorted(INSPIRATION.glob("*.yaml")):
        public_candidates.extend(yaml.safe_load(path.read_text(encoding="utf-8"))["reuse_candidates"])

    nomination_candidates = []
    for path in sorted((INSPIRATION / "_nominations").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for nomination in payload["nominations"]:
            nomination_candidates.extend(nomination["reuse_candidates"])

    assert BAD_ACTION_CANDIDATES.isdisjoint(public_candidates)
    assert BAD_ACTION_CANDIDATES.isdisjoint(nomination_candidates)
    assert QUOTED_REFERENCE in public_candidates
    assert QUOTED_REFERENCE in nomination_candidates


def test_quoted_negative_phrase_is_not_a_legacy_leading_prefix():
    assert not _has_legacy_leading_prefix(QUOTED_REFERENCE)


def test_active_canon_contract_has_no_legacy_field():
    roots = [
        ROOT / "skills" / "MUSE-canon-distill" / "knowledge-base" / "scripts",
        ROOT / "skills" / "MUSE-canon-distill" / "skills",
        ROOT / "skills" / "MUSE-canon-distill" / "agents",
    ]
    violations = []
    for root in roots:
        for path in (*root.rglob("*.py"), *root.rglob("*.md")):
            if path.name == "test_canon_reference_reuse_contract.py":
                continue
            if "do_not_copy" in path.read_text(encoding="utf-8"):
                violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_santi_worldbuilding_fields_are_misuse_risks_without_value_reversal():
    expected_counts = {
        "三体Ⅰ-地球往事": 10,
        "三体Ⅱ-黑暗森林": 10,
        "三体Ⅲ-死神永生": 15,
    }
    novels = ROOT / "skills" / "MUSE-canon-distill" / "knowledge-base" / "novels"
    risk_signal = re.compile(
        r"不要|不可|不能|必须|严禁|只能|不宜|否则|缺一|若|失效|反面|先行|前提|边界|禁"
    )

    for novel, expected in expected_counts.items():
        path = novels / novel / "pipeline" / "世界观与巧思拆解.md"
        text = path.read_text(encoding="utf-8")
        values = re.findall(r"^- \*\*misuse_risks\*\*: (.+)$", text, re.MULTILINE)

        assert len(values) == expected, path
        assert "**" + "do_" + "not_copy**" not in text, path
        assert all(value.strip() and risk_signal.search(value) for value in values), path


def test_current_rag_contract_separates_compact_evidence_from_writer_reuse():
    path = ROOT / "docs" / "Level_1_foundation" / "project-research" / "RAG.md"
    text = path.read_text(encoding="utf-8")

    assert "`quote` 的紧凑展示只服务 provenance 定位" in text
    assert "不限制 writer 从末位干净范文块直接复用原句或连续段落" in text
    assert "作为 evidence，不设字符或段落长度上限" not in text
