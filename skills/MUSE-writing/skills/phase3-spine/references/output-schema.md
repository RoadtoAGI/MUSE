# Phase 3 输出 Schema

交付物文件：`pipeline/phase3_spine.yaml`

```yaml
inciting_incident:
  description: "激励事件的具体描述"
  type: decision | accident
  timing: "在故事中的位置"
  balance_before: "事件前的日常平衡状态"
  balance_after: "事件后的失衡状态"

spine_mode: desire | information | motif

desire_object:   # 条件字段：仅 spine_mode=desire 时必填；information/motif 下为 null
  conscious: "自觉欲望对象（主角明确追求的具体目标）"
  unconscious: null  # optional；仅 Phase 2 已成立时填写本人未察觉的追求
  tension: null      # optional；存在双层欲望时解释关系

spine_statement: "一句话脊椎表述（语义按 spine_mode 解释：desire='主角想要 X 为此克服 Y' / information='真相 T 如何逐步显形' / motif='母题 M 如何展开呼应变形'）"
spine_type: conscious | unconscious   # 条件字段：仅 spine_mode=desire 时填；其他 mode 下为 null

reader_spine:    # 所有 mode 通用；读者整篇追踪的认知线，可与角色脊椎错位
  reader_waits_to_know: "读者真正等什么被确认 / 推翻"
  recognition_object: "读者凭哪些事件、经验或叙述关系形成最终认识"
  withheld_answer: "确需延迟的答案与理由；无需保密时为空或 null"
  reveal_ladder_seed:             # 整块 conditional；未命中触发判据时省略，保留三个位置键，未使用的位置可为空数组
    early_signals:
      - "早期信号：读者首次接触相关物件 / 行为 / 异常，价值未解释"
    mid_reframes:
      - "中段重构：物件 / 行为意义被部分修正 / 升级"
    final_confirmation:
      - "终局确认：真相在具体载体上显形"

dramatic_question:
  question: "核心戏剧问题（**这也是全篇读者追问**——读者整篇跟随的最大问题，不只是作者结构问题。Phase 5 的 reader_track 是其在单场尺度的具体化）"
  obligatory_scene: "读者期待看到的必备场景描述"

opposing_forces:
  - type: "对抗类型（如内在/人际/社会/环境/超自然等，按故事需要）"
    description: "具体对抗描述"

# ── 幕/Arc 框架 ──
arcs:
  - arc_id: ARC-1
    name: "Arc 名称"
    value_at_start: "进入此 Arc 时的关键叙事状态（语义按 spine_mode 解释：desire=价值状态 / information=信息或认知状态 / motif=母题状态；schema 字段名保留不变作向后兼容）"
    value_at_end: "离开此 Arc 时的关键叙事状态（语义同上，跨 mode 共用字段名）"
    climax_event: "Arc 高潮事件（一句话；desire 下=价值逆转、information 下=真相披露、motif 下=母题变奏）"
    function_note: "此 Arc 在整体故事中承担什么（可选）"

# ── 故事级危机/高潮/结局 ──
story_climax_design:
  crisis:
    dilemma: "结局前的待解处境；确有两难时说明选择为何互斥"
    option_a: null  # 有互斥选择时写 A 的条件与后果；无两难时为 null
    option_b: null  # 有互斥选择时写 B 的条件与后果；无两难时为 null
    character_revelation: "行动或认识变化显出的人物真相"
  climax:
    action: "高潮行动"
    value_change:
      from: "起始价值"
      to: "终止价值"
    controlling_idea_expression: "如何体现主控思想"
    climax_form: hero_succeeds | hero_fails_world_completes | withdrawal_as_resolution | silence_after_truth   # 可选；默认 hero_succeeds；其余三档为失败型高潮形态
  resolution:
    new_balance: "高潮后的新平衡状态"
    lingering_feeling: "留给读者的余味"
```

## 字段说明

| 字段 | 必需 | 下游使用 |
|------|------|---------|
| `inciting_incident` | 是 | Phase 4（按实际呈现位置展开激励事件及必要铺垫）|
| `spine_mode` | 是 | **phase-local operational enum**——声明故事组织力类型。enum：`desire`（麦基默认：单主角欲望 + 不懈努力）\| `information`（真相显形 / 碎片聚拢）\| `motif`（观念 / 意象 / 风格驱动的组织力）。Phase 3 独立判定，不回读 Phase 0 `primary_drive` 做条件分支。**消费者**：Phase 5 `spine_statement` 取舍测试按 mode 解释。**既有产物 fallback**：`phase3_spine.yaml` 缺 `spine_mode` 时兼容层按 `desire` 解释，新生成路径必须显式选择最贴近的一类，不允许以"不确定"为由跳过判定 |
| `desire_object` | 条件（`spine_mode=desire` 时必填；其他 mode 下为 null）| Phase 3 推导脊椎的欲望依据；其他 mode 为 null。下游从脊椎、Arc 和收束设计消费其结果 |
| `spine_statement` | 是 | Phase 5 场景取舍测试（是否与脊椎相关？）——**所有 `spine_mode` 通用**，语义按 mode 解释（desire 下"是否推进欲望"、information 下"是否贡献真相显形碎片"、motif 下"是否呼应/变形母题"）|
| `spine_type` | 条件（`spine_mode=desire` 时填；其他 mode 下为 null）| 仅 desire mode 下使用；其他 mode 下不适用（不强制填写）|
| `reader_spine` | 是（所有 mode 通用）| 读者整篇追踪的认知线，可与角色脊椎错位。**消费者**：Phase 5 `reader_track` 单场具体化时回查；Phase 6 / Phase 7 用 `withheld_answer` 校验是否过早披露；高潮场景用 `recognition_object` 锚定读者确认的具体载体（失败型高潮尤其关键）|
| `reader_spine.reveal_ladder_seed` | 否 | 真实事实、因果或身份需分阶段释放，且各段改变行动、归因、关系判断或价值评价时启用；按实际释放阶段填写，未使用位置为空数组；普通母题、象征和伏笔不触发 |
| `dramatic_question` | 是 | Phase 7（核对核心关切的收束是否符合已选意图）|
| `opposing_forces` | 是 | Phase 4（对抗力量分配到序列）。数组结构，类型和数量按故事需要，麦基的内在/个人/外在三层仅供参考 |
| `arcs[]` | 是 | Phase 4（逐 Arc 展开为序列）|
| `story_climax_design` | 是 | Phase 5（设计危机/高潮场景）、Phase 6（展开高潮场景）。`climax.climax_form` 可选 enum：`hero_succeeds`（默认）/ `hero_fails_world_completes` / `withdrawal_as_resolution` / `silence_after_truth`（后三档为失败型高潮形态，详见 SKILL.md "故事高潮"段）|

#### reveal_ladder_seed（optional）

| 子字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `early_signals` | string[] | 键存在，允许空数组 | 早期信号 |
| `mid_reframes` | string[] | 键存在，允许空数组 | 中段重构 |
| `final_confirmation` | string[] | 键存在，允许空数组 | 终局确认 |
