# 连载前推分析框架

本文件保留 Phase 0–5 的既有字段，供知识库分析与检索消费。字段用于描述原作；`scene_tasks`、`story_climax_design` 等历史名称不表示对新作发令，也不证明作者曾采用同名设计流程。

每份 Phase 带 `analysis_meta` 与可回查的来源。其余字段有对应机制才填写：适用但尚未确定可为 null，不适用的可省略或用空列表；不得为完整性补造类型颠覆、隐藏欲望、强度递增或价值翻转。独立场景、开放结构与群像可以保留实际形状。直接消费者读取对应 Phase 全文；索引只承载召回信息。

## 来源与范围

```yaml
analysis_meta:
  novel: 作品名
  source_text: full_text.md      # 实际原文；分章来源可用 published/manifest.yaml 定位
  through_chapter: C0018        # manifest 存在时沿实际章 ID；否则在 evidence_note 记原文截止
  source_form: 原文形态
  evidence_note: 本次覆盖范围、版本与定位方式
```

navigation 与 segments 是阅读导航。关键结论在对应字段就地附章/段或 `相对路径:L起-L止`；引用摘要不能替代所分析原文。analysis_meta 同时供创作侧 hook 识别分析资产，避免套用创作交付物的 schema。

## Phase 0：构想

《故事》第六章讨论前提与主控思想：前提开启探索，主控思想由关键价值变化及其原因表达。从已发生文本归纳价值问题，尚未发生的终局保持未定。

```yaml
premise: 人物进入什么处境，何种问题使生活偏离
core_value:
  positive: 原作中的主要价值
  negative: 与之相对的价值状态
  spectrum:                      # 原作存在相应层次时填写；不要求四格齐全
    contrary: 妥协或弱化的价值状态
    contradictory: 与正极直接相反的状态
    negation_of_negation: 负极进一步恶化或伪装为正极的状态
controlling_idea:                 # 可为 null；多义解释分别说明其依据
  value: 由原作支持的价值判断
  cause: 支持该判断的行动与后果
  full_statement: 整体解释及原文依据
  type: idealistic / pessimistic / ironic  # 适用时选择；不以分类代替解释
  provisional: true            # 仅方向假设加此标记；接管归入 intent 待共创
genre:
  primary: 有依据的主要类型
  secondary: null
  conventions: []                # 原作实际使用的背景、人物、事件或价值惯例
originality_statement:
  unique_angle: 本作有辨识度的组织或表达选择及其作用
  cliches_to_avoid: []            # 只有原文比较支持时填写，不推定作者有意避免
style_directives: []              # 描述原作风格，非新作必须遵循的规则
word_count: 0                    # 本次原文范围的实际统计
```

类型用于检索。主控思想与独创性属于解释，不能仅凭结局或题材标签断言；关键过程若形成反证，应修订或并列解释。价值光谱用于区分确有差异的处境，不把同义词填成四层。

## Phase 1：世界

《故事》第三章将背景作为创作限制：事件在所建立的世界中须有可能性与或然性。物理、社会、心理三类是本项目定位世界条件的方式；只有影响人物理解或选择的内容才需展开。

```yaml
setting:
  era: 时代
  duration: 实际时间跨度
  location: 主要地点
  conflict_levels:              # 原作出现的层次
    internal: 内在冲突来源
    personal: 人际冲突来源
    external: 社会或环境冲突来源
world_rules:
  physical: []
  social: []
  psychological: []
genre_conventions:
  primary_genre: 主要类型
  secondary_genre: null
  conventions:
    - convention: 实际惯例
      planned_subversion: 原作对惯例的使用或变形及证据  # 有对应选择才填写
daily_life:
  - dimension: 与原作相关的日常维度
    findings:
      - detail: 原文细节
        story_implication: 该细节如何影响选择、关系或表达
creative_constraints:
  - constraint: 有依据的世界限制
    narrative_function: 在原作中实际产生的作用
```

规则保留对象、条件、例外与来源时点。角色相信的规矩不自动成为世界真值；未提到的上限、代价或惯例变形保持未定。

## Phase 2：人物

系统图 `pipeline/phase2_character.yaml` 保存功能、对比与关系，供角色定位和结构参考。可选的 `characters/{角色名}.md` 保存有用的个体分析；原文可直接供角色蒸馏，无需先为每人补画像。相同信息在主要归属处维护，关系与个体判断互相需要时用定位衔接。

《故事》第五章以压力选择揭示性格，第十七章讨论连贯的内在矛盾。记录压力、可选行动、代价与实际选择，才足以解释人物；社会身份和某次言行不能直接推出永久性格。

```yaml
cast_overview:
  protagonist: 主角或主要人物
  antagonist: 对手或实际对抗力量
  supporting_cast:
    - name: 角色名
      function: 在原作中的具体作用
contrast_axes: 有证据的角色差异如何改变相同情境中的选择
relationships:
  power_dynamics: 权力与依赖关系
  key_tensions: []
  potential_shifts: []          # 已有张力支持的分析可能性，非已发生事实
```

个体分析可记录欲望、声音、稳定或变化的轨迹、关键对白、共情依据及历史原型差异。自觉目标可独立成立；隐藏欲望、人格缺陷与成长均按证据决定。人物自述、原文事实与分析推断分别写明，来源时点随判断保留。

## Phase 3：脊椎与主要轨迹

《故事》第八章解释激励事件如何打破平衡并引出欲望，第七章讨论主人公的意志和行动能力。MUSE 的 `spine_mode` 同时允许以信息追问或母题组织故事，这是项目的分析扩展。

