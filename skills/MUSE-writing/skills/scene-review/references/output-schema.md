# Scene Review Output Schema

本文件记录 scene-reviewer 输出 schema 的机器热路径字段。R 轮 `post_revision_updates` 仍保持 append-only list，不在其下挂 semantic migration 状态。

## patch 保护完整性声明

每条 patch 可选声明两组保护项。声明在 reviser dispatch 前由 validator 快照到 `pipeline/scene_{scene_id}/protected_integrity.yaml`；后续 pending directive 的裁剪不改变既有快照。

```yaml
application_id: S01-scene-review-round1  # 新 application round 唯一；同轮重试复用
patches:
  - patch_id: patch_02
    protected_tokens:
      - token_id: T-S01-01
        patch_id: patch_02
        source: scene_card | reuse_manifest | old_span
        raw: "十七岁"
        match_mode: exact | normalized
        accepted_forms: ["17 岁"]       # exact 时必须为空；normalized 时穷举允许形
        scope: patch_span | scene
    protected_relations:
      - relation_id: R-S01-01
        patch_id: patch_02
        type: agency | polarity | modality | causality | temporal | comparison
        expected: "一句可核验的关系预期"
        before_quote: "修订前承载该关系的正文原句"
```

硬约束：

- `application_id` 必填且在同一 scene 的新施工轮之间唯一；同轮重试保持不变。每条 patch 的 `patch_id` 必填且在该 application 内唯一。
- `token_id` 与 `relation_id` 共用 run 级唯一命名空间；每项 `patch_id` 必须与父 patch 相同。
- `protected_tokens` 由脚本按 `raw / accepted_forms / scope` 确定性核验，缺失即 hard fail。
- 当前 application batch 的 relation scopes 关闭免 reviewer 快速通道。post-revision reviewer 按 `(patch_id, relation_id)` 复合身份逐项核验；当前 applied scope 必须等于本轮核验集合，not_applied 与未触及的历史 relation 沿用既有 active anchor。
- PASS relation 记录的 `after_quote / current_span / scene_sha` 形成后续轮次的 active anchor。

## cluster_alerts 字段

aggregation 层输出，不归 FAMILY_REGISTRY。详 design doc §4.2 schema 草案。

```yaml
cluster_alerts:
  - alert_id: <str>
    scope: scene | paragraph | span
    family: <family_id>
    cluster: <cluster_name>
    group: semantic_heuristic | hard
    rule_counts: {<rule_name>: <count>}
    total_count: <int>
    density_per_1k: <float>
    hit_ids: [<lint_hit_id>, ...]
    distribution:
      mode: single_span | single_sentence | distributed | catastrophic | paragraph_pattern
      paragraph_count: <int>
      contiguous: <bool>
    severity: low | medium | high
    review_guidance:
      assessment: diagnostic
      decision_basis: current_text_function_and_readability
```

## pattern_migration_gate.semantic_function_migration 字段

```yaml
pattern_migration_gate:
  evaluated: true
  gate_pass: <bool>
  cross_cluster_migration: <bool>
  same_cluster_migration: <bool>
  semantic_function_migration:
    detected: <bool>
    migrations:
      - old_function: contrastive_explanation
        forbidden_new_patterns: [actually_assertion, true_actual_template, ...]
        detected_in_v2:
          - anchor_line: <int>
            matched_text: <str>
            matched_pattern: <pattern_name>
            verdict: failed
```

## 机器台账指针

ai_filler 病灶台账为 `pipeline/review/{scene_id}.machine_ledger.yaml`，schema 权威 = 生成脚本产物本身（entries[].id/family/level/status）；本文件不镜像。旧产物 `lint_resolution_ledger.yaml` 缺 machine ledger 时按其初始 triage 块 + 最后 update 块解释。
