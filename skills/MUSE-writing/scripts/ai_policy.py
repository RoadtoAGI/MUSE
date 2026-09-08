"""AI-pattern family lifecycle policy SSOT.

All runtime consumers resolve policy through :func:`effective_policy`.  The
compatibility constants at the bottom are derived views for older callers;
they do not carry independent policy.
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any


LANGUAGES = frozenset({"zh", "en"})
LIFECYCLES = frozenset({"observe", "enforced"})
BASELINE_METRICS = frozenset({"p80_all", "p90_all", "p80_positive", "p90_positive"})
CONSUMERS = [
    "lint-aggregation",
    "directive",
    "wholetext",
    "distribution",
    "scene-review",
]


def _calibration_ref(lang: str, family: str, metric: str = "p90_positive") -> str:
    return f"builtin:v1:{lang}:{family}:{metric}"


_BASELINES_ZH = {
    "abstract_phrase_debt": 0.48,
    "action_log": 0.39,
    "connector_overuse": 0.78,
    "dash_overuse": 0.26,
    "demonstrative_classifier": 6.11,
    "dummy_pronoun": 1.42,
    "figurative_debt": 0.40,
    "lexical_cliche": 3.75,
    "marker_pollution": 1.72,
    "micro_punchline_cadence": 7.05,
    "repeated_head": 0.70,
    "rhythm_fragmentation": 4.00,
    "silence_pause_cliche": 0.72,
    "social_choreography": 0.69,
    "state_persistence_template": 0.38,
}
_BASELINES_EN = {
    "dash_overuse": 0.27,
    "marker_pollution": 0.14,
    "rhythm_fragmentation": 0.82,
}

CALIBRATION_RECORDS: dict[str, dict[str, Any]] = {
    _calibration_ref(lang, family): {
        "family": family,
        "language": lang,
        "metric": "p90_positive",
        "value": value,
        "provenance": "kb-shadow-v1",
    }
    for lang, table in (("zh", _BASELINES_ZH), ("en", _BASELINES_EN))
    for family, value in table.items()
}

# New observe→enforced promotions are added here with all three evidence legs.
# The empty initial registry is intentional: current enforced policies predate
# the contract.  Their manifest entries carry ``pre_contract`` explicitly so a
# future observe policy cannot become enforced without a resolvable record.
PROMOTION_RECORDS: dict[str, dict[str, Any]] = {}


def _policy(
    lifecycle: str,
    *,
    sovereignty: str | None = None,
    baseline_policy: str | None = None,
    baseline_ref: str | None = None,
    single_hit: bool = False,
    aggregation: dict[str, float | int] | None = None,
    device_budget: dict[str, float] | None = None,
    pre_contract: bool = False,
    density_contract: bool = False,
    promoted_ref: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "lifecycle": lifecycle,
        "single_hit": single_hit,
        "aggregation": aggregation or {},
        "device_budget": device_budget or {},
        "rules": {},
    }
    if sovereignty is not None:
        result["sovereignty"] = sovereignty
    if baseline_policy is not None:
        result["baseline_policy"] = baseline_policy
    if pre_contract:
        result["pre_contract"] = True
    if promoted_ref is not None:
        result["promoted_ref"] = promoted_ref
    if density_contract:
        # 发布密度合同：最终文本 canonical count 必须 <= ceil(baseline*chars/1000)-1
        # （即密度严格 < 基线）。wholetext gate 按最终文本长度动态判，与 severity
        # 阈值解耦——high 的 count>=4 固定门槛和密度目标没有等价关系，短文本
        # 2-3 处命中即可超基线却永不 blocking（2026-07-17 用户裁决 + codex 分析）。
        result["density_contract"] = True
    if baseline_policy == "calibrated":
        result["baseline_metric"] = "p90_positive"
        result["baseline_ref"] = baseline_ref
    return result


def _family(
    group: str,
    cluster: str,
    aliases: list[str],
    repair: str,
    sovereignty: str | None,
    *,
    observe_zh: bool = False,
    observe_baseline: bool = False,
    exempt: bool = False,
    single_hit: bool = False,
    aggregation: dict[str, float | int] | None = None,
    device_budget: dict[str, float] | None = None,
    density_contract: bool = False,
    decision_ref: str | None = None,
    promoted_ref: str | None = None,
) -> dict[str, Any]:
    # en remains explicitly observe for every family until its own promotion.
    # promoted_ref 存在 = §1.3 合同晋升形态（须有 PROMOTION_RECORDS 三证据记录）；
    # 否则 enforced 只能是 pre_contract grandfather 形态。
    zh_policy = _policy(
        "observe",
        baseline_policy="calibrated" if observe_baseline else None,
        baseline_ref="__resolved_below__" if observe_baseline else None,
    ) if observe_zh else _policy(
        "enforced",
        sovereignty=sovereignty,
        baseline_policy="exempt" if exempt else "calibrated",
        baseline_ref=None if exempt else "__resolved_below__",
        single_hit=single_hit,
        aggregation=aggregation,
        device_budget=device_budget,
        pre_contract=promoted_ref is None,
        density_contract=density_contract,
        promoted_ref=promoted_ref,
    )
    return {
        "group": group,
        "cluster": cluster,
        "aliases": aliases,
        "repair": repair,
        "decision_ref": decision_ref,
        "consumers": list(CONSUMERS),
        "policy": {"zh": zh_policy, "en": _policy("observe")},
    }


FAMILY_MANIFEST: dict[str, dict[str, Any]] = {
    "marker_pollution": _family(
        "hard", "lexical_cliche", ["Markdown污染"], "删除正文中的 Markdown 结构标记", "S",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "lexical_cliche": _family(
        "hard",
        "lexical_cliche",
        ["词表面层", "硬cliche"],
        "用具体动作或物件替换套语",
        "S",
        device_budget={"storyteller_voice": 1.3},
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "fragment_settlement": _family(
        "semantic_heuristic",
        "micro_punchline_cadence",
        ["碎片结算短句"],
        "移除替读者结算情绪的碎片评注",
        None,
        observe_zh=True,
        decision_ref="CHANGELOG:2026-08-28-ban-domain-contraction",
    ),
    "micro_clause_chain": _family(
        "semantic_heuristic",
        "micro_punchline_cadence",
        ["碎切短分句链", "连续超短分句"],
        "合并无信息增量的连续短分句",
        None,
        observe_zh=True,
        decision_ref="CHANGELOG:2026-08-28-ban-domain-contraction",
    ),
    "connector_overuse": _family(
        "hard", "connector_overuse", ["段首然后", "连接词过用"], "删去流水连接词并恢复事件因果", "S",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "rhythm_fragmentation": _family(
        "syntax_heuristic",
        "rhythm_fragmentation",
        ["节奏碎片化", "短段刷屏"],
        "按动作与感知关系重组句段节奏",
        "S",
        device_budget={"staccato_action": 1.6, "archive_cold": 1.6},
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "repeated_head": _family(
        "syntax_heuristic", "rhythm_fragmentation", ["同字起手", "排比"], "打散机械重复的句首结构", "S",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "action_log": _family(
        "syntax_heuristic", "action_log", ["动作清单化", "流水账"], "保留有因果或选择后果的动作", "M",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "dash_overuse": _family(
        "syntax_heuristic", "rhythm_fragmentation", ["破折号过密"], "将解释性破折号改写为完整关系", "S",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "figurative_debt": _family(
        "semantic_heuristic", "figurative_debt", ["短比喻债务", "像某种X"], "删除借比喻代替观察的空泛句", "M",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "abstract_phrase_debt": _family(
        "semantic_heuristic", "abstract_explanation", ["抽象短语债务", "某种重量"], "把抽象判断还原成可见载体", "M",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "silence_pause_cliche": _family(
        "semantic_heuristic",
        "silence_pause_cliche",
        ["沉默停顿廉价化"],
        "让沉默承担可见的选择或压力",
        "M",
        device_budget={"naked_line": 1.3},
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "social_choreography": _family(
        "semantic_heuristic", "social_choreography", ["社交调度流水", "接电话去了"], "删除无后果的社交调度说明", "M",
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "contrastive_negation_assertion": _family(
        "semantic_heuristic",
        "explanatory_detour",
        ["不是A是B", "不是A而是B"],
        "直接陈述后项或让前项误判先在情节中成立",
        None,
        observe_zh=True,
        decision_ref="CHANGELOG:2026-08-28-ban-domain-contraction",
    ),
    "micro_punchline_cadence": _family(
        "semantic_heuristic",
        "micro_punchline_cadence",
        ["短句承重", "计数字台词", "首次末次标记"],
        "让重要性由事件后果承担",
        "S",
        aggregation={"same_paragraph_count_gte": 2, "same_rule_scene_count_gte": 3},
        device_budget={"naked_line": 1.6, "staccato_action": 1.6},
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "state_persistence_template": _family(
        "semantic_heuristic",
        "silence_pause_cliche",
        ["状态持续模板", "还在那里"],
        "用状态变化或具体感知替代标签",
        "M",
        aggregation={"same_rule_scene_count_gte": 2, "same_anchor_repeated_count_gte": 2},
        observe_zh=True, observe_baseline=True,
        decision_ref="skill-upgrade-2026-09-07-semantic-review",
    ),
    "meta_language_leak": _family(
        "hard", "meta_language_leak", ["元语言泄漏"], "移除写作过程或总结式元话语", None, observe_zh=True
    ),
    # 2026-07-17 晋升（observe → enforced aggregate S + 密度合同）：用户裁决
    # "修订后密度 < 名著基线"为不可豁免发布目标——S 而非 M，防 objection 窄门
    # 绕过 aggregate 目标。三证据 promotion record 见 PROMOTION_RECORDS。
    "dummy_pronoun": _family(
        "semantic_heuristic", "referential_vagueness", ["形式主宾语", "它这东西那东西"],
        "按序收敛：承前省略 > 实词复现 > 局部重构（不得以指示词+名词兜底）", "S",
        density_contract=True,
        decision_ref="pronoun-density-2026-07-17",
        promoted_ref="dummy_pronoun:zh:2026-07-17",
    ),
    "demonstrative_classifier": _family(
        "semantic_heuristic", "referential_vagueness", ["指示限定词", "这那加量词"],
        "按序收敛：删可选指示成分 > 普通定指 > 直写具体对象 > 局部改句", "S",
        density_contract=True,
        decision_ref="pronoun-density-2026-07-17",
        promoted_ref="demonstrative_classifier:zh:2026-07-17",
    ),
}

# ``parallel_negation`` 与 contrastive_negation_assertion 在多种句式上命中同一
# span。族级 lexical_cliche 仍保持 enforced；该重叠 rule 单独进入 observe，
# 防止候选族经旧词法路径重新获得阻断权。
FAMILY_MANIFEST["lexical_cliche"]["policy"]["zh"]["rules"]["parallel_negation"] = _policy(
    "observe"
)

# Resolve calibrated references after all family ids are known.
for _family_id, _record in FAMILY_MANIFEST.items():
    _zh = _record["policy"]["zh"]
    if _zh.get("baseline_policy") == "calibrated":
        _zh["baseline_ref"] = _calibration_ref("zh", _family_id)

# §1.3 晋升合同记录（observe → enforced:S + 密度合同，2026-07-17）：
# 三证据腿 prevalence_ref / hard_negative_ref / fixture_refs + 用户裁决 decision_ref
# （"修订后密度严格 < 名著基线"为不可豁免发布目标）。held-out 独立性已知折扣：
# 本批以源作高密段落 stress fixture + 名著普查为最小合同证据，作品级
# train/held-out 拆分归校准 provenance 另案。
PROMOTION_RECORDS.update({
    "dummy_pronoun:zh:2026-07-17": {
        "family": "dummy_pronoun",
        "language": "zh",
        "rule": None,
        "prevalence_ref": "183 系 AI 产物 4.06–4.34/k vs 同语域源作≈0（实词复现替代）；"
                          "普查档案见 pipeline CHANGELOG 2026-07-12 块",
        "hard_negative_ref": "9 部名著校准 P90(positive)=1.42/k；"
                             "should-not-fix 负例夹具与源作段落 stress fixture 入测试树",
        "decision_ref": "pronoun-density-2026-07-17",
        "fixture_refs": [
            "scripts/tests/test_referential_vagueness.py::test_it_subject_and_object_anchored",
            "scripts/tests/test_referential_vagueness.py::test_dummy_pronoun_dialogue_exempt",
        ],
    },
    "demonstrative_classifier:zh:2026-07-17": {
        "family": "demonstrative_classifier",
        "language": "zh",
        "rule": None,
        "prevalence_ref": "183 系历史三版 10.9–11.6/k 全超名著最大值 8.2，修订后仍 8.79；"
                          "普查档案见 pipeline CHANGELOG 2026-07-12 块",
        "hard_negative_ref": "名著带宽 1.3–8.2/k、P90(positive)=6.11/k（不加 register multiplier）；"
                             "8.2 源作段落 stress fixture 验证按序保留 protected 不逐处清空",
        "decision_ref": "pronoun-density-2026-07-17",
        "fixture_refs": [
            "scripts/tests/test_referential_vagueness.py::test_classifier_hit",
            "scripts/tests/test_referential_vagueness.py::test_classifier_dialogue_exempt",
        ],
    },
})


_PRE_CONTRACT_POLICY_FIELDS = (
    "lifecycle",
    "sovereignty",
    "baseline_policy",
    "baseline_metric",
    "baseline_ref",
    "single_hit",
    "aggregation",
    "device_budget",
)
# Independent migration oracle.  Keep this literal separate from
# ``FAMILY_MANIFEST`` so editing a live policy cannot silently rewrite its own
# grandfather record during import.
PRE_CONTRACT_POLICY_BASELINE: dict[tuple[str, str], dict[str, Any]] = {
    ("marker_pollution", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:marker_pollution:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("lexical_cliche", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:lexical_cliche:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {"storyteller_voice": 1.3},
    },
    ("fragment_settlement", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "exempt",
        "baseline_metric": None, "baseline_ref": None, "single_hit": True,
        "aggregation": {"same_family_scene_count_gte": 1}, "device_budget": {},
    },
    ("micro_clause_chain", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "exempt",
        "baseline_metric": None, "baseline_ref": None, "single_hit": True,
        "aggregation": {"same_family_scene_count_gte": 1}, "device_budget": {},
    },
    ("connector_overuse", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:connector_overuse:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("rhythm_fragmentation", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:rhythm_fragmentation:p90_positive",
        "single_hit": False, "aggregation": {},
        "device_budget": {"staccato_action": 1.6, "archive_cold": 1.6},
    },
    ("repeated_head", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:repeated_head:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("action_log", "zh"): {
        "lifecycle": "enforced", "sovereignty": "M", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:action_log:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("dash_overuse", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:dash_overuse:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("figurative_debt", "zh"): {
        "lifecycle": "enforced", "sovereignty": "M", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:figurative_debt:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("abstract_phrase_debt", "zh"): {
        "lifecycle": "enforced", "sovereignty": "M", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:abstract_phrase_debt:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("silence_pause_cliche", "zh"): {
        "lifecycle": "enforced", "sovereignty": "M", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:silence_pause_cliche:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {"naked_line": 1.3},
    },
    ("social_choreography", "zh"): {
        "lifecycle": "enforced", "sovereignty": "M", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:social_choreography:p90_positive",
        "single_hit": False, "aggregation": {}, "device_budget": {},
    },
    ("contrastive_negation_assertion", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "exempt",
        "baseline_metric": None, "baseline_ref": None, "single_hit": True,
        "aggregation": {"same_family_scene_count_gte": 1}, "device_budget": {},
    },
    ("micro_punchline_cadence", "zh"): {
        "lifecycle": "enforced", "sovereignty": "S", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:micro_punchline_cadence:p90_positive",
        "single_hit": False,
        "aggregation": {"same_paragraph_count_gte": 2, "same_rule_scene_count_gte": 3},
        "device_budget": {"naked_line": 1.6, "staccato_action": 1.6},
    },
    ("state_persistence_template", "zh"): {
        "lifecycle": "enforced", "sovereignty": "M", "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive", "baseline_ref": "builtin:v1:zh:state_persistence_template:p90_positive",
        "single_hit": False,
        "aggregation": {"same_rule_scene_count_gte": 2, "same_anchor_repeated_count_gte": 2},
        "device_budget": {},
    },
}


# Existing rule identities that inherited an enforced family policy before the
# promotion contract.  Any newly registered subtype must carry an explicit
# observe override first; it cannot inherit enforcement merely by appearing in
# RULE_REGISTRY.
PRE_CONTRACT_INHERITED_RULES = frozenset({
    ("banned_markdown", "zh", "marker_pollution"),
    ("keyword_ai_cliche", "zh", "lexical_cliche"),
    ("parallel_negation", "zh", "lexical_cliche"),
    ("conjunction_overuse", "zh", "connector_overuse"),
    ("short_paragraph_run", "zh", "rhythm_fragmentation"),
    ("clause_fragment_density", "zh", "rhythm_fragmentation"),
    ("comma_short_interval", "zh", "rhythm_fragmentation"),
    ("repeated_clause_head", "zh", "repeated_head"),
    ("micro_action_density", "zh", "action_log"),
    ("consecutive_action_phrase", "zh", "action_log"),
    ("dash_density", "zh", "dash_overuse"),
    ("short_simile_debt", "zh", "figurative_debt"),
    ("abstract_phrase_debt", "zh", "abstract_phrase_debt"),
    ("stock_silence_pause_phrase", "zh", "silence_pause_cliche"),
    ("social_choreography_log", "zh", "social_choreography"),
    ("contrastive_negation_assertion", "zh", "contrastive_negation_assertion"),
    ("narrative_micro_label", "zh", "micro_punchline_cadence"),
    ("counted_speech_weight", "zh", "micro_punchline_cadence"),
    ("ordinal_gravity_marker", "zh", "micro_punchline_cadence"),
    ("zero_yield_micro_clause_candidate", "zh", "micro_punchline_cadence"),
    ("state_persistence_tag", "zh", "state_persistence_template"),
    ("fragment_settlement", "zh", "fragment_settlement"),
    ("micro_clause_chain", "zh", "micro_clause_chain"),
})

PRE_CONTRACT_RULE_IDENTITIES = PRE_CONTRACT_INHERITED_RULES | frozenset({
    ("banned_markdown", "en", "marker_pollution"),
    ("em_dash_density", "en", "dash_overuse"),
    ("negation_pivot_en", "en", "contrastive_negation_assertion"),
    ("slop_phrase_en", "en", "lexical_cliche"),
    ("staccato_run", "en", "rhythm_fragmentation"),
    ("simile_density_en", "en", "figurative_debt"),
    ("meta_language_leak_zh", "zh", "meta_language_leak"),
    ("meta_language_leak_en", "en", "meta_language_leak"),
    ("dummy_pronoun", "zh", "dummy_pronoun"),
    ("demonstrative_classifier", "zh", "demonstrative_classifier"),
})


RULE_REGISTRY: dict[str, dict[str, Any]] = {
    "banned_markdown": {"family": "marker_pollution", "languages": ["zh", "en"]},
    "keyword_ai_cliche": {"family": "lexical_cliche", "languages": ["zh"]},
    "parallel_negation": {"family": "lexical_cliche", "languages": ["zh"]},
    "conjunction_overuse": {"family": "connector_overuse", "languages": ["zh"]},
    "short_paragraph_run": {"family": "rhythm_fragmentation", "languages": ["zh"], "aggregation_only": True},
    "clause_fragment_density": {"family": "rhythm_fragmentation", "languages": ["zh"]},
    "comma_short_interval": {"family": "rhythm_fragmentation", "languages": ["zh"]},
    "repeated_clause_head": {"family": "repeated_head", "languages": ["zh"]},
    "micro_action_density": {"family": "action_log", "languages": ["zh"]},
    "consecutive_action_phrase": {"family": "action_log", "languages": ["zh"]},
    "dash_density": {"family": "dash_overuse", "languages": ["zh"]},
    "short_simile_debt": {"family": "figurative_debt", "languages": ["zh"]},
    "abstract_phrase_debt": {"family": "abstract_phrase_debt", "languages": ["zh"]},
    "stock_silence_pause_phrase": {"family": "silence_pause_cliche", "languages": ["zh"]},
    "social_choreography_log": {"family": "social_choreography", "languages": ["zh"]},
    "contrastive_negation_assertion": {"family": "contrastive_negation_assertion", "languages": ["zh"]},
    "narrative_micro_label": {"family": "micro_punchline_cadence", "languages": ["zh"], "aggregation_only": True},
    "counted_speech_weight": {"family": "micro_punchline_cadence", "languages": ["zh"]},
    "ordinal_gravity_marker": {"family": "micro_punchline_cadence", "languages": ["zh"]},
    "state_persistence_tag": {"family": "state_persistence_template", "languages": ["zh"]},
    "em_dash_density": {"family": "dash_overuse", "languages": ["en"]},
    "negation_pivot_en": {"family": "contrastive_negation_assertion", "languages": ["en"]},
    "slop_phrase_en": {"family": "lexical_cliche", "languages": ["en"]},
    "fragment_settlement": {"family": "fragment_settlement", "languages": ["zh"]},
    "micro_clause_chain": {"family": "micro_clause_chain", "languages": ["zh"]},
    "staccato_run": {"family": "rhythm_fragmentation", "languages": ["en"]},
    "simile_density_en": {"family": "figurative_debt", "languages": ["en"]},
    "meta_language_leak_zh": {"family": "meta_language_leak", "languages": ["zh"]},
    "meta_language_leak_en": {"family": "meta_language_leak", "languages": ["en"]},
    "dummy_pronoun": {"family": "dummy_pronoun", "languages": ["zh"]},
    "demonstrative_classifier": {"family": "demonstrative_classifier", "languages": ["zh"]},
}


def effective_policy(
    family: str,
    lang: str,
    rule: str | None = None,
    *,
    manifest: dict[str, dict[str, Any]] | None = None,
    rule_registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve family×language policy, then apply a same-language rule override."""
    manifest = FAMILY_MANIFEST if manifest is None else manifest
    rule_registry = RULE_REGISTRY if rule_registry is None else rule_registry
    record = manifest.get(family)
    if not record or lang not in LANGUAGES or lang not in record.get("policy", {}):
        return {"registered": False, "lifecycle": "not_registered"}
    if rule is not None:
        registration = rule_registry.get(rule)
        if (
            not registration
            or registration.get("family") != family
            or lang not in registration.get("languages", [])
        ):
            return {"registered": False, "lifecycle": "not_registered"}

    resolved = deepcopy(record["policy"][lang])
    resolved.update({
        "registered": True,
        "family": family,
        "language": lang,
        "repair": record.get("repair"),
        "decision_ref": record.get("decision_ref"),
        "consumers": list(record.get("consumers", [])),
    })
    if rule is not None:
        override = record["policy"][lang].get("rules", {}).get(rule)
        if override:
            resolved.update(deepcopy(override))
        resolved["rule"] = rule
    return resolved


