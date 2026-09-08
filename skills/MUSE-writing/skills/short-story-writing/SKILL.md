---
name: short-story-writing
description: MUSE 完整原创短篇编排，从构想、人物与大纲到单次全文成稿。用户明确要求短篇、微型小说或选择短篇专线时触发；剧本由 screenplay-writing、衍生与连载由 MUSE-serial-writing、其他完整原创小说由 story-writing 承接。
---

# 原创短篇创作

四阶段围绕一篇完整正文工作。人物与情境在同一大纲中成型，由 short-composer 一次完成全文，保留篇幅集中、场景详略可变及整体叙述组织的空间。

| 阶段 | 技能 | 工作目录下的产物 |
|---|---|---|
| 0 构想 | `short-phase0-conception` | `pipeline/shortform/conception.yaml` |
| 1 人物 | `short-phase1-character` | `pipeline/shortform/characters.yaml` |
| 2 大纲 | `short-phase2-outline` | `pipeline/shortform/outline.yaml`，按需引用 ledger |
| 作者裁决 | 本入口 | `pipeline/run_state.yaml` 的 `outline_gate` |
| 3 成稿与修订 | `short-phase3-composition` | `story.md`，既有全文审阅报告 |

## 初始化与恢复

本包 `scripts/init_short_run.py` 创建短链骨架：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_short_run.py --results-dir results/ --query "<本次需求>"
# 已指定工作目录时：
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_short_run.py --run-dir <work_dir>
```

恢复已有任务先核对现有设计、正文和作者决定，从尚未完成或需要修正的阶段继续。新需求使用独立 run；复用目录不等于旧产物、参考或批准适用于新设计。

按宿主可用方式加载当前阶段技能；文件加载时定位本包相应 `skills/{name}/SKILL.md`。全篇设计由主会话协调，正文与修订按 Phase 3 派发。每次明确工作目录、技能入口、任务和本次有效的可选输入；静态字段含义由消费者技能维护。

每份短链 YAML 生成或变化后，若宿主未自动运行所属 hook，执行 `scripts/validate_shortform_contract.py <yaml_path>`。人物 ID 或 ledger 变化后，还须对已存在的 outline 复核受影响引用。已有成功结果可在文件及依赖未变时复用。该脚本检查结构与引用，语义问题由阶段负责人判断。

篇幅、人物关系和多线结构明显超出本次整篇生成的承载能力时，说明具体影响，由作者选择是否转完整链。短篇允许群像、混合类型和多视角，标签本身不触发转链。

## 大纲裁决

Phase 2 完成后读取 `outline_gate`，缺省为 `pending`。作者已批准当前设计则为 `passed`；本任务已明确免审或直接写完则为 `waived`。其余情况提交可读的大纲与链接，等待通过、修改或中止。更新状态只改该字段，保留其他已有内容。

修改意见回到最早失真的构思、人物或事件，保留认可部分；来源理解不足时按[大纲构思与回读](../story-writing/references/outline-exploration.md)处理。批准后若实质改变作者选定方向或结果，回到同一裁决；局部完善沿用批准，免审沿用其授权范围。

批准或免审后进入 Phase 3。已有有效成稿需要修订时直接使用其审阅与修订路径，不重新首写正文。

## 交付

Phase 3 负责当前全文的审阅、修订与终验，本入口消费完成状态和需要上游解决的问题。最终正文为根目录 `story.md`；三份设计文件保持各自职责，不转换成逐场写作流水线。解释未完成项，审美取舍交作者。
