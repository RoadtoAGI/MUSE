# 人物对白画像 schema

本文件是 `characters/{role-slug}/dialogue-profile.yaml` 的字段权威。完整人物形象继续由同目录 `SKILL.md` 拥有。

```yaml
schema_version: dialogue-character/v1
character_id: novel:作品目录名:role-slug
work_id: novel:作品目录名
display_name: 角色名
profile_tier: full                 # full | compact | voice_only
character_skill: SKILL.md
evidence_events: [novel:作品:S01:e01]

baseline_voice:
  observed_summary: 可观察的词汇、句法、节奏、修辞、沉默和动作倾向
  evidence_locators: [scenes/scene_01.md:L8-L12]

relationship_registers:
  - counterpart: novel:作品:other-role
    relation: superior_subordinate
    address_forms: []
    cooperation_baseline: partial
    permitted_offense: medium
    explanation_patience: low
    evidence_events: [novel:作品:S01:e01]

pressure_transformations:
  - trigger: public_humiliation
    capacity_change: strained_to_degraded
    observable_changes: [句子缩短, 只纠正关键词]
    evidence_events: [novel:作品:S03:e02]

interaction_patterns:
  controls_conversation_by: []
  evades_by: []
  attacks: []
  repairs_relationship_by: []

negative_space:
  rarely_says: []
  cannot_admit: []
  unsupported_inference: []

prototype_axes:
  agency: high
  cooperation: low
  relationship_cost_tolerance: high
  self_transparency: low
  pressure_capacity: degrading
  rhetoric_orality: oral
  blind_spot: 原文支持的持续误读

prototype_eligible: true
review_status: reviewed
```

## 层级

- `full`：稳定声音、关系语域和压力下变化均有事件证据，能支持跨处境的人物原型；
- `compact`：有可观察的表达依据，但不足以支持跨关系或压力变化的完整原型；
- `voice_only`：一次性、匿名或证据很少，只记录场景功能与可观察语言。

层级表达证据深度。它不表示人物重要性的高低，也不授权补写缺失心理。

## 原型准入

`full` 且每个 `prototype_axes` 判断均有事件证据时，`prototype_eligible: true`。`compact` 与 `voice_only` 仍进入检索索引，但权重较低，不作为完整人物原型绑定。
