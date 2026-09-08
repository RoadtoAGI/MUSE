# Phase 1 输出

文件：`pipeline/phase1_world.yaml`。保留已有键名，填写与当前故事有关的内容。

```yaml
setting:
  era: 时代或架空范围
  duration: 故事时间跨度
  location: 空间范围
  conflict_levels: []
genre_conventions:
  primary_genre: 主导类型
  secondary_genre: null
  conventions: []     # 每项 convention，可选 planned_subversion
generative_driver:
  mechanism: 持续压力或变化如何发生，以及当前已知的作用条件
  # 自由结构；可说明未明成因、局部表现、适配关系
world_rules:
  physical: []
  social: []
  psychological: []
daily_life: []          # 按需；每项 dimension、findings[{detail, story_implication}]
domain_knowledge: []    # 按需；每项 topic、details、source
creative_constraints: [] # 按需；每项 constraint、narrative_function
```

| 字段 | 消费者与语义 |
|---|---|
| `setting` | Phase 2 人物背景、Phase 4–6 事件时间与地点；保留原有时间精度 |
| `genre_conventions` | Phase 4–6 阅读期待与实现选择；颠覆可省略 |
| `generative_driver` | Phase 2/5/6 推演人物条件、威胁和后果；自由结构，不要求虚构终极成因。指定 `world_rule` 来源时写清保留机制及适配范围 |
| `world_rules` | Phase 2–6 保持事实与因果；独立制度或习俗可有自己的依据，不要求所有规则出自一个原因 |
| `daily_life` | Phase 2 人物生活、Phase 6 叙述经验；取自有效资料或明确的虚构设计，来源与设想在 detail 中可辨 |
| `domain_knowledge` | 用户提供或经核实的专业背景，保留 source；有适用内容时生成 |
| `creative_constraints` | 后续选择与后果的边界；按实际需要填写 |

前四项承载基本世界设计；其余按需省略或留空。现实、制度、习俗和信念的不同约束强度在字段内容中说明。不存在心理特殊规律时可保留空列表。

世界研究实际开展时，报告写入 `pipeline/world_research.md`，`daily_life` 承接有关发现，报告提供来源和语境供疑点回查。该报告的存在不代替有效事实已经进入 YAML。