```yaml
inciting_incident:              # 原作有可辨触发事件时填写
  description: 实际事件
  type: decision / accident    # 适用时使用，也可按实际事件说明
  timing: 原文位置
  balance_before: 原有处境
  balance_after: 改变后的处境
  impact_on_protagonist: 对主要人物的影响
spine_mode: desire / information / motif
spine_statement: 连接主要事件的追求、问题或组织关系
desire_object:                  # desire 模式且原文支持时
  conscious: 人物自觉追求
  unconscious: null             # 本人未觉察的另一追求，有行为证据才写
  tension: null                 # 两种追求实际冲突时说明
spine_type: conscious / unconscious / null
reader_spine:                   # 持续的信息追问确实组织原作时
  reader_waits_to_know: 读者持续追问的问题
  recognition_object: 原作借什么确认理解
  withheld_answer: 原文延后的答案
  reveal_ladder_seed:           # 确有分段揭示时，按实际信号填写
    early_signals: []
    mid_reframes: []
    final_confirmation: []
dramatic_question:
  question: 原作确立的主要问题
  obligatory_scene: 实际回应该问题的场景及定位；未回答则说明开放
opposing_forces:
  internal: 有依据的内在阻力
  personal: 有依据的人际阻力
  external: 有依据的外部阻力
arcs:
  - arc_id: ARC-1
    name: 轨迹名称
    value_at_start: 开始时的处境
    value_at_end: 所读范围末的处境
    climax_event: 实际承担局部决定性变化的事件；无则省略
    function_note: 本轨迹在整体中的作用及范围
story_climax_design:            # 记录实际整体结果；在连全书未决时可为空
  crisis:
    dilemma: 原作存在的选择困境
    option_a: 实际选项
    option_b: 实际选项
    character_revelation: 该选择说明什么
  climax:
    action: 实际行动或组织结果
    value_change: {from: 起始状态, to: 结果状态}
    controlling_idea_expression: 结果怎样支持整体解释
  resolution:
    new_balance: 实际余后状态
    lingering_feeling: 余味的分析与依据
```

未完结 Arc 标 `open_ended: true`，只写已发生部分；未发生的高潮不放入事实。方向假设标 provisional，接管时由 takeover-distill 放入 intent。原作未安排两难选择、独立高潮或明确答案时，保留实际收束方式。人物应当得到什么是评价，不能充作其不自觉欲望。

## Phase 4：序列及跨段关系

《故事》第二章区分场景、序列、幕和故事的变化尺度。按实际作用组织 Arc 与序列；章节是排版或发表单元，不能按章数直接映射层级。进一步说明见 [节拍分析](beat-analysis.md)。

```yaml
arc_expansions:
  - arc_id: ARC-1
    sequences:
      - seq_id: ARC1-SEQ1
        name: 序列名
        core_conflict: 核心冲突或持续张力
        escalation_direction: 处境、信息、关系或节奏的实际变化
        sequence_climax: 有局部决定性结果时填写
        closed: 实际闭合的问题，可为空
        opened: 实际打开的问题，可为空
    arc_progression_note: 序列间的组织作用
causal_chain: 有证据的序列因果关系；并行与对照分别说明
arc_progression:
  impact_escalation: 各 Arc 如何改变主要问题及其分量
  causal_chain: 有依据的 Arc 联系
narrative_threads:
  - name: 线名
    description: 本线的问题或持续作用
    primary_arcs: [ARC-1]
    presence: 实际出现范围
    evidence_scenes:            # 已切片时引用实际 scene ID；未切片可用原文定位
      - scene_id: S01
        note: 本场如何支持该解释
thread_intersections:
  - threads: [线甲, 线乙]
    cross_effect: 一线怎样改变另一线的条件、解释或选择
    evidence_scenes: []
```

场景相邻不证明因果；稳定、缓场或回旋也可承担作用。跨线并置只有对照效果时记录对照，不补造双方互相改变的事件。

## Phase 5：场景与表达

《故事》第二章与第十章强调冲突和价值处境变化。MUSE 也保留承担人物认识、信息、氛围或母题作用的片段，说明具体贡献；这是项目的参考取材范围，不要求所有片段都有正负翻转。

```yaml
sequence_expansions:
  - seq_id: ARC1-SEQ1
    scenes:
      - scene_id: S01
        arc_id: ARC-1          # 有对应层级时填写
        location: 原文地点
        time: 原文时间
        participants: []
        pov: 原文视角及权限
        conflict: 有冲突时说明对象与焦点
        value_start: 起始状态
        value_end: 结束状态，可与起始相同
        scene_tasks: 原作此场承担的作用及其依据；不改写为新作必须做的动作
        handoff: 与相邻段落的实际联系
        beat_direction: 关键场景的行为或认识变化
        source_chapter: 原文章/段及所属作品单元
        narrative_evidence:
          presentation: 时间、视角或线索的呈现次序
          transition_anchor: 读者据什么识别切换
          knowledge_change: 人物或读者认识的变化
          cross_thread_effect: 有跨线结果时填写
          effect: 具体阅读作用与依据
          source_anchor: 原文定位
tension_curve:                  # 对当前分析有用时
  description: 整体强弱与节奏的实际形态
  peaks: []
  valleys: []
causal_chain: 有依据的场景因果；呈现顺序另作说明
```

`scene_id`、原文范围与 `file` 的具体路径在入库时对应 scene_index。场景数量取决于当前用途与机制差异，代表性切片覆盖不能冒充全书穷尽。来源人物与情境保留到参考中，采用者再按当前作品决定迁移方式。
