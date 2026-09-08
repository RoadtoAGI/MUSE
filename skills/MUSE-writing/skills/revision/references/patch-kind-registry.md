# 定点修订类型

类型供场景裁决者标记已经确认的问题；实际授权范围与问题机制决定动作。原型名称不要求新作复制特定剧情。

```yaml
patch_kinds:
  carrier_then_explain:
    action: patch
    direction: 删除已由前文充分表达、且不增加认识或关系作用的重复解释
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
  rewrite_sentence:
    action: patch
    mode: semantic_rewriter
    direction: 在获准句内消除已确认的问题，保留事实、作用和声线
  rewrite_span:
    action: patch
    mode: semantic_rewriter
    direction: 在获准 old_span 内重组句群，保留 preserve 条件；超出范围回场景裁决者
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

rewrite_span 使用 old_span、anchor_quote_start、anchor_quote_end 与 location.line_range 定位。单句 patch 使用 anchor_quote。具体引文必须可在当前正文定位；字符串长度与命中数量不代替唯一性及语义判断。
