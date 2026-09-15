# 场景补丁格式

仅 PATCH 产 `pipeline/scene_{scene_id}/patch_directive.yaml`。单句使用 `anchor_quote`；连续片段使用 `old_span` 及首尾锚点，均需精确命中当前正文。同句重复时用 `location.line_range` 确定唯一位置；修订后行号变化应重新定位。

```yaml
source: scene_review
scene_id: S01
patches:
  - anchor_quote: 他又一次说明了自己为何不能离开。
    location: 中段重复解释处
    issue: 上一句已完整交代原因，此处复述也不承担回指、承接或人物语气。
    suggested_action: 删并重复；保留离开限制，并确认后句仍能自然承接。
    issue_id: A-S01-repeat
    patch_kind: null
```

需要句法重写时可用 `rewrite_sentence` 或 `rewrite_span`，由原文锚点确定修订范围。`max_sentences` 仅在作者或本次修订授权明确限制句数时选填，不从片段长度自动生成。

```yaml
source: scene_review
scene_id: S01
patches:
  - patch_id: patch_01
    patch_kind: rewrite_span
    anchor_quote_start: 他又一次说明了
    anchor_quote_end: 门外等待。
    old_span: 他又一次说明了自己为何不能离开。她仍在门外等待。
    location:
      line_range: [7, 7]
    issue: 重复说明拖住等待中的反应。
    suggested_action: 合并重复解释，保留不能离开、对方等待及两者的承接关系。
    rewrite_directive:
      semantic_function: 保留行动限制及等待关系。
      preserve: [他不能离开, 她仍在门外等待]
      remove_patterns: [重复解释]
      target_style: 指称与解释顺序清楚，与上下文声音相容。
      allowed_carrier_changes:
        low_intensity: true
        plot_adjacent: []
```

`rewrite_sentence` 使用 `anchor_quote` 替代 span 三字段，其余 rewrite_directive 同上。低强度表达可按授权调整，涉及物件状态、位置、动机或事件结果的变更须明确允许；需要改变有效事实时回源。

机器聚类、分布统计和旧复审 gate 使用脚本自己的产物格式，本补丁不复制这些 schema。已存在的旧字段可用于定位其当时的问题，修订仍以当前正文与有效约束为准。完整方向名见 [patch registry](../../patch-revision/references/patch-kind-registry.md)。
