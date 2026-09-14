---
name: inspiration-research
description: 连载设计中的灵感与原型研究。由 serial-outline 围绕当前叙事问题、指定书目或原型调用，提供有来源的候选卡供设计负责人采用。
---

# 连载灵感与原型研究

## 当前问题与来源

输入 work_dir，以及 books、prototype_description、narrative_problem 中已有的一项或多项；同时使用调用方给定的版本、改编范围、逐来源用途和已知条件。slug 可省略，按原型生成独立 ASCII kebab-case。指定书目优先；仅有开放问题时先按当前设计尺度查询 design-doc-reference 的已有材料。思想与核心关系用 phase_id=0，世界、人物或结构问题按相应设计尺度选择。类型参数使用来源包认可的 genre，具体表达目标放 narrative_problem，类型未定时可省略。

资料可以互补：已有作品走 [canon 查询](references/canon-path.md)，公开资料走 [web 核实](references/web-path.md)，用户材料直接读取。使用宿主可用入口，知识库只读；查询不隐式启动建库。缺少指定版本的必要依据时返回缺口，已有有效材料仍可使用。

## 解释与候选

围绕当前问题研究原作具体构想、情境、关系与后果。机制解释说明为何成立、迁移需要什么条件；文本分析、作者自述与当前适配建议分别保留效力。原型卡不预先约束新作人物动作。

按 [card 契约](references/prototype-card-schema.md) 写 `pipeline/references/prototypes/{slug}/prototype_card.yaml`，返回本轮有效路径及影响设计的发现。同一来源已有有效卡可复用；摘要不足时补原文，无需重复研究。文件身份、来源与枚举核对沿现有接口。

## 进入创作上下文

当前设计负责人选择采用项，按 card 的映射写入已有设计字段或 `pipeline/inspiration_ledger.yaml`。迁移记录保留原作机制、适用原因以及本作对象、时点、必要结果和可改范围。未采用候选继续留在卡中。

writer 通过当前 scene_card.inspiration_refs 消费采用项；章物化沿既有 ledger 链接。条目缺失、来源定位失效或摘要改变了机制时，回到采用/装配环节修正。参考只需说明改变了哪项设计判断，不新增阅读报告或审计步骤。
