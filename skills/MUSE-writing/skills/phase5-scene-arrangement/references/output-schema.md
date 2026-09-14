# Phase 5 输出 Schema

交付物文件：`pipeline/phase5_scenes.yaml`

> **scene_card 概念 vs 物理**：scene_card 是 L2 设计中的**逻辑单位**（每场景一个）；**物理落地**为本文件交付的 `pipeline/phase5_scenes.yaml` 的 `scenes[]` 列表——每元素对应一个 scene_card。不存在"每场景独立文件"的物理布局。

```yaml
sequence_expansions:
  - seq_id: ARC1-SEQ1
    scenes:
      - scene_id: S01
        arc_id: ARC-1              # 派生字段：从 seq_id 归属 Arc 获得
        title: "场景标题"
        pov: "视角角色名"
        narration_style: close-third  # close-third=紧贴 pov 角色内心 | third-omniscient=全知叙述者 | first=第一人称
        participants:
          - "角色 slug"
        location_time: "本场景时空坐标（如 '破宅 / 黄昏'）"
        conflict: "本场的追求与阻力、待解信息关系或母题联系；按实际组织方式填写"
        value_start: "开始时的关键叙事状态（语义按 spine_mode 解释：desire=价值状态 / information=信息或认知状态 / observe-motif=关系或感知状态；schema 字段名保留作向后兼容）"
        value_end: "结束时的关键叙事状态（语义同上，按实际结果记录；作用不能仅由起止标签判断）"
        reader_track: "本场读者跟随的阅读焦点及必要关联（如『小龙女判断陌生人证据是否可信，并决定是否纳入寻找杨过的行动』）"
        scene_tasks:
          - abstract_function: "角色第三层自欺话术被击穿"
            physical_carrier:       # optional；Phase 5 已找到承重候选时才写
              - text: "杯沿停在唇边却没喝"
                function_link: "杯沿停顿 → 自欺裂缝可观察化"
            reader_yield:
              - "关系压力"
              - "自欺破裂"
            rendering:
              default: summary
              expand_only_if: "动作改变关系 / 危险 / 欲望"
        inspiration_refs:           # optional，引用 inspiration_ledger 中 type=pattern 的 INS-* 卡
          - INS-001
          - INS-007
        handoff: "衔接到下一场景的方式"
        beat_direction: "（仅关键场景）压力、期待或解释怎样改向及其原因"

        # —— 以下 5 字段全部 optional（缺字段时 writer 走通用 Craft Preflight，不强约束）——
        pov_constraint:
          can_perceive: [字符串]
          cannot_perceive: [字符串]
          intentional_blind_spot: "关键遮蔽（描述）"

        craft_carrier:
          type: "object | bodily_action | silence | procedural_form | second_hand_story | sensory_shock | scale_shift | expectation_reversal"
          concrete_anchor: "具体物件 / 动作 / 声音 / 文体"
          replaces: "它替代了哪段解释 / 心理 / 背景"

        # world_disclosure_plan：安排当前场景释放或暂缓的世界规则。
        # 缺省 = writer 按用户要求、Phase 1 与当前冲突完成最低读者定向。
        # 详细语义与渲染契约见下方 `world_disclosure_plan` 小节。
        world_disclosure_plan:
          forbid:
            - "当前 POV 尚无渠道得知的幕后操控者身份"
          allow:
            - "由回忆或现场证据交代当前危险怎样形成、传播或运作"
            - "让行动选择成立所需的生存规则与世界规则"

        omission_plan:
          - "本场明确省略什么；涉及后续揭示的答案时说明适用范围和实际释放条件"

        irreversible_action:
          - "一个可见且不可撤销的动作"

        reveal_method:
          type: "direct_action | indirect_evidence | witness_chain | object_trace | official_record | overheard_fragment | bodily_reaction | delayed_revelation"

        # —— 以下 4 字段全部 optional（缺字段时 writer 走通用 Craft Preflight，不强约束）——
        narrator_distance:
          mode: "本场叙述位置；可沿用既有 narrator_position 标签或用准确描述"
          # 继承 phase0 craft_targets.narrator_position.primary；按场景需要说明调整
          reason: "为什么选这个距离 — 写一句"

        scale_inversion:
          used: true        # true | false
          bridge: "连接大命题与小物件的具体桥（粮票 / 二向箔 / 5kg 生态球 / 一只手 / 一句回家）"

        precedent_mirror:
          mirrors_scene: "S_XX | null"
          mirror_kind: "failure | success | irony | null"
          preserved_anchors: ["同样的动作 / 物件 / 命令词清单"]
          removed_premises: ["前者成功 / 失败 / 完整的前提，本场景被删除的"]

        # 高潮场景的可选机制参考。字段与既有 enum 保持兼容；
        # writer 可按最终效果采用、组合、改造或舍弃，不把 pattern 当步骤模板。
        climax_pattern:
          primary: "layered_revelation | ineffable_realization | passive_death | mask_hard_cut | unfinished_action | anti_epic_failure | scale_shrink | null"
          secondary: "同上或 null"
          forbidden_moves: ["不得追加解释链", "不得宏大辞藻堆叠"]  # 仅故事不变量/因果/知识边界类禁项为硬约束
          # 仅 scene_card.climax / sequence_climax / arc_climax = true 时显式选择；
          # 缺字段时 writer 使用通用 Craft Preflight，仍可自主选择其他高潮手法

        # 对白偏好的 scene 级 hint；writer 在 dialogue-craft 工坊阶段消费。
        # 缺字段 = writer 走通用 dialogue 设计（不强约束）。
        dialogue_hints:
          - speaker: "<角色名 | null（表示对全场 hint）>"
            attribution_strategy: "neutral_tag | action_bridge | object_bridge | listener_reaction | omitted_tag"
            # 5 enum：句子在 narrative 中怎么被标注（纯归属策略）
            dialogue_form: "diagnostic_verdict | single_word_winner | caretaker_tone_violence | monosyllable_confession | co_creation_as_confession | null"
            # 5 enum + null：对白本身呈现的形态
            reason: "为什么本场偏好这个组合 — 写一句（可选）"

        # 反先验场景标记：本场景的核心设计 = "高情感语境中嵌入不合适的日常行为"
        # 参考：《挪威的森林》scene 10 — 医院 + 黄瓜 + 欧里庇得斯。
        # used=true 时 phase6 dispatcher 触发 fast-path：orchestrator 读子字段
        # 拼额外约束注入 writer dispatch prompt。
        # 缺字段 / used=false → writer 不收特殊注入，走通用 Craft Preflight。
        counter_prior_scene:
          used: true                                  # true | false
          kind: "ritual_with_food | hospital_with_lecture | death_with_chore | farewell_with_chess | custom"
          mundane_action: "吃黄瓜 / 讲课 / 整理衣服 / 闲聊（具体描述：让 writer 知道嵌入的日常动作是什么）"
          emotional_context: "临终 / 崩溃 / 高压告别 / 灾难现场（高情感语境）"
          forbidden_moves: []  # 仅填写本作实际需要的限制与适用条件；不按该类型自动补禁令

        # 写作层 AI pattern 提示：标出本场值得关注的风险面与候选策略。
        # used=true 时 scene_card.md 渲染 `## 写作层 AI pattern 预防 (prose_risk_contract)` 段；
        # 缺字段 / used=false → 不渲染，writer 走通用 Craft Preflight。
        prose_risk_contract:
          used: true                                  # true | false
          risk_families:                              # 本场 high-risk family；family 名锚 ai-cliche-patterns.md 现有条目（F 类 snake_case 或 A-G 中文短语）
            - "动作清单化"
            - "psychological_overfill"
            - "情绪库存短语"
          positive_strategy:                          # 本场候选策略；writer 可用其他方式取得同等或更好的成品效果
            - "本场社交调度场景，动作合并必须落到关系压力变化点（不是单纯减字数）"
            - "本场短比喻只在感官替代功能成立时出现（不是通用『少用比喻』）"
          bad_shape_examples:                         # 可选；"长相"参考，只提供定位线索，不构成字面或结构禁令
            - "他停下，低头，看门缝，伸手，推开"
            - "像某种没有声音的重量"

