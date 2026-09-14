---
name: chapter-summarizer
description: 连载定稿的前情摘要与台账候选生成。由 serial-chapter-writing 在章审阅和防治完成后调用；单元或卷结束时生成对应 digest。
---

# 章节摘要与台账候选

recap 同时服务下一章的前情输入和发布事务的事实转正；digest 供较远章节降低读取量。正文是发生事实的依据，设计文件只说明原意和标识。正文没有兑现的计划留在设计层，不写成已发生。

本技能写 recap / digest，不修改正文或台账。发布获授权后，现有事务先校验、转正候选，再复制正文，最后登记 manifest；buffer 内候选尚未转正。

## 输入与来源

调用明确 `series_root`（含 series / published 的作品根）、`work_dir`（章目录）、`chapter_id`；生成 digest 时再给卷或单元范围。先读：

- 当前定稿 `draft.md`、章卡与本章卷纲条目，确定实际事件、章末状态和本章职责。
- 本章 `serial_context.md` 及相关 `threads`、人物经历、事实原记录，连接现有 ID、状态和知情者。需要 `supersedes` 时回查被替代的真实 fact_id。
- 本章之前有效 buffer 链的相关 recap；未发布候选保持其来源，不能冒充已转正 ID。
- 有揭示事件时读对应 `world_reveal_plan`；生成 digest 时读范围内 recap，缺 recap 的接管历史使用 manifest 对应原文和已核对卷纲摘要。

资料按[上下文协议](../serial-chapter-writing/references/context-contract.md)取时点和实体。角色 ID 与显示名分开，设计诊断、猜测及未来方向保留原有强度。

## 写 recap

输出 `<work_dir>/recap.yaml`。字段权威为 [workspace-schema](../serial-outline/references/workspace-schema.md)，新建时读[模板](../serial-outline/references/templates/recap.yaml)。

`summary` 用一段承接后续判断：主要事件及结果、发生变化的人物处境和关系、必要的认识或情绪状态、仍有效的未决问题与章末落点。按本章实际需要取舍，保留误解、未知和因果联系。摘要不把人物意图改成下一章的动作命令。

四类 `deltas` 均可为空：

| 候选 | 提取条件与连接 |
|---|---|
| `fact_deltas` | 跨章有效且将影响后续判断的事实或状态。场内瞬态留在正文/摘要。能力与规则保留真实限制；`supersedes` 指既有 fact_id；秘密按实际获知者与 `learned_at` 记录，不能将作者所知发给所有角色。兑现揭示时填实际 `source_reveal_id` |
| `thread_events` | open 给出稳定 thread_id、thread_kind、statement 和 intended_payoff；advance/payoff 指已入账、有效前章候选或本章此前 open 的线程。正文兑现情况与卷纲 opened/closed 不符时回报编排负责人，发布前对齐当前获准设计 |
| `character_deltas` | 值得长期保留的身份、认识、关系、能力或处境变化，包括创伤、损失、退场。保留 char_id 与 milestone 的 at/kind/before/after/evidence；日常互动、稳定信念和普通目标不强造为成长或誓言 |
| `causal_edges` | 本章结果确实依赖的前章及具体因果；仅相邻或主题相似不构成因果边。前后按作品的实际链确定 |

同一秘密内容的知情范围扩大时，新版本的 known_by 保留仍成立的原获知记录，再追加本章获知者；若秘密内容改变，分别判断谁获知了新内容，不能自动继承知情权。

尚无转正 ID 的前章候选，在当前 fact_delta 的既有 note 中保留前章号、所指事实及替代关系，supersedes 暂空；可继续 buffer 创作。orchestrator 在当前章转正前按前章链发布所依赖的前章，再交 summarizer 在同一 recap 补入已能查到的真实 fact_id。依赖未解只阻断当前章发布，不以虚构 ID 或无说明空值放行。

## digest 与完成条件

单元完成后产 `series/digests/V##-U##.yaml`（[模板](../serial-outline/references/templates/digest_unit.yaml)）；卷收束时产 `series/digests/V##.yaml`（[模板](../serial-outline/references/templates/digest_volume.yaml)）。每个范围生成一次；来源后来改变时再更新受影响摘要。缩写仍保留结果、有效关系和未决义务，不能凭卷纲补写结局。

落盘前核对章号、summary 与列表结构，以及每条候选的来源和连接。可选变化证据不足时不立该条，正文或摘要保留可观察事实；既有明确义务、必需标识或已输出候选有误时，报告具体缺口并回来源负责人。需要改变作者已确认事实时才交用户，避免不确定就反复重写。

完成回复只给产物路径、实际摘要范围和未解决的必要输入。orchestrator 对照当前正文确认摘要中的事件结果与章末落点后，纳入 buffer 或既有发布流程。
