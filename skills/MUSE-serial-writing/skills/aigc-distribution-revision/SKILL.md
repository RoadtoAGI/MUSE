---
name: aigc-distribution-revision
description: 连载单场景的分布性表达修订。由 serial-distribution-reviser 在章稿装配前消费当前 machine_directive；装配后的章稿表达修订用 aigc-wholetext-revision。
---

# 场景表达修订

只处理本次明确交付的重复、失焦或表达失真。统计频数是线索；需要消除的是正文中的问题机制，同时保持人物知识、事件因果、必要结果与声音。

## 输入与权限

读取当前 `pipeline/scenes/scene_{scene_id}.md` 与 `pipeline/review/{scene_id}.machine_directive.yaml`。`dispatch_ready` 必须为 true；输入缺失、过期或指向别场时停止并报告。新统计报告只记录观察；已有 directive 的待修项需要结合当前正文确认，不能把历史 severity 当作修改授权。

按需读取本场 scene card、serial_context 与相关 role_view，核对待修内容的事实、人物时点及必要结果。角色来源遵循[上下文协议](../serial-chapter-writing/references/context-contract.md)。通过宿主技能调用或文件读取加载本包 [prose-craft](../prose-craft/SKILL.md) 中相关判据；已经取得且仍适用的内容直接使用。

## 修改

- 对当前 pending 项先定位它实际造成的问题，再合并重复句群、调整信息次序或表达方式。词语、family 或密度的改变不等于问题消除；保留有具体作用的相邻合法表达。
- 可以调整段落、句序和措辞，保持场景必要结果、人物动机与所知、空间和物件事实。解决问题需要新增或改变事实时，交回对应负责人。
- `protected_regions[].preserve` 的已接受语义继续成立。保护范围内的措辞可以协调，不能恢复已修问题；简要交代每个实际受影响保护区。空保护区不要求额外说明。
- 待修目标不成立、依据缺失或与保护内容冲突时，说明具体原因与需裁决的内容；不为降频删去必要信息。

仅写本场正文与 `pipeline/scene_{scene_id}/distribution_summary.md`，不修改 directive、其他场景或已装配 draft。summary 顶部使用 `**status**: complete | partial | failed`；按实际 pending 项说明改动或未完成原因，并保留保护区的 patch_id 与处置。没有 pending 项时返回 complete，说明无待修项即可。

完成后读受影响段落确认语义和衔接，回复：

```text
done distribution for scene {scene_id}; status={complete|partial|failed} ({n} entries)
```

complete 表示本次问题已处置，partial 表示仍有明确未完成项，failed 表示输入或执行阻塞。调用方复用现有审阅判断修复效果；机器 gate 只检查执行状态、接口及可确定的保护条件。恢复执行使用本次有效 directive，不沿旧 summary 重复修文。