tension_curve:
  description: "张力曲线的文字描述"
  peaks:
    - "高张力场景 ID"
  valleys:
    - "低张力场景 ID"

scene_causal_chain: "S01 →（因为…）S02 →（因此…）S03 → ..."
```

## scene_task 字段（对象结构）

每条 scene_task 必含三字段；`physical_carrier` 为条件字段：

```yaml
scene_task:
  abstract_function: <str>            # 允许保留戏剧意图概括（"角色第三层自欺话术被击穿"）
  physical_carrier:                   # optional list；非空项为候选戏剧承载物
    - text: <str>                     # 载体描述（"杯沿停在唇边却没喝"）
      function_link: <str>            # 对应 abstract_function 子节点 ID 或描述；去空白后非空
  reader_yield: [<str>, ...]          # 必须 ≥1 项开放文本；描述正文应产生的叙事增量
  rendering:
    default: summary | expand
    expand_only_if: <str>             # expand 条件（"动作改变关系 / 危险 / 欲望"）
```

### 必备字段校验

`abstract_function / reader_yield / rendering` 任一缺失 → schema error。`physical_carrier` 缺失合法；存在时必须是 list，存量 `[]` 合法。非空 carrier 项必须是含非空 `text` / `function_link` 的 object。

### 字段内容边界

`abstract_function` 写叙事工作，`reader_yield` 写希望成品产生的叙事增量。先定 `reader_yield`，再对候选 carrier 做替换测试：换成同类通用实现会改变因果结果、人物选择、读者判断、来源复用或形式效果时，Phase 5 预选才有帮助。同场 task 产生相同 `reader_yield` 时复核，只合并对同一结果的复述；重复继续改变行动、关系、压力、读者理解、不可逆后果、形式效果或来源复用时保留。普通移动、操作和仅有抽象气氛理由的动作留给 writer。“紧张 / 节奏 / 类型感”需写清声音暴露、退路封闭、伤势恶化、时间或资源损失、误判或选择收窄等具体变化。脚本只验证字段类型与连接完整性；内容质量由 Phase 5 编排者和成品审阅判断。

`rendering.default: expand` 表示动作次序与过程本身承载本场实际发生的局部逆转、选择或不可逆代价；读者只需结果或可用常识补完过程时使用 `summary`。`expand_only_if` 写本场已规划的具体变化。潜在效率、潜在安全和职业习惯不构成展开条件，也不得靠临时补造事件替候选 carrier 自证。

### carrier 连接完整性

任一已填写的 `physical_carrier` 项，其 `text` 和 `function_link` 都必须存在、为 str 且去空白后非空，否则 schema error。动作是否形成流水、是否具有场景功能由成品语境判断，schema 和脚本不按动作数量、句式或词表裁决。

## scene_tasks 语义（重要）

Phase 5 新产物使用上方 scene_task 对象结构。历史双 marker 字符串列表仅供下游兼容读取，不再指导新产物。

## 字段说明

| 字段 | 必需 | 下游使用 |
|------|------|---------|
| `sequence_expansions[].seq_id` | 是 | 关联 Phase 4 的序列设计 |
| `scenes[].scene_id` | 是 | Phase 6（按 ID 展开每个场景为叙事文本）。**必须匹配 `^S\d{2}$`**（`S01` / `S02` / ... / `S99`）；不得含 `scene_` 前缀或纯数字格式，否则下游路径模板 `pipeline/scene_{scene_id}/` 会撞双前缀（如 `scene_scene_1`）|
| `scenes[].arc_id` | 是 | Phase 6（快速定位当前幕的价值方向）。派生字段：从 seq_id 归属 Arc 获得 |
| `scenes[].title` | 是 | Phase 6（场景标识） |
| `scenes[].pov` | 是 | Phase 6（叙事视角锚定） |
| `scenes[].narration_style` | 是 | Phase 6（叙事腔调锚）。close-third=紧贴 pov 角色内心；third-omniscient=全知叙述者；first=第一人称 |
| `scenes[].participants` | 是 | Phase 6（确定对白角色）、character-rehearsal（Actor 分配） |
| `scenes[].location_time` | 是 | Phase 6（时空坐标，引用 Phase 1 世界观切片） |
| `scenes[].conflict` | 是 | Phase 6（场景卡显示“冲突或组织关系”：欲望组织时写追求与阻力，信息组织时写证据与待解问题，母题或观察组织时写意义、感知之间的联系；无人物对抗时按实际关系填写） |
| `scenes[].value_start` / `value_end` | 是 | Phase 6 设计与审阅；writer-facing scene_card 只显示“入场处境 / 离场结果”，正文通过行动与后果使变化成立 |
| `scenes[].reader_track` | 是 | Phase 6 设计与审阅；writer-facing scene_card 显示“阅读焦点” |
| `scenes[].scene_tasks` | 是 | Phase 6 设计与审阅；writer-facing scene_card 只投影需成立的叙事工作、可替换的候选承载、目标叙事增量和不规定正文顺序的呈现建议，不显示内部键与 function_link |
| `scenes[].inspiration_refs` | 否 | Phase 6（writer 通过 scene_card.md 看见本场 INS-* 引用；普通 pattern 由现有场景字段承载，ledger 实际存在 `disclosure_ladder` 时才消费对应 layer）；记录本场实际采用的材料 |
| `scenes[].handoff` | 是 | Phase 6（场景衔接） |
| `scenes[].beat_direction` | 否 | Phase 6 orchestrator、role-brief 与 review（仅关键场景）；不进入 writer-facing scene_card |
| `scenes[].pov_constraint` | 否 | Phase 6（writer：限定本场 POV 可感知/不可感知项，定位 intentional_blind_spot；缺字段=无额外 POV 限制，人物知识与既定叙述方式继续生效） |
| `scenes[].craft_carrier` | 否 | Phase 6（writer：鸿沟由 type+concrete_anchor 承载，replaces 指明它替代了哪段解释/心理/背景；缺字段=由 writer 临场决定承载） |
| `scenes[].world_disclosure_plan` | 否 | Phase 6（writer：安排当前场景释放 / 暂缓的世界规则；`{forbid, allow}` 字符串列表 × 2；缺字段=按用户要求、Phase 1 与当前冲突完成最低读者定向） |
| `scenes[].omission_plan` | 否 | 字符串列表；writer 与作者侧审阅取得本场省略要求。承接 `reader_spine.withheld_answer` 时附实际延迟条件；永久留白保留，缺字段=无额外省略要求 |
| `scenes[].irreversible_action` | 否 | Phase 6（writer：本场不可逆结果的候选实现；仅明确规定的事实/因果结果为硬约束；缺字段=不强约束） |
| `scenes[].reveal_method` | 否 | Phase 6（writer：信息揭示方式锚——direct_action / object_trace / overheard_fragment 等；缺字段=writer 自由选择揭示路径） |
| `scenes[].narrator_distance` | 否 | Phase 6（writer：本场叙事距离 mode + reason；继承 phase0 craft_targets.narrator_position.primary；可按本场职责调整，缺字段=继承既有叙述位置） |
| `scenes[].scale_inversion` | 否 | Phase 6（writer：是否启用大命题↔小物件反转 + 具体桥；缺字段=不强约束） |
| `scenes[].precedent_mirror` | 否 | Phase 6（writer：本场镜像哪场 + 镜像类型 + 保留锚点 + 删除前提；缺字段=不构造镜像关系） |
| `scenes[].climax_pattern` | 否 | Phase 6（writer：高潮场景可选机制参考；primary/secondary 保持既有 7 enum + null 兼容。writer 可采用、组合、改造或舍弃；缺字段走通用 Craft Preflight） |
| `scenes[].dialogue_hints` | 否 | Phase 6（writer 在 dialogue-craft 工坊阶段消费：每条 hint = `{speaker, attribution_strategy(5 enum), dialogue_form(5 enum + null), reason}`；缺字段=走通用 dialogue 设计，不强约束） |
| `scenes[].counter_prior_scene` | 否 | Phase 6（dispatcher 反先验场景 fast-path 信号——结构化对象：`{used, kind, mundane_action, emotional_context, forbidden_moves}`。`used=true` 时 orchestrator 在 writer dispatch prompt 附加额外约束段；缺字段 / `used=false` → writer 不收特殊注入，走通用 Craft Preflight）|
| `scenes[].prose_risk_contract` | 否 | Phase 6（写作层 AI pattern 可选提示——结构化对象：`{used, risk_families, positive_strategy, bad_shape_examples}`。`used=true` 时渲染供 writer / scene-reviewer 参考；缺字段 / `used=false` → writer 走通用 Craft Preflight）|
| `tension_curve` | 否 | Phase 7（验证全文张力分布） |
| `scene_causal_chain` | 否 | Phase 7（因果链审查） |

#### inspiration_refs（optional）

| 子字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `inspiration_refs[]` | string[] | 否 | INS-* ID 引用 ledger 中本场实际采用的 type=pattern 卡 |

引用数量由材料对本场剧情的作用决定。每张卡的成立条件与作用沿现有场景字段表达，来源数量不增加情节步骤或兑现次数。

**Hard gate**（`validate_phase5_r10.py`）：双向一致性匹配——ledger 内 INS-* 的 `project_encoding[]` 必须有对应 `(phase=5, scene_id, adoption_kind ∈ {scene_carrier, reveal_carrier, structure_carrier, craft_carrier})` 项。

`reader_spine` 到 `reader_track / scene_tasks / omission_plan` 的转换方法见 [SKILL.md“读者信息与世界规则的定向”](../SKILL.md#1ter-读者信息与世界规则的定向)。现有提取器将这些字段随场景卡交 writer；作者侧披露安排与人物所知分别判断。

## `world_disclosure_plan` (optional, str list × 2)

安排 writer 在当前场景释放或暂缓的世界规则。缺省时，writer 按用户要求、Phase 1 `generative_driver`、canon 与当前冲突完成最低读者定向。

```yaml
world_disclosure_plan:
  forbid:                       # 区分人物知识限制与作者明确的延迟披露；按既定视角适用
    - 当前 POV 尚无渠道得知的幕后操控者身份
  allow:                        # 当前冲突成立所需的信息，按贴身/外部叙述的实际渠道呈现
    - 由回忆或现场证据交代当前危险怎样形成、传播或运作
    - 让行动选择成立所需的生存规则与世界规则
