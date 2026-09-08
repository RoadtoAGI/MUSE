# 审稿报告格式

报告只列当前输入支持的问题，空报告为 `review_findings: []`。调用方显式选取本次报告；文件名或空列表不能证明读取了正确正文。

```yaml
review_findings:
  - dimension: factual_detail
    subkind: null
    severity: IMPORTANT
    scene_id: S03
    location: S03 第三段
    evidence_quote: 他把唯一的钥匙留在了门外。
    contradiction_pair: S03 后段：“他从自己的衣袋里取出那把钥匙。”
    source: story
    issue: 同一把钥匙的存放位置冲突，期间没有取回或其他可成立的说明。
    suggestion: 根据有效事实核对钥匙去向，再修正不相容的一端。
summary:
  total_issues: 1
  by_dimension:
    factual_detail: 1
```

`dimension`、`scene_id`、`location`、`evidence_quote`、`source`、`issue`、`suggestion` 必填。`scene_id` 为 null 表示全文问题；能定位场景就填实际 ID。`source` 为 story 或 pipeline，按问题来源选择。引用不得伪造：缺失类问题引用其发生位置的实际文本，再在 issue 说明缺少的必要信息；相关约束放 contradiction_pair。

`severity` 为 CRITICAL / IMPORTANT / INFO；缺省 IMPORTANT。CRITICAL 需要明确说明被破坏的事实、因果或有效作者约束；审美偏好和不确定风险不自动阻断。`subkind` 用于细分既有维度，名称不决定修改范围。

| 组 | dimension | 文件 |
|---|---|---|
| A | ai_pattern, voice_consistency, value_change, on_the_nose, credibility, action_log, micro_language, sensory_balance, pov_boundary, scene_ending | pipeline/review/A_aesthetic.yaml |
| B | characterization, factual_detail, narrative_style | pipeline/review/B_narrative_consistency.yaml |
| C | timeline_plot, world_building, pipeline_crosscheck | pipeline/review/C_structural_consistency.yaml |

micro_language 的 subkind 使用 false_literary_diction / sensory_mismatch / abstract_judgment_without_action / stock_speech_tag / weak_character_expression。INS 条目使用 C 指南的既有 subkind；continuity-check 使用 `serial_continuity`，由调用方并入 B，更新 summary 并保留有效条目。

summary 统计本次报告实际问题。报告写完回复文件路径和必要输入缺口，由调用方交 scene-review 或对应负责人，不在报告中修改正文。
