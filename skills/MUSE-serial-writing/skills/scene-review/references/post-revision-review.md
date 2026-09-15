# 修订后的语义复审

适用于 dispatch 明确要求 `post-revision` 或 `post-rewrite`。目标为 `pipeline/review/scene_{scene_id}.post_revision.yaml`；首次 `scene_{scene_id}.yaml` 保留。复审使用当前正文判断原问题是否解决，及修订是否造成理解跳步、声音损失或新的事实不符，仍由 scene-reviewer 给出四档 verdict。

## 输入与当前性

调用方先确认本次修订已经完成，并更新受影响的设计、角色切片及 A/B/C 证据。原问题从首次 verdict、其引用的 finding 及 PATCH 的实际应用记录取得；刷新后的报告用于判断当前状态，不能用其空列表代替原问题已经解决的证据。

- 读取当前场景正文、scene_card、问题涉及的角色视图与来源；PATCH 另读 `patch_directive.applied.yaml`、尚未应用的 directive（如有）和 `revision_summary.md`。
- 初始 lint 是 `pipeline/review/lint/{scene_id}.ai_filler.yaml`，修订后为 `.ai_filler.v2.yaml`。已有 local lint 只在其对应补丁确已应用且片段定位仍有效时使用；行号因改写漂移时回当前原文，不把其他片段的统计当成修复证据。
- 当前机器状态来自 `{scene_id}.machine_ledger.yaml` 与 machine_directive；这些文件属于机器通道，复审者不代写 resolved、豁免或脚本 PASS。

缺少必要输入时返回具体缺项与负责环节，不产语义 PASS。orchestrator 在当前复审目标写既有 `ESCALATED / review_incomplete / missing_inputs / written_by: orchestrator_input_gate` 降级结构，保留首次 verdict；补齐后移走该降级目标，再派本次复审。已过期的 post_revision 由调用方在派发前清理，旧文件存在不能作为本次成功依据。

## 判断与回交

按本包 [prose-craft 的阅读连续性判据](../../prose-craft/SKILL.md#组织场景与段落)对照可用的修前片段及上下文，核对原问题机制与修后指称、关系、解释顺序、声音和节奏；必要事实、人物知识与核心因果继续成立。原稿已有的断裂与修订新增损失分别定位，未解决旧问题不得记为改善。例如，把错误归因换成同义词仍是原问题；改变具体动作但保留合法的选择与结果可以完成修复。对修订引起的新矛盾按实际影响回到相应负责人，审美偏好继续由作者裁决。

| 当前结果 | verdict |
|---|---|
| 原语义问题已解决，修订未损害阅读连续性、声音及事实约束 | PASS |
| 仍有可定位且方向明确的正文问题 | PATCH，并按现有补丁协议交接 |
| 输入成立但场景整体实现仍失败 | ROLLBACK |
| 根因在场景设计、人物来源或系列约束 | REWRITE，指向实际设计负责人 |

修订范围由剩余问题决定；同义替换无效时回到造成问题的表达、因果或输入，不按补丁类型或固定轮数自动扩大整场重写。

## 两条通道的结果

`verdict` 判断叙事修订。机器残余、family 迁移与分布统计只提供线索，由现有机器通道继续处理；它们不强迫语义复审先写 PATCH 才允许 distribution。反过来，脚本通过也不能代替本次语义判断。

```yaml
scene_id: S01
review_stage: post_revision
review_round: post_revision_round1
verdict: PASS
rationale: 原错误归因已被删除；当前动作依据角色实际知情成立，必要结果保留。
```

有尚未执行的机器指令时可在 rationale 中指出，orchestrator 随后执行既有 distribution 路由。发布与装配仍同时要求语义复审完成、当前机器通道闭合。

既有报告中的 `targeted_span_gate`、`scene_residual_gate`、`pattern_migration_gate` 与 `ai_pattern_gate` 可作为其检查当时的记录读取。明确的语义失败或输入未齐继续阻断；旧 `machine_gate: fail` 在当前机器通道已经完成处理后不再阻断。仅有旧 lint_resolution_ledger 的工作区沿其已有机器结果契约判断，缺少当前凭据不能假定问题已解决。
