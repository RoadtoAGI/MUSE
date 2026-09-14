# Phase 5 输出 Schema

交付物文件：`pipeline/phase5_scenes.yaml`

每个 scene card 是 `pipeline/phase5_scenes.yaml` 中一个场景对象。可直接使用顶层 `scenes[]`，或按下面的 `sequence_expansions[].scenes[]` 分组；选择一种存储形态，保持读者呈现顺序。字段应承载下游决策所需的意图、边界与候选素材。

```yaml
sequence_expansions:
  - seq_id: ARC1-SEQ1
    scenes:
      - scene_id: S01
        arc_id: ARC-1              # 派生字段：从 seq_id 归属 Arc 获得
        title: "场景标题"
        pov: "视角角色 char_id"
        narration_style: close-third  # close-third=紧贴 pov 角色内心 | third-omniscient=全知叙述者 | first=第一人称
        participants:
          - "已绑定的角色 char_id 或一次性 participant ID"
        location_time: "本场景时空坐标（如 '破宅 / 黄昏'）"
        conflict: "本场的追求与阻力、待解信息关系或母题联系；按实际组织方式填写"
        value_start: "开始时的关键叙事状态（desire 关注价值处境，information 关注信息或认识，motif 关注关系、感知或意义；字段名保留兼容）"
        value_end: "结束时的关键叙事状态；状态保持时按本场作用说明，不虚构翻转"
        reader_track: "本场读者跟随的主要问题、行动或感知变化"
        scene_tasks:
          - abstract_function: "本场要完成的事件、人物、关系或感知变化"
            physical_carrier: []     # 已有合适候选时填 {text, function_link}
            reader_yield:
              - "读者由本场取得的新证据、理解或待解问题"
            rendering:
              default: summary
              expand_only_if: "本场需要读者经历的变化、感知或过程及其成立条件"
            voice_gear: dense        # 可选；有角色 voice_boundaries 依据时，提示声音突出或收敛；随人物压力和表达目的判断
        inspiration_refs:           # optional，引用 inspiration_ledger 中 type=pattern 的 INS-* 卡
          - INS-001
          - INS-007
        handoff: "衔接到下一场景的方式"
        beat_direction: "（仅关键场景）压力、期待或解释怎样改向及其原因"

        # —— 以下为按场景需要填写的可选字段 ——
        pov_constraint:
          can_perceive: [字符串]
          cannot_perceive: [字符串]
          intentional_blind_spot: "关键遮蔽（描述）"

        craft_carrier:
          type: "object | bodily_action | silence | procedural_form | second_hand_story | sensory_shock | scale_shift | expectation_reversal"
          concrete_anchor: "具体物件 / 动作 / 声音 / 文体"
          replaces: "该承载方式的叙事作用；有替代对象时说明替代了什么"

        # world_disclosure_plan：本场世界信息披露边界。
        # 缺省时按来源事实、人物知情和既定揭示时点决定。
        # 详细语义与渲染契约见下方 `world_disclosure_plan` 小节。
        world_disclosure_plan:
          forbid:
            - "本场尚未获准揭示的具体事实"
          allow:
            - "本场已到揭示时点、且具备来源依据的信息"

        omission_plan:
          - "本场故意不解释什么"

        irreversible_action:
          - "本场已确认为必要的不可撤销变化及其条件"

        reveal_method:
          type: "direct_action | indirect_evidence | witness_chain | object_trace | official_record | overheard_fragment | bodily_reaction | delayed_revelation"

        # —— 以下为按场景需要填写的可选字段 ——
        narrator_distance:
          mode: "intimate_first | reminiscing_first | reporter_third_close | reporter_third_distant | archival_zero | omniscient_satirist | bilingual_drifter | unreliable_first"
          # enum 沿既有接口；依据本作已确认叙述方式和本场作用选择。
          reason: "为什么选这个距离 — 写一句"

        scale_inversion:
          used: true        # true | false
          bridge: "连接大命题与小物件的具体桥（粮票 / 二向箔 / 5kg 生态球 / 一只手 / 一句回家）"

        precedent_mirror:
          mirrors_scene: "S_XX | null"
          mirror_kind: "failure | success | irony | null"
          preserved_anchors: ["同样的动作 / 物件 / 命令词清单"]
          removed_premises: ["前者成功 / 失败 / 完整的前提，本场景被删除的"]

        # 高潮场景的模式线索；writer 按已选机制与本场条件实现。
        # climax=true 不自动加载全部高潮模板。
        climax_pattern:
          primary: "layered_revelation | ineffable_realization | passive_death | mask_hard_cut | unfinished_action | anti_epic_failure | scale_shrink | null"
          secondary: "同上或 null"
          forbidden_moves: []  # 有明确作者禁界时写出对象与条件，不自动采用模板禁句
          # 仅 scene_card.climax / sequence_climax / arc_climax = true 时显式选择；
          # 缺字段时 writer 不加载任何高潮模板（fallback = 走通用 Craft Preflight）

        # 对白偏好的 scene 级 hint；writer 在 dialogue-craft 工坊阶段消费。
        # 缺字段 = writer 走通用 dialogue 设计（不强约束）。
        dialogue_hints:
          - speaker: "<角色名 | null（表示对全场 hint）>"
            attribution_strategy: "neutral_tag | action_bridge | object_bridge | listener_reaction | omitted_tag"
            # 5 enum：句子在 narrative 中怎么被标注（纯归属策略）
            dialogue_form: "diagnostic_verdict | single_word_winner | caretaker_tone_violence | monosyllable_confession | co_creation_as_confession | null"
            # 5 enum + null：对白本身呈现的形态
            reason: "为什么本场偏好这个组合 — 写一句（可选）"

        # 反先验场景标记：日常行为与高情感处境相遇，按其实际作用判断。
        # 参考：《挪威的森林》scene 10 — 医院 + 黄瓜 + 欧里庇得斯。
        # used=true 时 dispatcher 激活卡上材料，具体实现按作用和条件选择。
        # 缺字段 / used=false → 沿一般写作路径。
        counter_prior_scene:
          used: true                                  # true | false
          kind: "ritual_with_food | hospital_with_lecture | death_with_chore | farewell_with_chess | custom"
          mundane_action: "<在当前情境中确有作用的日常行为，作为候选实现>"
          emotional_context: "<本场压力与关系>"
          forbidden_moves: []  # 已确认的作者禁界须说明对象与条件

        # 写作层 AI pattern 预防：声明本场 writer 应主动规避的风险族 + 本场特化正向策略。
        # used=true 时 scene_card.md 渲染 `## 写作层 AI pattern 预防 (prose_risk_contract)` 段；
        # 缺字段 / used=false → 不渲染，writer 走通用 Craft Preflight。
        prose_risk_contract:
          used: true                                  # true | false
          risk_families:                              # 本场 high-risk family；family 名锚 ai-cliche-patterns.md 现有条目（F 类 snake_case 或 A-G 中文短语）
            - "动作清单化"
            - "psychological_overfill"
            - "情绪库存短语"
          positive_strategy:                          # 本场特化策略；通用修法 writer 通过 prose-craft skill 查 ai-cliche-patterns.md
            - "例行调度若重复结算同一结果，可合并；改变人物关系或实际压力的交接保留展开"
            - "比喻若只重复已表达的情绪，可删并；带来贴合人物的新认识、声音或感知时保留"
          bad_shape_examples:                         # 可选；补充有辨别价值的形态示例，按机制判断
            - "停下、低头、伸手的连续步骤若没有新增感知或代价，可以收束；逐步发现危险时可以展开"
            - "已有沉重情绪后再写‘像某种没有声音的重量’，若没有新的意象或人物作用，只是在重复结算"