def validate_manifest(
    *,
    manifest: dict[str, dict[str, Any]] | None = None,
    rule_registry: dict[str, dict[str, Any]] | None = None,
    calibration_records: dict[str, dict[str, Any]] | None = None,
    promotion_records: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    manifest = FAMILY_MANIFEST if manifest is None else manifest
    rule_registry = RULE_REGISTRY if rule_registry is None else rule_registry
    calibration_records = CALIBRATION_RECORDS if calibration_records is None else calibration_records
    promotion_records = PROMOTION_RECORDS if promotion_records is None else promotion_records
    errors: list[str] = []

    def validate_promotion(
        context: str,
        promoted_ref: Any,
        expected_identity: dict[str, Any],
    ) -> None:
        if not isinstance(promoted_ref, str) or not promoted_ref.strip():
            errors.append(f"{context}: enforced promotion missing promoted_ref")
            return
        promotion = promotion_records.get(promoted_ref)
        if not isinstance(promotion, dict):
            errors.append(f"{context}: promoted_ref {promoted_ref!r} unresolved")
            return
        for field, expected in expected_identity.items():
            if promotion.get(field) != expected:
                errors.append(
                    f"{context}: promotion {field} "
                    f"{promotion.get(field)!r} != {expected!r}"
                )
        for field in ("prevalence_ref", "hard_negative_ref", "decision_ref"):
            if not isinstance(promotion.get(field), str) or not promotion[field].strip():
                errors.append(f"{context}: promotion missing {field}")
        fixtures = promotion.get("fixture_refs")
        if (
            not isinstance(fixtures, list)
            or len(fixtures) < 2
            or any(not isinstance(item, str) or not item.strip() for item in fixtures)
        ):
            errors.append(f"{context}: promotion fixture_refs must contain a pair")

    for rule, registration in rule_registry.items():
        family = registration.get("family")
        if family not in manifest:
            errors.append(f"rule {rule}: family {family!r} missing from manifest")
        languages = registration.get("languages")
        if not isinstance(languages, list) or not languages or set(languages) - LANGUAGES:
            errors.append(f"rule {rule}: invalid languages {languages!r}")
            continue
        family_record = manifest.get(family)
        policies = family_record.get("policy") if isinstance(family_record, dict) else None
        if not isinstance(policies, dict):
            continue
        for lang in languages:
            family_policy = policies.get(lang)
            if not isinstance(family_policy, dict):
                continue
            overrides = family_policy.get("rules", {})
            has_override = isinstance(overrides, dict) and rule in overrides
            if (
                family_policy.get("lifecycle") == "enforced"
                and not has_override
                and (rule, lang, family) not in PRE_CONTRACT_INHERITED_RULES
                and not (
                    family_policy.get("promoted_ref")
                    and (rule, lang, family) in PRE_CONTRACT_RULE_IDENTITIES
                )
            ):
                errors.append(
                    f"{family}/{lang}/{rule}: new rule cannot inherit enforced lifecycle; "
                    "start with an explicit observe override"
                )

    for family, record in manifest.items():
        if not record.get("repair"):
            errors.append(f"{family}: repair missing")
        policies = record.get("policy")
        if not isinstance(policies, dict):
            errors.append(f"{family}: policy must be mapping")
            continue
        for lang, policy in policies.items():
            lifecycle = policy.get("lifecycle")
            if lang not in LANGUAGES or lifecycle not in LIFECYCLES:
                errors.append(f"{family}/{lang}: invalid lifecycle {lifecycle!r}")
                continue
            if lifecycle == "enforced":
                pre_contract = policy.get("pre_contract", False)
                if not isinstance(pre_contract, bool):
                    errors.append(f"{family}/{lang}: pre_contract must be boolean")
                if pre_contract:
                    expected_pre_contract = PRE_CONTRACT_POLICY_BASELINE.get(
                        (family, lang)
                    )
                    if expected_pre_contract is None:
                        errors.append(
                            f"{family}/{lang}: pre_contract identity is not grandfathered"
                        )
                    else:
                        actual_pre_contract = {
                            field: policy.get(field)
                            for field in _PRE_CONTRACT_POLICY_FIELDS
                        }
                        if actual_pre_contract != expected_pre_contract:
                            errors.append(
                                f"{family}/{lang}: pre_contract policy drift"
                            )
                promoted_ref = policy.get("promoted_ref")
                if not pre_contract or promoted_ref is not None:
                    validate_promotion(
                        f"{family}/{lang}",
                        promoted_ref,
                        {"family": family, "language": lang, "rule": None},
                    )
                if policy.get("sovereignty") not in {"S", "M", "L"}:
                    errors.append(f"{family}/{lang}: enforced policy missing sovereignty")
                baseline_policy = policy.get("baseline_policy")
                if baseline_policy not in {"calibrated", "exempt"}:
                    errors.append(f"{family}/{lang}: invalid baseline_policy {baseline_policy!r}")
                if baseline_policy == "calibrated":
                    metric = policy.get("baseline_metric")
                    ref = policy.get("baseline_ref")
                    if metric not in BASELINE_METRICS:
                        errors.append(f"{family}/{lang}: invalid baseline_metric {metric!r}")
                    calibration = calibration_records.get(ref) if isinstance(ref, str) else None
                    if not calibration:
                        errors.append(f"{family}/{lang}: baseline_ref {ref!r} unresolved")
                    elif (
                        calibration.get("family") != family
                        or calibration.get("language") != lang
                        or calibration.get("metric") != metric
                    ):
                        errors.append(f"{family}/{lang}: baseline_ref {ref!r} points to another policy")
                if baseline_policy == "exempt" and not record.get("decision_ref"):
                    errors.append(f"{family}/{lang}: exempt policy missing decision_ref")
                if policy.get("single_hit") and not record.get("decision_ref"):
                    errors.append(f"{family}/{lang}: single_hit missing decision_ref")
            else:
                if policy.get("pre_contract"):
                    errors.append(f"{family}/{lang}: observe policy cannot be pre_contract")
                if policy.get("promoted_ref"):
                    errors.append(f"{family}/{lang}: observe policy cannot carry promoted_ref")
                baseline_policy = policy.get("baseline_policy")
                if baseline_policy is not None:
                    if baseline_policy != "calibrated":
                        errors.append(
                            f"{family}/{lang}: observe baseline_policy must be calibrated"
                        )
                    metric = policy.get("baseline_metric")
                    ref = policy.get("baseline_ref")
                    calibration = calibration_records.get(ref) if isinstance(ref, str) else None
                    if metric not in BASELINE_METRICS:
                        errors.append(f"{family}/{lang}: invalid baseline_metric {metric!r}")
                    if not calibration:
                        errors.append(f"{family}/{lang}: baseline_ref {ref!r} unresolved")
                    elif (
                        calibration.get("family") != family
                        or calibration.get("language") != lang
                        or calibration.get("metric") != metric
                    ):
                        errors.append(
                            f"{family}/{lang}: baseline_ref {ref!r} points to another policy"
                        )

            rules = policy.get("rules", {})
            if not isinstance(rules, dict):
                errors.append(f"{family}/{lang}: rules must be mapping")
                continue
            for rule, override in rules.items():
                registration = rule_registry.get(rule)
                if (
                    not registration
                    or registration.get("family") != family
                    or lang not in registration.get("languages", [])
                ):
                    errors.append(f"{family}/{lang}/{rule}: rule is not registered for this language")
                    continue
                rule_lifecycle = override.get("lifecycle")
                if rule_lifecycle not in LIFECYCLES:
                    errors.append(f"{family}/{lang}/{rule}: invalid lifecycle {rule_lifecycle!r}")
                if lifecycle == "observe" and rule_lifecycle == "enforced":
                    errors.append(f"{family}/{lang}/{rule}: rule lifecycle above family lifecycle")
                if rule_lifecycle == "enforced":
                    validate_promotion(
                        f"{family}/{lang}/{rule}",
                        override.get("promoted_ref"),
                        {"family": family, "language": lang, "rule": rule},
                    )
    return errors


def registry_hash() -> str:
    payload = json.dumps(
        {"families": FAMILY_MANIFEST, "rules": RULE_REGISTRY},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def calibration_value(policy: dict[str, Any]) -> float:
    """Return the validated baseline selected by an effective policy."""
    if policy.get("baseline_policy") != "calibrated":
        return 0.0
    record = CALIBRATION_RECORDS.get(policy.get("baseline_ref"))
    if not record:
        raise ValueError(
            f"unresolved calibration for {policy.get('family')}/{policy.get('language')}"
        )
    return float(record["value"])


def density_contract_max_count(policy: dict[str, Any], total_units: int) -> int | None:
    """Existing user contract: canonical density must be strictly below its baseline."""
    if policy.get("lifecycle") != "enforced" or not policy.get("density_contract"):
        return None
    return max(math.ceil(calibration_value(policy) * max(total_units, 1) / 1000) - 1, 0)


# Derived compatibility views. New consumers should call effective_policy.
FAMILY_REGISTRY = {
    family: {
        "group": record["group"],
        "cluster": record["cluster"],
        "aliases": list(record.get("aliases", [])),
    }
    for family, record in FAMILY_MANIFEST.items()
}
FAMILY_GROUPS = {family: record["group"] for family, record in FAMILY_REGISTRY.items()}
FAMILY_CLUSTERS = {family: record["cluster"] for family, record in FAMILY_REGISTRY.items()}
RULE_TO_FAMILY = {rule: data["family"] for rule, data in RULE_REGISTRY.items()}
RULE_LANGUAGES = {rule: frozenset(data["languages"]) for rule, data in RULE_REGISTRY.items()}
AGGREGATION_ONLY_RULES = frozenset(
    rule for rule, data in RULE_REGISTRY.items() if data.get("aggregation_only")
)
BASELINE_EXEMPT_FAMILIES = {
    family
    for family in FAMILY_MANIFEST
    if effective_policy(family, "zh").get("baseline_policy") == "exempt"
}
FAMILY_DENSITY_BASELINE = {
    lang: {
        str(record["family"]): float(record["value"])
        for record in CALIBRATION_RECORDS.values()
        if record.get("language") == lang and record.get("metric") == "p90_positive"
    }
    for lang in LANGUAGES
}
OBSERVE_ONLY_FAMILIES = {
    family
    for family in FAMILY_MANIFEST
    if all(effective_policy(family, lang)["lifecycle"] == "observe" for lang in LANGUAGES)
}
FAMILY_SOVEREIGNTY = {
    family: policy["sovereignty"]
    for family in FAMILY_MANIFEST
    if (policy := effective_policy(family, "zh"))["lifecycle"] == "enforced"
}
PER_FAMILY_OVERRIDE = {
    family: deepcopy(policy["aggregation"])
    for family in FAMILY_MANIFEST
    if (policy := effective_policy(family, "zh")).get("aggregation")
}
DEVICE_BUDGET_CLASSES: dict[str, dict[str, float]] = {}
for _family_id in FAMILY_MANIFEST:
    for _device, _multiplier in effective_policy(_family_id, "zh").get("device_budget", {}).items():
        DEVICE_BUDGET_CLASSES.setdefault(_device, {})[_family_id] = float(_multiplier)


_MANIFEST_ERRORS = validate_manifest()
if _MANIFEST_ERRORS:  # fail closed at import, before any gate consumes drifted policy
    raise RuntimeError("invalid AI policy manifest: " + "; ".join(_MANIFEST_ERRORS))
