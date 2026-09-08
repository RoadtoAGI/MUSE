# A 组审查：非触发边界前置 + 承载完整性

> 本子文件承载 A 组审查的**协议层规则**：病灶非触发边界判断（与 prose-craft cliche 表 + scene-review 协议同源）+ 承载完整性核验（与 `craft_carrier` 字段联动）。主表逐项检查见 [`A_aesthetic.md`](A_aesthetic.md)。

## §0 非触发边界前置

> 与 prose-craft/references/ai-cliche-patterns.md §"病灶非触发边界" 配套。

A 组扫到 AI 病灶 / 审美问题位置时，先核常见边界机制及其补强字段（与 [`scene-review/SKILL.md`](../../scene-review/SKILL.md) "非触发后处理" 同源）：

1. 信息缺失类病灶（如 omniscient_overexposure 反向触发 / 反应过淡 / 信息不足）：局部 POV 证据证明人物无法接触信息；`scene_card.pov_constraint.intentional_blind_spot` 可补强
2. 解释缺席类病灶（如 psychological_overfill 反向 / 顿悟无内容 / 临终极简）：动作、物件或留白在局部文本中已经承载意义；`scene_card.omission_plan` 可补强
3. 文体冷感 / 不可靠叙述类病灶：局部声线与认知偏差证明叙述机制；`scene_card.narrator_distance`（`archival_zero` / `unreliable_first` 等）只提供补强的叙述状态证据，`subtext_translated_by_narrator` 与 `signature_voice_overuse` 仍按各自病理机制逐句判断
4. 配角长独白被报"AI 注水"：局部文本满足 reframing 判读并承担具体叙事功能（见 [`A_aesthetic-micro_language.md`](A_aesthetic-micro_language.md) §reframing 独白判读）

**非触发资格由两项成品证据决定：引用局部文本，并具体说明其叙事、视角、角色或节奏功能。两项同时成立时，对应病灶不适用，不写 finding。**

scene_card 预声明只增强设计意图与状态证据，不作前置；字段缺失不取消成品证据已经成立的资格，也不单独要求回滚。只给字段或抽象主观判断仍不足。完整边界表与执行约定见 [`prose-craft/references/ai-cliche-patterns.md`](../../prose-craft/references/ai-cliche-patterns.md) §"病灶非触发边界"。

## §11 承载完整性检查

> 与 `craft_carrier` 字段联动。

读 `pipeline/scene_{id}/scene_card.md` 中的 `craft_carrier.type` 与 `craft_carrier.concrete_anchor`。逐场景核：

| 检测项 | 判据 | 报告落点（`dimension: ai_pattern` + subkind） |
|---|---|---|
| **carrier 缺席** | scene_card 承诺的叙事功能在正文中未实现；替换、合并或舍弃候选材料后仍实现功能的用法合法 | `subkind: carrier_missing` |
| **carrier 已完成意义后被解释** | carrier 出现并完成意义后，正文又用心理 / 主题语言重复同一意义 | `subkind: carrier_then_explain`（与 `psychological_overfill` 联动，但 `psychological_overfill` 是任何场景的通病，`carrier_then_explain` 是"已设计 carrier 仍解释"的强失守） |
| **carrier 反向解释** | 正文解释破坏了仍须成立的信息保留或体验，例如提前泄露受保护答案；说明计划与实际效果的冲突 | `subkind: omission_violated` |

craft_carrier 字段缺位时跳过本节，不强制。