tension_curve:
  description: "张力曲线的文字描述"
  peaks:
    - "高张力场景 ID"
  valleys:
    - "低张力场景 ID"

scene_causal_chain: "S01 →（因为…）S02 →（因此…）S03 → ..."
```

## scene_task 字段与语义

新产物的 `scene_tasks` 是非空对象列表。对象四字段分别承担意图、候选实现、读者所得和展开尺度；具体方法由场景与人物条件决定。

```yaml
scene_task:
  abstract_function: "本场要发生的事件、人物、关系或感知变化"
  physical_carrier:                  # list，可为空
    - text: "候选动作、物件、对白、感官或叙述安排"
      function_link: "该候选怎样服务本任务；缺少什么条件就不成立"
  reader_yield:
    - "读者由本场取得的新证据、理解或待解问题"
  rendering:
    default: summary                 # summary | expand
    expand_only_if: "过程本身改变选择、理解、压力或阅读节奏的具体条件"
```

### 结构与接口

四字段均须存在。`abstract_function` 为非空文本；`physical_carrier` 为列表，允许 `[]`；非空项包含非空且非占位的 `text` 与 `function_link`。`reader_yield` 为非空文本列表。`rendering.default` 为 `summary | expand`，`expand_only_if` 写明取舍条件。缺字段或类型错误回章编排修正；词汇命中只提供语义复核线索。

`physical_carrier` 保留为候选，writer 可以替换、合并或舍弃。已定事实、人物知识边界、必须发生的结果应由场景作用、入场/离场状态及专门约束承载，不依赖一份候选动作清单隐式传递。完整来源与权限关系见[上下文协议](../../serial-chapter-writing/references/context-contract.md)。

### 语义判据

- `abstract_function` 保留创作判断所需的心理、关系或母题意图；“边界”“机制”等词不能自行证明问题。只有评价“精彩、深刻、得体”而未说明要改变什么时，补足对象与作用。
- `physical_carrier.text` 指出可写入场景的材料，`function_link` 解释其作用。普通移动、操作可在正文承担衔接；在大纲逐项规定它们，需要说明其选择、方式或后果如何影响本场。
- `reader_yield` 可以描述读者将获知什么、重估什么、继续追问什么。单写“感动、震撼、紧张”缺少判断依据，应补出造成该体验的处境、信息或选择。氛围与感官目标具有独立表达作用时保留，并说明它怎样改变场景体验。
- `rendering` 指导亲历与概述的取舍。关键变化需要读者看见，支撑材料可给结果与必要锚点；任何档位都不要求穷尽动作过程。各任务应服务本场 `reader_track`，并行线或对照可以共同构成阅读焦点。

### 历史字符串读取

既有任务如 `[核心][main] ...` 按两个维度解释：`核心` 表示必要叙事工作，`灵感/惊艳` 表示可选构想；`main` 表示正面呈现的关键变化，`support` 表示结果与必要锚点，`atmosphere` 表示背景压力或感知。缺第二个 marker 时按 `support` 读取。修订这些任务时迁移为对象字段，保留原有有效意图与约束；新产物不再补写 marker。

## 字段说明

| 字段 | 必需 | 下游使用 |
|------|------|---------|
| `sequence_expansions[].seq_id` | 采用分组时 | 关联本章使用的单元/序列组织；已有有效 Phase 4 设计时沿用其归属 |
| `scenes[].scene_id` | 是 | Phase 6（按 ID 展开每个场景为叙事文本）。**必须匹配 `^S\d{2}$`**（`S01` / `S02` / ... / `S99`）；不得含 `scene_` 前缀或纯数字格式，否则下游路径模板 `pipeline/scene_{scene_id}/` 会撞双前缀（如 `scene_scene_1`）|
| `scenes[].arc_id` | 是 | Phase 6（快速定位当前幕的价值方向）。派生字段：从 seq_id 归属 Arc 获得 |
| `scenes[].title` | 是 | Phase 6（场景标识） |
| `scenes[].pov` | 是 | Phase 6（叙事视角锚定） |
| `scenes[].narration_style` | 是 | Phase 6（叙事腔调锚）。close-third=紧贴 pov 角色内心；third-omniscient=全知叙述者；first=第一人称 |
| `scenes[].participants` | 是 | Phase 6（确定对白角色）、character-rehearsal（Actor 分配） |
| `scenes[].location_time` | 是 | Phase 6（时空坐标，使用本章上下文及相关世界册的有效条件） |
| `scenes[].conflict` | 是 | Phase 6（场景卡显示“冲突或组织关系”：欲望组织时写追求与阻力，信息组织时写证据与待解问题，母题或观察组织时写意义、感知之间的联系；无人物对抗时按实际关系填写） |
| `scenes[].value_start` / `value_end` | 是 | 章内设计与审阅；writer-facing scene_card 只显示“入场处境 / 离场结果”，正文通过行动与后果使变化成立 |
| `scenes[].reader_track` | 是 | 章内设计与审阅；writer-facing scene_card 显示“阅读焦点” |
| `scenes[].scene_tasks` | 是 | 章内设计与审阅；writer-facing scene_card 保留本场作用、候选材料及其作用依据、读者所得和展开尺度，以可读标签呈现 |
| `scenes[].inspiration_refs` | 否 | Phase 6（writer 通过 scene_card.md 看见本场 INS-* 引用，再按 ledger 的 carrier / disclosure_ladder 消费）；仅记录对本场有实际作用的引用 |
| `scenes[].handoff` | 是 | Phase 6（场景衔接） |
| `scenes[].beat_direction` | 否 | 章 orchestrator、role-brief-deriver 与 review（仅关键场景）；不进入 writer-facing scene_card |
| `scenes[].scene_tasks[].voice_gear` | 否 | Phase 6 writer（声音突出/收敛的场景提示）、scene-review（按人物依据检查 signature_voice_overuse） |
| `scenes[].pov_constraint` | 否 | Phase 6（writer：限定本场 POV 可感知/不可感知项，定位 intentional_blind_spot；缺字段=仍遵守叙述视角和人物实际可知范围） |
| `scenes[].craft_carrier` | 否 | Phase 6（writer：type+concrete_anchor 提供承载候选，replaces 说明其作用及适用的替代关系；缺字段时由 writer 决定实现） |
| `scenes[].world_disclosure_plan` | 否 | Phase 6（writer：授权 / 禁止借物披露世界规则的边界；`{forbid, allow}` 字符串列表 × 2；缺字段=按来源事实、人物知情与既定揭示时点判断） |
| `scenes[].omission_plan` | 否 | Phase 6（writer：本场故意不解释什么；缺字段=不强约束省略点） |
| `scenes[].irreversible_action` | 否 | Phase 6（本场已确认为必要的不可撤销变化及其条件；仅为实现候选的动作放入 physical_carrier，不用本字段提前固定） |
| `scenes[].reveal_method` | 否 | Phase 6（writer：信息揭示方式锚——direct_action / object_trace / overheard_fragment 等；缺字段=writer 自由选择揭示路径） |
| `scenes[].narrator_distance` | 否 | Phase 6（writer：本场叙事距离 mode + reason，沿既有 8 值 enum；缺字段时使用本作已确认的叙述方式） |
| `scenes[].scale_inversion` | 否 | Phase 6（writer：是否启用大命题↔小物件反转 + 具体桥；缺字段=不强约束） |
| `scenes[].precedent_mirror` | 否 | Phase 6（writer：本场镜像哪场 + 镜像类型 + 保留锚点 + 删除前提；缺字段=不构造镜像关系） |
| `scenes[].climax_pattern` | 否 | Phase 6（writer：高潮场景 pattern 锚——primary/secondary 7 enum + null；仅 climax/sequence_climax/arc_climax=true 时显式选择；缺字段=不加载任何高潮模板，走通用 Craft Preflight） |
| `scenes[].dialogue_hints` | 否 | Phase 6（writer 在 dialogue-craft 工坊阶段消费：每条 hint = `{speaker, attribution_strategy(5 enum), dialogue_form(5 enum + null), reason}`；缺字段=走通用 dialogue 设计，不强约束） |
| `scenes[].counter_prior_scene` | 否 | Phase 6（反先验场景的结构化提示：`{used, kind, mundane_action, emotional_context, forbidden_moves}`。`used=true` 时 dispatcher 激活 scene_card 上的相应材料；具体实现按作用和适用条件判断，已确认的作者禁界保留。缺字段 / `used=false` 时沿一般写作路径）|
| `scenes[].prose_risk_contract` | 否 | Phase 6（`used=true` 且有内容时渲染场景风险和策略供 writer / reviewer 使用；对象缺省或 `used=false` 时走通用写作指导。提取只检查当前场景已提供对象的格式）|
| `tension_curve` | 否 | 章编排与当前审阅按相关问题理解压力、节奏与变化 |
| `scene_causal_chain` | 否 | 章编排与当前审阅按相关问题核对因果依赖 |

#### inspiration_refs（optional）

| 子字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `inspiration_refs[]` | string[] | 否 | INS-* ID 引用 ledger 中 type=pattern 的卡 |

只保留改变本场设计决策的引用；数量由实际作用决定。

**Hard gate**（`validate_phase5_r10.py`）：双向一致性匹配——ledger 内 INS-* 的 `project_encoding[]` 必须有对应 `(phase=5, chapter_id, scene_id, adoption_kind ∈ {scene_carrier, reveal_carrier, structure_carrier, craft_carrier})` 项。

## `world_disclosure_plan` (optional, str list × 2)

说明本场允许和暂缓披露的具体世界信息。允许披露仍需符合来源事实、人物知情和既定揭示时点；字段缺省时沿用这些约束。

```yaml
world_disclosure_plan:
  forbid:                       # 禁止披露的内容
    - 本场尚未获准揭示的具体事实
  allow:                        # 允许披露的内容
    - 本场已到揭示时点、且具备来源依据的信息
