---
name: short-phase3-composition
description: 原创短篇的成稿与修订编排，在大纲批准或免审后派发一次全文创作，组织已有检查与全文审修，交付 story.md。
---

# 短篇成稿与全文修订

取得当前有效的 conception、characters、outline 与大纲批准。正文由 short-composer 生成，修订由 short-manuscript-reviser 完成；主控读取设计、诊断和状态组织工作。

## 来源与首次成稿

设计所需的世界规则在构思与大纲阶段已经确认。成稿前按实际文风、场景表达或作者指定用途加载 `scene-reference`；已有适用材料可直接复用。手选来源按作品和领域限定，命中 `world_rule` 时读取同作 lore，纯文风用途不升级为情节或世界规则复用。来源不足时说明实际缺口，不自行替换作者选定机制。

conception 含 `canon_reference_profile` 时，把 `pipeline/shortform/conception.yaml` 的绝对路径交 scene-reference，由其用 `--canon-reference-profile` 按作品解析用途与领域；全局 `--reuse-mode / --intended-domains` 只作所有来源共有的限制。采用语义沿本包[参考采用契约](../writer/references/reference-adoption.md)。

采用的正文参考放在既有 `pipeline/shortform/reference_pack.md`，各来源的 `<reference_scope>`、使用约定和适用原文一起保留，总头不能扩大单条来源的范围。本次派发明确有效路径或“无”；只有本次成功取得，或已确认来源范围、用途仍适用的材料才生效。关闭参考、无匹配或失败时不给旧文件输入权。

通过宿主可用方式派发 short-composer，明确工作目录、本包技能入口和有效 ref。宿主未预载 agent 时，主控读取本包对应 `agents/{agent-name}.md`，将正文交给子执行者或要求其先读取该绝对路径；后续审阅和修订派发沿用此要求。composer 一次写完整篇 `story.md`；已有有效正文的恢复任务直接进入当前审阅或修订步骤。参考机制的独立 ID 仍只读当前 outline 实际引用的 adopted 条目。

派发 short-story-review 或修订者时同样传本次有效 ref，reader 模式明确当前报告路径；未启用的可选输入传“无”。

正文、审阅与修订的子执行者默认继承主会话所选模型，注册 agent 与通用子执行者同样适用；仅按作者明确的任务指定覆盖。实际调用方落实该选择，宿主限制使其不可用时报告受影响任务。

## 检查与修订

正文落盘后运行现有全文检查；同一正文已有成功报告时复用，内容变化才刷新：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ai_filler_lint.py --story {work_dir}/story.md --work-dir {work_dir}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lexical_stats.py --story {work_dir}/story.md --work-dir {work_dir}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dialogue_lint.py --story {work_dir}/story.md --work-dir {work_dir}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wholetext_gate.py --story {work_dir}/story.md --work-dir {work_dir}
```

前三份报告提供定位信号。wholetext_gate exit 2 为工具或输入错误，停止自动修订并报告；exit 1 进入既有 `de-AI` 修订，读取 `revision_summary.md` 的处理结果，再对改变后的正文检查；exit 0（PASS 或 REVIEW）进入全文审阅；REVIEW 的定位线索交 short-story-review 结合正文判断。de-AI 自动修订最多两轮，保留现有限制，不为通过数值无限重试。

派发 short-story-review，传工作目录、本轮 N、有效 ref 和本次有效 reader 报告路径（无则明示“无”）。N 从已有报告最大轮次之后递增，避免恢复任务被更高编号的旧报告覆盖。审阅规则和 schema 归该技能：

- `PASS`：进入条件性读者反馈与终验。
- `REVISE`：派发 short-manuscript-reviser 的 `reader` 模式，明确当前报告路径与有效参考；按问题位置修订，再刷新改变正文的检查并复审。
- 修订 `failed`：停止并报告缺失输入或执行失败。`partial` 若需改变人物或大纲，回到相应设计；其余未决项交同一复审，不重复改写相同措辞。

reader 修订与复审最多三轮。用户要求读者视角或当前问题需要盲读判断时，调用既有 reader-review，仅传当前 `story.md` 和输出路径，报告 `input_snapshot: story.md`；其当前报告交 short-story-review 判断是否构成问题，沿同一路径处理，不增加并行裁决层。单纯审美偏好交作者。

## 终验与交付

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_shortform_review_complete.py --work-dir {work_dir}
```

终验检查当前正文、当前审阅、硬要求覆盖及既有机器资格。报告对应旧正文时更新受影响检查；输入错误修输入，实际未解决问题回其负责环节。复查仍受原轮数限制。

自动修订达到上限、工具失败或需要作者裁决时，沿用 `pipeline/shortform/review/quality_gate_failed.yaml`，记录 `reason`、`rounds: {de_ai, reader}` 和具体 `unresolved`，保留现有正文并报告待处理项。终验通过后交付 `story.md`。
