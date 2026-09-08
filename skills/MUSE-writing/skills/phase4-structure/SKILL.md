---
name: phase4-structure
description: 序列设计阶段。把 Phase 3 幕或 Arc 展开为中程剧情单元，明确局部变化、因果关系与阅读顺序，产出 phase4_structure.yaml 供 Phase 5 编排场景。
---

# Phase 4：序列设计

把幕或 Arc 展开为能让后续继续行动、解释或感受的序列。麦基《故事》第九章讨论进展纠葛与不可轻易返回的点；本阶段据此组织中程变化，外部强度可以回落，信息、关系或选择代价可以接管推进。

## 输入与加载

读取 Phase 3 的 `arcs`、`inciting_incident`、`opposing_forces`、`spine_mode`、`reader_spine` 和 `story_climax_design`，以及 Phase 0 的作者要求与核心认识、Phase 1 的有关世界条件、Phase 2 的相关人物追求和轨迹。危机两难未成立时 `option_a/option_b` 可为 null；继承实际条件和后果，候选台词或字段顺序不规定表现方式。

填写前读[输出 schema](references/output-schema.md)，理论和组织边界见[结构参考](references/mckee-structure.md)。关键走向未定或被退回时，按[大纲构思与回读](../story-writing/references/outline-exploration.md)推演不同推进方式。需要新来源时加载 `design-doc-reference`，传 `phase=4`、开放的 `narrative_problem` 和已有结构条件，读取返回的 `phase4_design_ref.md`；已有适用材料直接复用，作者排除的参考不使用。

## 组织序列

为每个 Arc 设计其需要的序列：本段围绕什么关系或问题，条件怎样变化，哪个事件形成局部高潮，结果怎样承接到后文。`core_conflict/escalation_direction/sequence_climax/closed/opened` 的字段含义由 schema 统一规定。

序列数量按实际中程变化确定。激励事件应有清楚的结构位置，可以先建立处境再出现。最终序列抵达已定的高潮和结果，收束后可以没有新问题。

`desire` 可从策略、对抗与取舍观察变化，`information` 可看证据怎样改变判断，`motif` 可看重复、变奏与对位怎样产生新认识。这些是项目组织视角，实际设计可以结合使用。序列要能说明阅读推进发生在哪里；更大声的争吵、更多困难或技巧名称本身不足以说明。

`causal_chain` 写实际事件依赖，序列列表写读者看到的顺序。倒叙、插叙、交替视角可以使两者不同；平行段落可以经由对位改变理解。检查各条因果是否可重建、信息是否在合理时点取得，以及跳转是否需要读者识别锚，不能为相邻列表项强造因果。

真实多线且 Phase 5 需要定位时使用 `narrative_threads`，记录 `line_id/description/sequence_refs`；跨线影响写进已有序列结果或因果链。单线省略该块。

## 交付与回查

写入 `pipeline/phase4_structure.yaml`。每个序列保留足够具体的关键事件和结果，完整场景清单、微观动作与对白由 Phase 5/6 展开。

核对序列是否形成可辨变化、承接必要结果，人物能力与知识是否支持事件，最终结果是否符合作者已定意图。缺少真实推进时合并或重新设计；合法的停顿、回望和形式对位按其阅读作用保留。必要前提变化时回到对应阶段，更新受影响依赖。
