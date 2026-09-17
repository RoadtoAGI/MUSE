---
name: patch-revision
description: 连载单场景的定点修订。由 serial-reviser 消费当前 patch_directive，在授权片段内改文并返回 revision_summary；整场重写由 writer 负责。
---

# 场景定点修订

读当前 `pipeline/scenes/scene_{scene_id}.md` 与 `pipeline/scene_{scene_id}/patch_directive.yaml`。调用方提供章目录与 scene_id，并完成本次补丁定位校验。按[补丁格式](../scene-review/references/output-schema.md)执行；不以历史 revision_summary 重新立案。

## 范围与上下文

先确认每条 patch 的当前原文、问题、方向和保留项，再在授权片段内修改。涉及场景结果、知识、声音或承载作用时读 scene_card 与对应 role_views；依[上下文协议](../serial-chapter-writing/references/context-contract.md)区分必要事实与候选实现。资料不足或指令冲突时回报来源和负责人，不用补写猜测解决。

同一句的事实、知情、动机、关系与对象状态不得被无意改变。涉及表达删改时，先取得本包 [prose-craft](../prose-craft/SKILL.md) 主文件；改动对白内容、话轮或声音时取得 [dialogue-craft](../dialogue-craft/SKILL.md)，参考按问题补读，已有有效上下文可复用。删除冗余、重写说明、补足指代或反应均可使用，保留文本需要的承接、声音、过程和节奏。不为了去掉一种句式而补手势、物件或相同功能的另一模板。

只改明确授权范围。无法定位、方向互斥或需要改变未获授权的事实时，该条 `not_applied` 并说明原因；其余独立合法条目继续。需要整场重写时记录 `should_be_rollback` 及实际原因；patch_kind 名称本身不强制改变修订档位。方向标签见 [registry](references/patch-kind-registry.md)。

## 执行与交接

修改前保留本次原文供对照；按原阅读顺序核对问题机制是否改善、保留项及相邻衔接是否成立。删改新增理解跳步或含混指代时，恢复有用部分并重组；修复超出 patch 范围时交回调用方调整方向。未授权片段保持原样，不统一改造全场文风。正文保持纯作品文本，说明写入 `pipeline/scene_{scene_id}/revision_summary.md`。

```markdown
# Revision Summary: S01

**status**: complete
**patch directive source**: scene_review
**patches applied**: 1 / 1

**[patch_01 · issue_id A-S01-repeat · applied]** 场景中段
- old_span: 他又一次说明了自己为何不能离开。
- new_span: （删除）
- reason: 前句已交代同一限制；后句仍能直接承接，删除不损失人物语气与节奏。
- preserve: 不能离开的事实、回指关系与后续行动缘由继续成立。
- contract_conflict: {observed: false, note: null}
```

| status | 结果与下一步 |
|---|---|
| complete | 全部补丁已应用，回调用方用 mark_patch_applied.py 将 pending 改名 applied |
| partial | 已安全应用部分；summary 记录全部结果，directive 仅留下 not_applied，调用方处理未完项 |
| failed | 零补丁应用且没有落盘正文改动；保留指令，说明输入、范围或执行阻塞 |

发生部分改动时不能用 failed 隐藏。保留 issue_id、实际 old/new span 与所需保留功能；机器关联字段存在时透传，不为了完整填空表。回复回显 summary 的 status。原问题的语义复审由现有 post-review 完成，不能将 complete 当作作品通过；事实或上下文变化交调用方刷新真正受影响的后续输入。
