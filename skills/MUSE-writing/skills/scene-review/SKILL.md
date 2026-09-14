---
name: scene-review
description: 裁决原创完整链的当前场景，结合正文、有效诊断与设计作四档判定；由 scene-reviewer 调用，局部问题交补丁修订，设计问题交原阶段。
---

# 场景裁决与修订交接

## 输入与模式

接收 work_dir、scene_id、本轮实际审阅来源及模式。读取 `pipeline/scenes/scene_{id}.md`、`pipeline/scene_{id}/scene_card.md`、当前 A findings 和本场三份 L1 报告；B/C 仅消费本次实际调用的有效结果，未调用则明确“无”。来源缺失、损坏或版本失效由主控 input_gate 处理；不把旧文件存在视为本轮成功。

初审写 `pipeline/review/scene_{id}.yaml`；post-revision / post-rewrite 写 `scene_{id}.post_revision.yaml`，并先读[复审协议](references/post-revision-review.md)。当前模式已有有效结果时由主控复用；当前输入/正文改变且主控明确本次重审与替换权限时，读取旧结果作为问题依据并刷新该模式报告。未经本次授权不覆盖，返回 `ESCALATED(already_reviewed)`。

主控处理输入失败、派发失败与回复冲突。reviewer 正常输出 PASS / PATCH / ROLLBACK / REWRITE；ESCALATED 是运行失败状态。回复必须回显文件中的 verdict。

## 核实问题与决定范围

findings、lint 与设计提示用于定位。将问题计入裁决前，引用当前正文并说明具体损害：事实或知识冲突、必要因果丢失、声线失真，或已可说明的阅读障碍。统计频率、标签、候选动作未采用以及审美偏好各有用途，不能单独决定修改。

按疑点补读相关人物、世界、场景或作者要求；采用的必要结果保留，实现候选允许 writer 替换。正文中的长句、独白、直陈、冷叙述、重复或留白可有作用，缺少预声明不取消其合法性。相关表达判据在本包 prose-craft / dialogue-craft；宿主 skill 入口或实际安装文件均可加载。

| verdict | 判断与交接 |
|---|---|
| PASS | 本场无须处理的已确认问题，允许合法表达和作者审美选择 |
| PATCH | 问题与修改范围可定位，局部调整能够解决并保持其余约束 |
| ROLLBACK | 当前设计成立，成品的整体因果、人物或组织需要 writer 重写本场 |
| REWRITE | 问题来自人物、脊椎、结构或场景输入，指明 Phase 2–5 的责任位置 |

severity 是输入线索，判档取决于实际问题和范围。OOC、carrier_missing 或信息过载等名字不自动决定回滚；可以局部修正的知识用词与贯穿全场的错误人物动机应分别处理。scene_id=null 的全局 finding 交主控汇总，不猜测归属到本场。

## 机器信号与语义反馈

observe 命中由现有 A 审阅及本裁决按实际作用判断，确认问题后走同一 PATCH 路径。当前 ai_policy 仍将两条有作者裁决的 density_contract 交机器通道执行；其保护、预算与未决状态按当前报告处理，不以语义 PASS 解除合同冲突。

本轮不为普通统计线索生成 machine_objection；该文件仅兼容旧应用。machine ledger 由脚本维护，reviewer 只读本次有效状态。dialogue/lexical 或参考分布差异同样只提供候选；需要修订时给正文证据与具体方向。

prose_risk_contract 说明上游担心的机制。相同 family 的形态仍出现时先核实问题是否继续存在；合同自身误判或漏供输入回到其生产者。避免把相同病灶重复列成 lint、A 与 contract 三份 patch。

## 输出与冲突处理

所有正常裁决写当前 verdict_path：

```yaml
scene_id: S02
verdict: PATCH
review_incomplete: false
missing_inputs: []
written_by: scene-reviewer
rationale: 引用实际问题并解释范围
findings_summary:
  total: 1
  by_source: {lint: 0, A: 1, B: 0, C: 0}
  by_severity: {blocker: 0, major: 1, minor: 0}
key_findings:
  - source: A
    dimension: pov_boundary
    location: L12
    severity: major
```

PATCH 另写 `pipeline/scene_{id}/patch_directive.yaml`：

```yaml
source: scene_review
scene_id: S02
application_id: S02-scene-review-round1
patches:
  - patch_id: patch_01
    issue_id: A-01
    patch_kind: rewrite_sentence
    location: {line_range: [12, 12]}
    anchor_quote: 当前原文
    issue: 此处把人物未获的消息写成其自知
    suggested_action: 保留可见事实，修正知情归属
    rewrite_directive:
      semantic_function: 保留人物据现有信息作出的判断
      preserve: 当前事实与尚未告知的关系
      remove_patterns: [无来源自知]
      target_style: 延续本场叙述声音
```

rewrite_span 使用 old_span、anchor_quote_start/end 和 line_range。锚须精确、唯一定位，重复文本用行范围消歧；短句无需扩写到固定字符数。字段见[输出与保护声明](references/output-schema.md)，问题机制、既有类型与操作范围见[修订类型与操作](../revision/references/patch-kind-registry.md)，追溯见[定位协议](references/traceability-protocol.md)。

合并同一位置、相同语义问题的重复诊断；同一机制涉及不同位置时，可共用问题解释，各处需要独立修改与核验的范围仍保留各自 patch_id、锚点与保护条件。相邻问题相关但不同则保留职责；同位置指令冲突时先决定正确语义，输出一项相容修订，不把互相覆盖的指令顺序下发。分散 patch 仍无法保持整体逻辑时交 writer 重写；局部修订可增、删、重组，方向由问题决定。

保留当前应用身份、已授权原文及关系保护。用户已接受或 next_round_only 的问题不重新激活。只有本次 pending patches 进入施工，已应用历史由主控保存；复审检查受影响的实际功能和必要关系。reviewer 只写判定、指令与既有复审记录，不改正文或上游设计。
