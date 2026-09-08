---
name: story-review
description: MUSE 技术诊断与一致性审查。Phase 6 对场景运行 A/B/C；Phase 7 复用 A 组对冻结全文运行有界语义审查，产出 pipeline/review/ 报告供修订与终态消费。
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

Phase 7 wholetext 完成（PASS / REVIEW）且明确密度合同通过后，orchestrator 先用 `revision_quality.py snapshot` 冻结当前 `story.md`，再 fresh dispatch `story-review`：

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

## 注意事项（三组通用）

- 审稿的价值在于**定位问题**，不在于确认"通过"。不要列出通过项，只列出发现的问题。
- 如果某个维度没有发现问题，直接跳过，不要写"未发现问题"。
- 引用原文时保留足够上下文，让 orchestrator 无需回查场景文件即可理解问题。
- **只标记真实存在的矛盾**，不要捏造、推测或想象不存在的问题。没有问题就是没有问题。
- **区分文学手法和真正的错误**——不可靠叙述者、比喻表达、有意的风格对比都不是矛盾。当存在疑问时，倾向文学解读而非错误判定。
- 一致性维度（B/C 组）的发现应尽量提供 `contradiction_pair`，引用矛盾的两端让 orchestrator 快速定位。

## INS-* carrier 可见性 / inference path 检测

读取当前实际采用的 `status ∈ {accepted, bound}` 卡及其 `project_encoding`，核对来源 → 设计 → 正文的联系。未采用候选不形成正文义务。发现归入 C 组 `dimension=pipeline_crosscheck`，不新增审核层。

先确定本作实际采用的机制与不可变要求，再读对应正文。`field_path` 必须定位真实设计；正文需要实现该处承诺的作用，候选物件、动作或呈现方式可以替换。只有对象身份本身属于事实/来源合同，才检查同一对象。`disclosure_ladder` 缺省时不补阶段；存在时只核对实际声明的信息变化与延迟条件，不按 early/mid/final 凑次数。

`do_not_explain` 保留实际知识边界、受保护答案与作者明确的省略意图；心理叙述或直接说明仅在破坏这些条件、或重复既有意义而损伤阅读时报告。人物原型按实际采用领域判断，可体现于追求、关系、声音或轨迹，不要求另建 `recognition_path`。

| 兼容 subkind | 何时使用 |
|---|---|
| `inspiration_bound_but_no_visible_carrier` | 本作已采纳的必要作用未实现，且没有其他有效承载 |
| `carrier_visible_but_inference_gap` | 材料出现，但不足以支持已设计的信息变化 |
| `carrier_overexplained` | 解释实际破坏保留条件或造成无作用的意义复述 |
| `archetype_declared_but_no_recognition_path` | 本作已明确采用的人物机制在相关设计/正文中缺失；沿用既有 code |
| `inspiration_accepted_but_never_bound` | 只在作者明确要求采用且遗漏影响当前设计时使用；普通未采用卡不报告 |

严重度由具体后果和修复范围决定，引用来源要求与正文两端；不能由 code、缺候选物件或卡片数量自动定为 CRITICAL。

**输出 schema 落点**：字段约定见 [输出结构](references/output-schema.md)。`contradiction_pair` 必须标明 ledger 内 INS-* ID + 字段路径（如 `INS-001 disclosure_ladder[early_signal].carrier`），让 orchestrator 可一键定位 ledger 卡定位修复方向。

**字段缺席降级**：ledger 文件不存在 / 所有 INS-* status=candidate → 整段跳过，不报错。
