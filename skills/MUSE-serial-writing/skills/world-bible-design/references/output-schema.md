# 连载世界交付契约

权威接口见 [workspace-schema 的 worldbook](../../serial-outline/references/workspace-schema.md#seriesworldbook--分域设定集)。本技能写 `series/worldbook/index.yaml` 与已注册分册；总纲负责人同时保持 `story_bible.frozen.world_ceiling` 等承诺一致。

```yaml
schema_version: 1
sections:
  - section_id: civic-order
    file: civic-order.md
    title: 城市制度与日常
    mutability: axiom
    summary_line: 城内居留、配给与执行机构的规则
```

`section_id` 与分册文件名对应；mutability 为 axiom 或 append。分册先写带依据的硬约束，后段以精确标题 `## 素材库` 开始，再写素材、质感和可选细节；装配器用该标题区分硬约束与可裁剪素材。分册清单按 genre_profile 对应 genre-pack 与当前需要确定；模板已有字段沿既有 schema，不另造 Phase 1 输出。

| 内容 | 消费方式 |
|---|---|
| index 的 summary_line 与公理册硬约束 | 章上下文恒注的世界地图与边界 |
| 本章有关的机制册与素材 | 章卡 recap_inputs.worldbook_sections 选择后装配给 writer / reviewer |
| 规则的来源、限制和例外 | 人物与卷纲设计核对可行选择，写作检查后果 |
| 运行期变化 | 由 world_facts 台账记录，避免改写静态设定 |

场景涉及某规则而切片尚未选中时，补当前章选择并刷新上下文。引用路径和文件存在不等于 writer 已取得内容。分册的冻结、追加与缺省兼容规则均沿 workspace-schema；已有作品的材料保持原状，按当前授权做必要映射。
