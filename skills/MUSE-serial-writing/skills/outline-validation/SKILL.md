---
name: outline-validation
description: 核对连载设计中具体的时间、世界约束与引用矛盾。由 serial-outline 在系列/卷设计存在跨源疑点时，或 serial-chapter-writing 在章内编排完成后按疑点或用户要求调用。使用实际系列资料及已存在的设计文件，写入 design_validation.yaml；内部诊断技能，审美与方向选择由作者裁决。
---

# 设计一致性校验

核对当前设计是否同时要求两个不能共存的事实，或引用了无法定位的对象。发现问题后指出来源、成立条件与负责修复的环节，供调用方在正文采用该设计前处理。世界规则、时间算术与引用接口属于本技能；创作质量、人物轨迹优劣和手法偏好由创作技能及作者判断。

## 调用输入与范围

调用方提供 `scope`、`series_root`、`work_dir`、本次疑点及相关文件路径。`series_root` 是包含 `series/` 与 `published/` 的作品根；`work_dir` 决定报告位置。

| scope | work_dir 与标识 | 首先核对的资料 |
|---|---|---|
| `series` | 等于 series_root | story_bible、有关决定、世界册及人物资料 |
| `volume` | 等于 series_root；给 volume_id | 当前卷纲、所依赖的系列约束及既有经历 |
| `chapter` | 本章目录；给 volume_id、chapter_id | 本章卷纲条目、章卡、已装配的 serial_context 与 phase5_scenes |

先读被指出的设计及其约束来源，再沿矛盾所需的引用补充材料。人物、事实和知识的时点依 [上下文协议](../serial-chapter-writing/references/context-contract.md)；持久化字段依 [workspace-schema](../serial-outline/references/workspace-schema.md)。历史章核对不能把共享最新状态当作当时事实。

已存在的 `phase0_conception.yaml` 至 `phase5_scenes.yaml`、人物 adapter 或角色包，可作为明确适用于本次范围的补充资料。接管和系列规划使用其真实来源；缺少整篇 Phase 文件不构成错误，也不补造这些文件。字段中的未来方向、人物信念、待定问题与原文事实分别解释。来源冲突时回到作者决定、原文或有权维护该来源的环节，派生文件不能自行覆盖它们。

## 判断与执行

三类核对按本次疑点选择，详细边界与案例见 [校验指南](references/validation-guide.md)：

- **时间**：保持来源给出的精度，比较日期、年龄、时长及事件先后能否同时成立。阅读顺序和事件顺序分别核对。
- **世界约束**：将设计中的能力、资源、事件与适用的事实、公理、上限和明确条件对照。把人物信念或一般风气当成绝对世界规律会改变原约束。
- **引用**：核实本次使用的角色、章、场景、世界册、决定及灵感卡能否明确定位；只检查当前范围应承担的映射。

`review_findings` 只收确定矛盾或已经确立的接口不符。每项同时给出两端位置、原措辞及不能共存的理由；无法从现有输入区分的情况列入 `summary.input_gaps`，说明缺哪项资料、影响哪项判断。资料缺失和已证明矛盾分别回交，避免用空报告表示未完成的检查。

人物可以改变习惯、保持稳定或坦白真相；不同叙事驱动也可以共存。只有它们与已确认事实或作者约束发生具体冲突时才报告。`primary_drive`、人物轨迹等标签帮助理解设计，不通过复制标签、固定组合或要求主题分配给特定角色判定合格。

## 报告与回交

按 [报告 schema](references/output-schema.md) 写入 `<work_dir>/pipeline/review/design_validation.yaml`。本次只覆盖调用方给出的范围与查明的相关依赖。完成回执简述实际范围、已读来源、报告路径和是否存在输入缺口，让调用方读取本次报告；文件存在本身不表示当前设计已通过。

调用方将 finding 回交 `suggestion` 指定的负责环节：系列来源由 serial-outline 路由，卷设计由 volume-outline 修复，场景设计由 chapter-scene-plan 修复，派生/装配错误回相应输入环节。涉及修改作者决定或已发布内容时保留其裁决权限。依赖问题设计的正文暂不推进，其他已授权且不受影响的工作可以继续。

修订后复核原矛盾及其受影响引用；已成立且未变化的部分直接沿用。无 finding 且无 input_gaps 表示本次指定范围未发现硬性不符，创作效果仍由正文与作者判断。既有 `mode_alignment.yaml` 可作历史材料读取，其状态不代表本次检查或新的放行凭据。
