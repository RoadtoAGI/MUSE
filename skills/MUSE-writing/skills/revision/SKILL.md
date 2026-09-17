---
name: revision
description: 按本次 patch_directive 定点修订原创完整链的场景，保留事实、人物与保护内容；由 reviser 调用，返回应用结果供主控复审。
---

# 场景定点修订

## 当前输入与边界

读取 `pipeline/scenes/scene_{scene_id}.md`、`pipeline/scene_{scene_id}/patch_directive.yaml` 与其指定的保护约束。按疑点补读本场 scene_card、本人 role_view、作者要求或实际来源；输入用于理解修复目标，不扩大修改范围。使用宿主技能入口或实际安装位置加载本技能及[patch 类型](references/patch-kind-registry.md)。

必需文件缺失、指令无法定位或需要改动设计时返回具体原因。只处理本次 pending patches，历史 summary 由主控用于恢复；同名旧反馈不另行激活。

## 修订动作

句段语义重写前加载本包 [prose-craft](../prose-craft/SKILL.md)，改写对白的交流、声音或承接时加载 [dialogue-craft](../dialogue-craft/SKILL.md)。已有且仍适用的内容直接复用，深度 reference 按问题取得；机械改错或未改正文时按当前指令处理。

先用实际正文核实 issue，再按 suggested_action 和 rewrite_directive.preserve 处理。保留当前指令的 patch_kind，机制类名称提供问题线索，具体改动由指令语义、锚点与保护条件确定。单句或一段重写以获准 anchor 为界，范围由问题影响决定；情绪直陈、自省、沉默、物件或长句均按功能判断。只换同义词却保留原有重复/解释结构时继续修该处，不强制把它改为动作。

保留事实、人物动机、必要结果、声音与知识边界。低强度承载可在 preserve 内调整；改变因果、关系结论或物件状态须有明确授权。active relation 的冻结 span 不在本 lane 重新判定；冲突返回主控。

交接前按 [prose-craft 的可读性与承接判据](../prose-craft/SKILL.md#组织场景与段落)对照修订前后，连读改动句段与相关上下文；修订所需上下文超过获准 anchor 时返回具体扩展范围。

带 cluster_id 的 patch 使用指令允许的 patch_kind，结合实际语义问题修复；命中数量不能证明某种承载一定有害。接到 ROLLBACK 类或越出授权范围时记 `not_applied` 和 `reason: should_be_rollback`，交场景裁决者；同批其余合法项继续。

## 身份与结果

保留每项 patch_id、可选 issue_id 和当前 application_id。anchor_quote 或 rewrite_span 的 old_span/首尾锚须精确定位当前原文；定位已失效时由生产者补正，不能凭模糊相似扩大施工。

正文就地编辑，写 `pipeline/scene_{scene_id}/revision_summary.md`。沿现有可解析格式：

```markdown
# Revision Summary: S02
**status**: partial
**patch directive source**: scene_review
**patches applied**: 1 / 2

1. **[patch_01 · applied · patch_kind=rewrite_sentence]**
   - old_span：实际原文
   - new_span：实际修订
   - preserve: 指令要求保留的事实与功能
   - 改动：消除已确认重复并保留认识变化
2. **[patch_02 · not_applied]**
   - 原因：当前锚点失效，回场景裁决者补正
```

new_span 使用当前正文中可唯一定位的实际文字。summary 保留本轮全部应用与未应用项；指令包含 consumed_patterns、preserved_function、added_carriers、contract_conflict 等复审所需信息时如实记录，不为填表添加承载。顶部 status 为权威，回复同值。

| status | 处理与交接 |
|---|---|
| complete | 全部应用；主控 mark_patch_applied、刷新尾摘并复审 |
| partial | 部分应用（包括中途失败但已有成功修改）；一次更新 pending directive，只留未应用项并换成未使用过的 application_id，summary 保留本轮完整记录 |
| failed | 零应用；保持正文，报告原因，主控回对应负责人 |

同一 dispatch 重试沿用 application_id；裁剪为下一轮 pending 时才换新值。已修部分仍有语义问题由既有复审回交；complete 只说明应用完成。正文不写批注，主控负责快照、脚本验证与轮次。