```

人物未知不等于全知叙述者不得交代；`forbid` 中角色知识限制与作者延迟计划分别适用，并服从用户明确要求、Phase 1 世界事实和手选 canon 绑定。信息延迟需要服务后续判断或转折；开放式结局没有默认偏好。篇幅较短时，当前危险的类型差异与行动因果仍应让读者可理解，披露方式由 POV 和场景压力决定。

**渲染契约**（由 `extract_scene_card.py` 实施）：

- 段标题精确字面量：`## 世界观披露 (world_disclosure_plan)`
- 字段缺失 OR `forbid` 与 `allow` 同时为空 → 整段不输出
- 任一非空 → 输出段标题 + 该非空列表（另一侧空则不输出对应子标题）
- 渲染位置：在 scene_card.md 内输出即可（渲染位置软化契约）；位置 executor 按现有 `_render_v3_fields` 结构判断

## `prose_risk_contract` (optional, 4 子字段对象)

写作层 AI pattern 可选提示：记录本场值得关注的风险面与候选处理方向。family 可引用 `prose-craft/references/ai-cliche-patterns.md` 现有条目。

**字段语义**：

| 字段 | 必需 | 语义 |
|---|---|---|
| `used` | 是 | `true` 时 scene_card.md 渲染 contract 段作 writer / reviewer 可见 canonical source；`false` 或缺整段对象 → 不渲染 |
| `risk_families` | 否 | 风险关注清单；存在时为由非空字符串组成的 list。family 可锚 ai-cliche-patterns.md 现有条目，未知 family 不阻断 writer |
| `positive_strategy` | 否 | 本场候选策略；存在时为由非空字符串组成的 list。writer 可用其他方法实现同等或更好的成品效果 |
| `bad_shape_examples` | 否 | 问题形态线索；存在时为由非空字符串组成的 list，只用于帮助定位风险 |

**设计原则**：

- 不写数字阈值；用场景语义说明风险与候选方向
- `bad_shape_examples` 只提供定位线索；writer 和 reviewer 都回到实际正文判断

**渲染契约**（由 `extract_scene_card.py` 实施）：

- 段标题精确字面量：`## 写作层 AI pattern 预防 (prose_risk_contract)`
- 字段缺失 OR `used != true` OR 三个子列表（risk_families / positive_strategy / bad_shape_examples）皆空 → 整段不输出

与其他场景提示冲突时，故事事实、人物知识边界、核心因果和 handoff 优先；其余技巧提示由 writer 按成品效果取舍，不新增冲突分支。
