---
name: story-review
description: 诊断原创完整链的叙事与一致性问题；Phase 6 按组审查场景，Phase 7 对冻结全文作语义审阅，供裁决、修订与终验使用。
---

# 审稿模块（Pass 1: 技术诊断 + 一致性审查）

## 执行总览

```text
场景与设计产物
  -> A 审美组（必跑）
  -> 评估 adaptive 信号
       |-- 长篇 / 复杂关系 / 已有风险 -> 加跑 B 叙事一致性
       |-- 复杂世界 / 多时间线 / 交叉风险 -> 加跑 C 结构一致性
       `-- 无相应信号 -> 不派发该组
  -> 若 C 执行且存在 ledger / inspiration refs
       -> 同步检查 INS-* 引用闭合
  -> 汇总各组独立报告
  -> scene-review 按 scene_id 消费并作四档判定

装配后的冻结全文
  -> A 审美组（scope=manuscript）
  -> 全文语义 finding 进入 global_findings
  -> 如有 finding，与 reader finding 合并做一次全文修订
  -> 正文变化后再做一轮 A 全稿复审
```

组别选择由 run 的风险信号决定；A、B、C 的检查维度继续由各自 reference 定义。

## 核心原则

> 「一旦通过适当的方式来研究一个场景，其瑕疵便会一目了然。」
> —— 《故事》第十一章

审稿走 adaptive dispatch，**不默认三组全开**——A 是场景级技术诊断的主用组、B/C 是长篇 / 复杂世界一致性审计，按需触发。**orchestrator 不读取 `references/` 下的审查指南文件**——每组 subagent 根据自己的指南自行定位并读取所需文件。

> **全文双视角**：reader-review 只报告读者体验；A manuscript scope 负责可归因的 AI 叙事形态。二者读取同一版终稿并保持独立，finding 在全文修订入口合并。

## Phase 7 manuscript scope

Phase 7 当前 wholetext 完成（PASS / REVIEW）且无有效阻断项后，统计候选进入本次全稿语义审阅；orchestrator 先用 `revision_quality.py snapshot` 冻结当前 `story.md`，再 fresh dispatch `story-review`：

```text
group=A scope=manuscript review_round=1
```

若 A 或 reader 产生 finding，现有 manuscript-reviser 做一次合并修订；正文变化后重跑 wholetext，再冻结新稿并 dispatch `review_round=2`。第二轮只验证当前稿，不能读取初审报告或修订总结；仍有 finding 时停止自动修订。路径与报告附加字段见 A 指南和 output schema。

## Dispatch 表 + adaptive 触发

| 组别 | Subagent 读取的审查指南 | 审查粒度 | adaptive 触发条件 |
|------|------------------------|----------|------------------|
| **A 审美组** | `references/A_aesthetic.md` | 场景级 | **默认必跑** |
| **B 叙事一致性** | `references/B_narrative_consistency.md` | 全文级 | 满足任一即跑：长篇（多 arc / 场景数足以发生跨场景矛盾）/ 复杂角色关系（多角色高频互动）/ design-validation 已发现风险 / reader-review 报告理解断裂 / 用户明确要求 |
| **C 结构一致性** | `references/C_structural_consistency.md` | 全文级 + 设计文档级 | 满足任一即跑：复杂世界规则 / 多时间线 / pipeline_crosscheck 风险 / design-validation 已发现风险 / 用户明确要求 |

**判据是信号，不是数字门槛**——orchestrator 现场判断本 run 是否触发 B/C；判定无明显信号时按短篇默认（仅 A）。

每组 subagent 的审查指南中已包含：输入契约（读哪些文件）、审查维度、输出格式。orchestrator 无需了解具体审查内容。

## 审阅者共同原则与 INS-* 闭环

三组共同的审阅原则（只列问题、区分文学手法与错误、引用足够语境、以读者仅凭正文能否取得所需信息为基准）由 [`agents/story-review.md`](../../agents/story-review.md) 随派发交给审阅者；INS-* carrier 闭环检测归 C 组指南 [`references/C_structural_consistency.md`](references/C_structural_consistency.md) §3 F，发现归入 `pipeline_crosscheck`。本文件只维护组别选择、Phase 7 scope 与派发关系。
