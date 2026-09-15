# A 组审查：语境与承载完整性

> 本子文件汇集会改变语义判断的常见语境，并核对 `craft_carrier` 已承诺的作用。问题与报告判据沿 [`A_aesthetic.md`](A_aesthetic.md) 和 [`scene-review/SKILL.md`](../../scene-review/SKILL.md) 执行。

## §0 语境判读

下列语境帮助核实候选位置的实际作用。回读相关句段后，依据可定位的阅读损害决定是否报告；设计字段补充意图和条件：

1. 信息延迟或视角未知：局部 POV 证据证明人物无法接触信息；`scene_card.pov_constraint.intentional_blind_spot` 可补强
2. 意义已经可恢复的省略：动作、物件或留白在局部文本中已经承载意义；`scene_card.omission_plan` 可补强
3. 文体冷感 / 不可靠叙述：局部声线与认知偏差证明叙述机制；`scene_card.narrator_distance`（`archival_zero` / `unreliable_first` 等）只提供补强的叙述状态证据，`subtext_translated_by_narrator` 与 `signature_voice_overuse` 仍按实际句段作用判断
4. 配角长独白：局部文本满足 reframing 判读并承担具体叙事功能（见 [`A_aesthetic-micro_language.md`](A_aesthetic-micro_language.md) §reframing 独白判读）

finding 引用当前正文并说明具体失效及其影响。实际表达有作用时保留，普通候选无需逐条申请豁免；scene_card 字段缺失本身不构成问题。更完整的表达机制见 [`prose-craft/references/ai-cliche-patterns.md`](../../prose-craft/references/ai-cliche-patterns.md)。

## §11 承载完整性检查

> 与 `craft_carrier` 字段联动。

读 `pipeline/scene_{id}/scene_card.md` 中的 `craft_carrier.type` 与 `craft_carrier.concrete_anchor`。逐场景核：

| 检测项 | 判据 | 报告落点（`dimension: ai_pattern` + subkind） |
|---|---|---|
| **carrier 缺席** | scene_card 承诺的叙事功能在正文中未实现；替换、合并或舍弃候选材料后仍实现功能的用法合法 | `subkind: carrier_missing` |
| **承载后的冗余解释** | 后续心理 / 主题语言反复结算已成立的意义，未承担回指、承接、认识、关系、声音或节奏作用，并造成可说明的阅读损害 | `subkind: carrier_then_explain`（与 `psychological_overfill` 联动） |
| **carrier 反向解释** | 正文解释破坏了仍须成立的信息保留或体验，例如提前泄露受保护答案；说明计划与实际效果的冲突 | `subkind: omission_violated` |

craft_carrier 字段缺位时跳过本节，不强制。