```

**渲染契约**（由 `extract_scene_card.py` 实施）：

- 段标题精确字面量：`## 世界观披露 (world_disclosure_plan)`
- 字段缺失 OR `forbid` 与 `allow` 同时为空 → 整段不输出
- 任一非空 → 输出段标题 + 该非空列表（另一侧空则不输出对应子标题）
- 渲染位置：在 scene_card.md 内输出即可；与其他场景约束相邻显示

## `prose_risk_contract`（按风险使用）

写作层 AI pattern 提示：保留本场已识别的风险条件与可用策略。无具体风险时可省略对象或使用 `used: false`。family 命名锚 `prose-craft/references/ai-cliche-patterns.md` 现有条目（F 类已用 snake_case；A-G 类与观察层用中文短语——两者都接受）。

**字段语义**：

| 字段 | 必需 | 语义 |
|---|---|---|
| `used` | 对象存在时 | 布尔值；`true` 且有内容时 scene_card.md 渲染 contract 段供 writer / reviewer 消费；`false` 或对象缺省时不渲染 |
| `risk_families` | 按已识别风险填写 | 列表可空，元素为非空字符串。family 名锚 ai-cliche-patterns.md 现有条目；未知 family 不阻断 writer，按实际风险和既有写作指导判断 |
| `positive_strategy` | 有可用策略时 | 列表可空，元素为非空字符串。保留本场风险条件和合适处理；通用方法由 writer 通过 prose-craft 查阅 |
| `bad_shape_examples` | 否 | 列表可空，元素为非空字符串；本场具体形态示例说明触发条件和决定性差异，writer 按实际语境判断机制 |

**设计原则**：

- 用 `positive_strategy` 说明具体风险的形成条件与修正方向，不把动作、对白或比喻数量当成质量判据
- `bad_shape_examples` 是结构示例不是禁词——writer 不做字面规避

**渲染契约**（由 `extract_scene_card.py` 实施）：

- 段标题精确字面量：`## 写作层 AI pattern 预防 (prose_risk_contract)`
- 字段缺失 OR `used != true` OR 三个子列表（risk_families / positive_strategy / bad_shape_examples）皆空 → 整段不输出

**与 `counter_prior_scene` 同场冲突兜底**：

- 两字段共同服务本场表达。先服从来源事实、知情范围与已授权的场景结果；具体场景策略可调整一般 craft 偏好，语义规则不能覆盖硬约束。
- 同时满足会破坏场景功能时，按[上下文协议](../../serial-chapter-writing/references/context-contract.md)报告冲突来源，由 orchestrator 交回对应设计者修订输入；仅换 writer 不能解决互相矛盾的指令。
