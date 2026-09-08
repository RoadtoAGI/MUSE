---
name: phase7-integration
description: 完整原创链的全文整合、独立读者与语义审阅、有界修订及交付。由 story-writing 在 Phase 6 场景闭合后调用，恢复时继续当前整合稿。
---

# 全文整合与修订

## 控制与恢复

```text
[Phase 6 闭合] -> [首次装配 / 恢复当前 story.md]
                             |
                         [wholetext]
                合同 FAIL：de-AI 修订，最多两轮
                             |
              [冻结稿 -> reader 盲读 + A 全稿初审]
                             |
                      [本次有效反馈]
                +------------+------------+
                |                         |
           无待处理反馈             合并处置一次（可不改文）
                |                         |
                |                [wholetext + A 当前稿复审]
                +------------+------------+
                             |
                   [finalize -> validate -> 交付]
```

恢复时读取已有正文、审阅、修订与发布状态，从未完成或失效的步骤继续；不默认重装配或清零轮次。已经修订的 `story.md` 是全文阶段的正文权威。场景源或设计改变时先确定如何把变化并入当前稿；确需重装配时保留旧整合稿后再执行，避免丢失全文修订。

控制、作者要求与设计依据由主控协调；正文阅读交相应执行者。只有本次有效、对应实际输入的结果可以复用。输入错误或格式错误允许补正，不借此增加创作重试轮数。

## 1. 场景闭合与初始整合

沿 [Phase 6 协议](../phase6-scene-development/references/execution-protocol.md) 确认人工裁决、patch 应用和机器通道已闭合。`verify_review_complete.py` 负责实际 admission；宿主未触发 hook 时显式执行：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_review_complete.py {work_dir}
```

缺失时回到对应场景补齐 story-review、scene-review 与修订。用户明确允许的人工 skip 沿现有 `skip_review.yaml` 白名单处理；它关闭发布资格，不能跳过机器通道。相同 admission 的重复检查保留已有终态，输入改变仍使终态失效。

没有整合稿时运行：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/assemble_story.py {work_dir}
```

脚本按 `phase6_development.yaml` 列表读取完整场景并装配，不按 ID 或事件时间排序；缺场停止。已有同内容稿可复用，不同内容稿保留并报告。非线性、切视角与开放结构按因果、知识和阅读关系判断。

## 2. 当前正文的机器检查

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wholetext_gate.py --story {work_dir}/story.md --lang auto --work-dir {work_dir}
```

exit 0（PASS 或 REVIEW）进入全文审阅，并把当前报告的定位线索交 A；REVIEW 只表示有待语义判断的候选。exit 1 派发 `manuscript-reviser` 的 `de-AI` 模式，明确本次 wholetext 报告；exit 2 修复输入/工具问题。de-AI 自动改文最多两轮，恢复沿实际已有轮次继续；必要内容与机器要求无法兼容或达到上限后停止并报告。

每次修订使用第 4 节的既有快照和保护审计。只对改变后的稿件刷新失效结果，不把旧报告存在视为本次已检查。

## 3. 独立阅读与反馈选择

在 reader 和 A 审阅前，将当前稿冻结到既有快照：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/revision_quality.py snapshot --source {work_dir}/story.md --out {work_dir}/pipeline/review/snapshots/story.semantic.round1.md
```

已有该轮快照与报告时先核对任务及输入；复用有效结果，不覆盖受审快照来让旧报告显得有效。

- 新独立执行者加载本包 `reader-review`，仅取得此快照与报告路径，写 `pipeline/review/reader_review.yaml`。明确无需本次盲读或已有有效读者反馈时，可沿既有 `reader_review_skip.yaml` 记录具体依据；省略步骤须有当前任务依据。
- fresh dispatch `story-review`，传 `group=A scope=manuscript review_round=1`、本包入口和 work_dir。它读取同一快照并独立写 A 全稿报告，不读取 reader 报告。

实际执行盲读时移除旧 skip 标记；选择 skip 时移开未采用的旧 reader 报告，保持分支明确。缺输入、未读完或报告无效时补正该次任务。选择本次有效的全稿 A 报告聚合：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate_global_findings.py --work-dir {work_dir} --source A-manuscript
```

Phase 6 的全局问题应在原责任方处理；只有明确仍适用于当前稿的来源才追加 `--source A|B|C`。聚合器不自动扫描旧报告；选中来源缺失、损坏或全稿来源过期时停止，不生成“无问题”的假结果。

reader 观察需在当前正文核实；合法表达与审美偏好可保留。所有反馈在本次合并修订中处理，既有旧 lint 与局部报告不会另行扩大待修范围。

## 4. 一次合并修订与当前稿复审

有本次反馈时派发 `manuscript-reviser reader`，明确当前 reader 报告路径或“无”、global_findings、work_dir。修订者按问题读取作者要求、相关世界/人物依据、因果、来源与保护条件；内容缺口回上游，局部问题原位修复。处置可包含有依据的保留，无需为每条感受改文。A finding 若源于输入或分类错误，回原审阅负责人补正同轮报告；纯审美取舍交作者。reviser 的 complete 不会解除尚成立的 A finding。

每次修订前后由主控执行，`{mode}` 为 `de-ai|reader`，`{N}` 为本模式的实际轮次：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/revision_quality.py snapshot --source {work_dir}/story.md --out {work_dir}/pipeline/review/snapshots/story.{mode}.round{N}.pre.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/revision_quality.py audit --before-text {work_dir}/pipeline/review/snapshots/story.{mode}.round{N}.pre.md --after-text {work_dir}/story.md --lane manuscript --work-dir {work_dir} --lang auto --out {work_dir}/pipeline/review/manuscript_quality.{mode}.round{N}.yaml
```

reader 模式且本次使用 reader 报告时，audit 追加 `--reader-report {work_dir}/pipeline/review/reader_review.yaml`，将该报告与修订前后稿绑定。保护失败停止；`retention` 等观察不自动升级为内容错误。revision_summary 的 failed 表示执行失败，partial 保留未决项，complete 表示本次处置完成。

正文改变后刷新 wholetext，并冻结到 `story.semantic.round2.md`，fresh dispatch `story-review group=A scope=manuscript review_round=2`。无改文时沿用仍有效的 round 1。reader 合并修订仅一轮，A 全稿语义审阅最多两轮；后续仍有实际问题或输入无法闭合时停止自动改写，返回具体问题及负责人。

## 5. 终态与交付

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/release_eligibility.py finalize --work-dir {work_dir} --lang auto
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/release_eligibility.py validate --work-dir {work_dir}
```

finalize 现场检查当前正文及其 admission、机器、语义和读者结果；validate 确认消费时仍有效。`released` 且 validate exit 0 才交付 `story.md`；`completed_not_releasable` 保留内部产物；`quality_failed / escalated` 返回具体未决原因。修订 complete、报告空列表或文件齐全均不能单独代替这些状态。

产物职责见 [输出契约](references/output-schema.md)。
