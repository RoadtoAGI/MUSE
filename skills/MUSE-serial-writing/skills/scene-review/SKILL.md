---
name: scene-review
description: 连载单场景的审阅裁决。根据当前正文与有效诊断输出 PASS、PATCH、ROLLBACK 或 REWRITE；局部修订同时交付可追溯补丁。
---

# 场景裁决

本技能只裁决当前场景并交接修订，不改正文、场景设计或机器台账。调用方提供作品根、章目录、scene_id、首次/post-revision/post-rewrite 形态及当前报告范围。本包职责按宿主包限定入口或明确文件位置加载。

## 当前输入

必读 `pipeline/scenes/scene_{scene_id}.md`、`pipeline/scene_{scene_id}/scene_card.md`、本轮 `pipeline/review/A_aesthetic.yaml` 和该场明确的 ai_filler、lexical_stats、dialogue lint 文件。B/C 只消费调用方确认仍有效且命中本场的条目；`scene_id: null` 留给调用方。density_vs_ref 等可选统计只在本次实际生成时读。

人物问题按需读所涉角色的 role_views；来源采用问题读当前已绑定 INS 条目。依据[上下文协议](../serial-chapter-writing/references/context-contract.md)区分事实、人物知情、必要结果和候选实现。参考或角色动作未选用不自动构成错误。

调用方按现有 input gate 确认输入齐备。缺失或冲突时回报具体文件和负责人，不以缺资料判 OOC，不给互相冲突的 patch。调用方写既有 ESCALATED 输入降级产物；本技能的主体 verdict 只用四档。

## 裁决

| verdict | 判据与交接 |
|---|---|
| PASS | 无尚成立的硬性不符或已确认需修的问题；必要处境、因果与结果成立。单纯偏好作为作者意见，不强迫修改 |
| PATCH | 问题及方向可确定，能在明确片段内解决并保留有效事实、人物与场景作用；可删、改或补 |
| ROLLBACK | 输入成立，但正文整体实现需要重写，局部修订不足以恢复必要关系；交当前 writer |
| REWRITE | 根因在场景设计、人物来源、世界或系列约束；说明实际来源，交 chapter-scene-plan 或 serial-outline 路由 |

严重度用于提示影响，类别名不决定 verdict。人物 OOC、carrier 缺失或价值方向问题也应先辨认根因和范围；单个字词错误不因此强制整场重写。稳定价值、过渡段、直接抒情或议论结尾可以成立，不靠动作、感官或转折配额判场景。

lint 命中是定位信号；确认对应片段确有语义病灶后才能进入 PATCH。prose_risk_contract 同样按其实际风险与作者约束判断，命中词汇或替换了候选方法不等于违约。A/B/C、lint 和 contract 发现同一问题时归并证据。

机器通道使用已有 directive/ledger。新统计不会单独形成正文修订义务；既有 pending 仍按当前正文确认并处理，不因重新生成报告而丢弃。历史 machine_objection 只能作为其当时的理由与证据，不能替代本次语义判断。

## 补丁与产物

首次目标为 `pipeline/review/scene_{scene_id}.yaml`；复审目标为 `.post_revision.yaml`。若本次目标已存在且调用方未明确处理其当前性，返回 `ESCALATED(already_reviewed)`，不覆盖。调用方先恢复、清理失效复审或移走 input_gate 降级目标，再派当前任务；首次 verdict 保留。

```yaml
scene_id: S01
verdict: PATCH
review_incomplete: false
missing_inputs: []
written_by: scene-reviewer
rationale: 指明当前问题及其可局部修复的依据。
findings_summary:
  total: 1
  by_source: {A: 1}
  by_severity: {blocker: 0, major: 1, minor: 0}
key_findings:
  - source: A
    dimension: on_the_nose
    location: 场景中段
    severity: major
```

PATCH 另写 `pipeline/scene_{scene_id}/patch_directive.yaml`，先读[补丁 schema](references/output-schema.md)。原文锚点必须命中当前正文并能唯一确定位置；受作者保留/延期决定保护的 finding 不进入补丁。具体校验沿[可追溯协议](references/traceability-protocol.md)。

同位置同问题归并成一个补丁；方向冲突先核事实与权限，不能先删后加两条抵消指令。跨位置的同机制问题可以合并到实际连续片段；若解决范围已涉及全场因果，按表返回 ROLLBACK/REWRITE。补丁类型仅指修订方式，方向见 [registry](../patch-revision/references/patch-kind-registry.md)。

完成回复回显当前目标文件的 verdict。PATCH 必须同时有 directive；回执与文件不一致或缺产物由调用方恢复。进入修后评审时加载[复审协议](references/post-revision-review.md)，检查原问题机制及新引入的硬错，不能把机器通过或新空报告代写为语义 PASS。
