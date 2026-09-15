# 定点修订类型与操作

场景裁决者用问题机制说明损害与修复目标，用执行操作说明修改范围与定位方式；修订者结合当前正文落实指令。同一机制可用不同操作修复，同一操作也可处理不同机制，实际授权范围和保护条件共同决定选择。

## 问题机制与候选处理

以下机制名保留在既有 `patch_kinds` 中，现有指令继续使用原值。名称帮助定位问题，`direction` 提供有适用条件的处理方向；具体动作在当前指令的 `issue`、`suggested_action` 和适用的 `rewrite_directive` 中说明。原型名称不要求新作复制特定剧情。

```yaml
patch_kinds:
  carrier_then_explain:
    action: patch
    direction: 删合已确认冗余的解释，接续仍需表达的回指、因果与认识关系，保留声音和节奏
  omission_violated:
    action: patch
    direction: 恢复当前设计明确需要的信息保留范围，保留读者理解所需依据
  narrator_self_corrects:
    action: patch
    direction: 修复违背本作叙述权限的自我解释，有作用的自省或不可靠叙述保留
  emotion_naming_under_face_loss:
    action: patch
    direction: 修复遮蔽本场体验的重复情绪命名，直陈与间接表达依人物自知和语境选择
  care_tone_violence_dropped:
    action: patch
    direction: 本作已采用照料语言与伤害反差时恢复其条件；不将该模式推广到所有施害者
  omission_filled_in:
    action: patch
    direction: 删除未经采用且破坏必要留白的补写，来源作品的留白不自动约束新作
  referential_vagueness_rewrite:
    action: patch
    direction: 恢复指代对象与关系的可理解性，承前省略、实词或指示词均可使用
```

## 执行操作与定位契约

以下两个既有 `patch_kinds` 值直接说明改写范围。问题机制相同时，局部语义与保护条件仍可能需要不同范围；操作名本身不承担问题诊断。

```yaml
patch_kinds:
  rewrite_sentence:
    action: patch
    mode: semantic_rewriter
    direction: 在获准句内消除已确认的问题，保留事实、作用和声线
  rewrite_span:
    action: patch
    mode: semantic_rewriter
    direction: 在获准 old_span 内重组句群，保留 preserve 条件；超出范围回场景裁决者
```

`rewrite_span` 使用 `old_span`、`anchor_quote_start`、`anchor_quote_end` 与 `location.line_range` 定位；`rewrite_sentence` 及其他既有机制类 patch 使用 `anchor_quote`。引文在当前正文唯一定位，重复原文用行范围消歧。两个 rewrite 类型沿现有接口提供 `rewrite_directive`。裁决者按问题与范围选择既有类型，修订者按下发类型执行定位与校验契约。

## 超出局部修订的回交理由

下列名称保留在 `requires_rollback_reason` 中，供裁决者按正文证据、影响范围与责任决定回交 writer 或设计阶段。问题在局部授权内可修时，由裁决者选既有 `patch_kinds` 生成 PATCH 指令，问题名称保留在 `issue` 中；修订者收到的 ROLLBACK 类仍按既有协议回交。

```yaml
requires_rollback_reason:
  epic_death_facing:
    direction: 仅在死亡场面违背已确认的事件/人物设计且需要重写时使用，不指定死亡方式与临终台词
  mirror_loosened:
    direction: 本作明确采用的结构关系缺失、局部无法恢复时回结构或场景负责人
  carrier_missing:
    direction: 必要作用未实现且局部无法修复时回场景负责人；候选 carrier 被其他有效方式替代不触发
  narrator_distance_global_drift:
    direction: 叙述权限或整体距离失配且超出局部授权时回场景负责人
```
