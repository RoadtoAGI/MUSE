# Phase 6 输出 Schema

## 正文文件

每个场景写入独立的 markdown 文件：`pipeline/scenes/scene_{id}.md`

场景文件是纯叙事文本（含对白），不包含结构化字段、节拍标注或元数据。这些文件是正文的唯一权威来源（narrative source of truth）。

## 索引文件

交付物文件：`pipeline/phase6_development.yaml`

```yaml
total_word_count: 8500
scenes:
  - scene_id: S01
    file_path: pipeline/scenes/scene_S01.md
    summary: 场景一句话摘要
    beats: 自由格式——按场景类型选择合适的记录方式
    word_count: 850
    value_change:
      from: 起始价值
      to: 终止价值
    consistency_notes: 与前序交付物的一致性备注（可选）
```

`beats` 没有固定结构。根据场景类型选择合适的记录粒度：

- **对白场景**：可记录 action / reaction / subtext（已说 vs 未说）
- **叙事/内心戏**：可记录行为变化点和认知转变
- **动作/环境场景**：可记录关键事件节点
- **简单场景**：一句话概括节拍走向即可

理论参考：麦基的节拍分析是剖析已有场景的诊断工具，不是创作模板。逐节拍设计仅建议用于关键场景（转折点、高潮、激励事件），一般场景在创作中自然生长。

## 字段说明

| 字段 | 必需 | 下游使用 |
|------|------|---------|
| `scenes[].file_path` | 是 | Phase 7（读取正文进行拼接） |
| `scenes[].scene_id` | 是 | Phase 7（按编排顺序排列） |
| `scenes[].summary` | 是 | 溯源审计（场景概述） |
| `scenes[].beats` | 否 | 溯源审计（写完后回填，自由格式） |
| `scenes[].word_count` | 是 | 报告字段（用户感知场景规模），不阻断 |
| `total_word_count` | 是 | 报告字段（用户感知全文规模），不与 `target_length` 做硬比较；**不触发 second writer pass** |

## 文件分工规则

- **正文工件**（`scenes/scene_{id}.md`）= narrative source of truth
- **YAML 索引**（`phase6_development.yaml`）= structural source of truth
- YAML 不保存完整正文，避免双份正文源漂移
