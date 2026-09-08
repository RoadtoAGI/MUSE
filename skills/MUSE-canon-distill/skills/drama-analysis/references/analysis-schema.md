# 戏剧分析契约

本契约保留戏剧的空间、表演与观众信息机制。原作事实附定位，结构解释说明理由；特定演出本的选择限于该版本。可选内容缺少证据或无分析作用时省略。

## 作品与分析身份

`work-meta.yaml` 集中记录作品、作者、译者、版本与媒介。`source_medium` 使用 stage_play / screenplay / teleplay / radio_play / musical_libretto / opera_libretto / traditional_opera；`dramatic_form` 为开放描述。`language` 指当前文本语言，原作语言可另记 `original_language`。类型与版本不同不应混写为同一事实。

```yaml
work_id: ferry-play
# 此处为格式示例，分析时填写实际作品身份。
title: 渡口
source_medium: stage_play
dramatic_form: one-act drama
language: zh
notes: 分析所用版本与文本范围
```

每个 `pipeline/phase{N}_*.yaml` 带 `analysis_meta`，用于识别逆向分析与来源。作品身份的详尽资料留在 work-meta；有必要的版本差异在对应分析处说明。

```yaml
analysis_meta:
  source: 渡口
  source_medium: stage_play
  dramatic_form: one-act drama
  reverse_engineered_from: drama-analysis
  completed_at: "2026-09-07"
  analyst_notes: 本节采用的版本、范围或解释分歧
```

以下模板省略重复的 `analysis_meta`。模板描述信息职责，取值和可选字段依真实文本填写。`reference_lanes / allowed_phases / forbidden_phases / transform_required` 的旧声明没有对应的通用拦截器；实际召回依查询字段，跨媒介适配由检索者与采用者判断。

## Phase 0：整体构想

文件 `pipeline/phase0_conception.yaml`。从实际事件与结局解释主要经验、张力和作品组织力。控制思想可以多义；无需给实验或开放作品补造唯一道德答案。

```yaml
premise: 人物进入怎样的处境，什么使其原有生活发生偏离
# genre 用于查询；描述作品实际题材或类型。
genre: contemporary-drama
core_value: 作品中的主要价值及其具体表现
controlling_idea: 由选择和结果支持的整体解释，附原文定位
core_tension: 有持续作用的冲突关系或经验张力
dramatic_engine: 张力怎样被维持、转化或耗尽，附关键场次
theatricality_notes: 表演或观众关系怎样参与意义形成
```

`dramatic_engine / theatricality_notes` 按实际作用填写，无需凑齐激励、维持、终结三种压力。

## Phase 1：世界与演出条件

文件 `pipeline/phase1_world_stage.yaml`。世界事实决定人物的行动条件，演出资源决定表达载体；二者分开描述。

```yaml
world_type: 原文世界的性质与题材条件
primary_space: 故事发生的实际空间及人物使用它的方式
power_structure: 制度、身份或资源如何影响行动
rules:
  - condition: 原文中成立的规则
    evidence: "full_text.md:L20-L28"
stagecraft_constraints:
  - condition: 此演出本明确限定的空间或资源
    evidence: "full_text.md:L4-L8"
```

只在实际限定时填写 `stagecraft_constraints`。电影中的房间、舞台的一套布景与戏曲的虚拟空间属于不同层次；不能把一种改编方案写成原作条件。戏曲可加 `xiqu_program`，记录有依据的行当、唱念做打或程式及其场内作用。

## Phase 2：人物系统

文件 `pipeline/phase2_roles.yaml`。用原角色键保存 mapping，消费者按 `name / name_zh` 或原键定位；兼容既有列表形式。角色关系连同个体一起阅读。

```yaml
roles:
  lin:
    name: 林
    dramatic_role: 本人在作品关系中的功能
    desire: 本人在具体时点的自觉追求
    obstacle: 相关阻力
    voice_function: 声音怎样作用于对象、关系与场面
    status_arc: 地位或关系的变化，也可稳定
    evidence: "full_text.md:L30-L52"
relationships:
  key_tensions: 人物之间的依赖、误解、冲突或亲近
contrast_axes: 有原文依据的差异如何改变人物选择
```

除身份与关系定位外，按角色实际证据填字段。欲望、自知、作者分析分别处理；`soliloquy_signature / aria_or_soliloquy_locations` 仅在实际独语或唱段有分析价值时填写。信使、合唱队、功能人物未必有独立转变；人物声音也不能从“反派”“母亲”等职能直接推导。

## Phase 3：故事组织力

文件 `pipeline/phase3_dramatic_spine.yaml`。记录连接主要事件的欲望、追问、母题或其他组织关系。麦基的冲突与后果分析帮助识别行动因果；六类固定节点不能代替本作结构。

```yaml
inciting_incident: 原文中打破相关平衡的事件与定位，适用时填写
dramatic_question: 作品实际形成的主要悬念或追问
objects_of_desire: 人物的追求及其时点
spine:
  - event: 实际事件或组织节点
    cause_and_consequence: 与前后事件的依赖、解释或对位
    evidence: "full_text.md:L60-L88"
obstacles: 使追求或理解受阻的条件
arcs: 分析出的主要轨迹及其起止依据
story_climax_design: 实际决定整体结果的变化；开放作品按其收束方式说明
```

字段有对应机制才填，`spine` 节点按原文命名。人物未行动、认识未达成或张力未解决，也可能构成有依据的组织结果。

## Phase 4：幕与序列

文件 `pipeline/phase4_act_sequence.yaml`。原文分幕保留原边界；每幕可包含多个分析序列。无幕作品使用有定位的连续段落，不补造三幕或幕末逆转。

```yaml
acts:
  - act_id: A1
    source_boundary: 原文幕号或分析划分及依据
    function: 此段在整体中的作用
    sequences:
      - seq_id: A1-Q1
        scenes: [A1S1, A1S2]
        function: 这些场次怎样构成相关行动或表达
        turn: 实际发生的改变；无改变时可省略
        end_state: 后续依赖的结果或状态
inter_act_weaving: 跨段因果、并置或母题关系，存在时填写
```

`act_id / seq_id` 只在本作品单元内标识层级。分析序列与剧本印刷场次分别保留；演员出入场可以是节拍变化，不必每次新建结构场。

## Phase 5：场次与原文边界

文件 `pipeline/phase5_scene_table.yaml`，`scenes` 覆盖本次分析范围的全部场次。无显式幕场时记录实际划分依据。

```yaml
scenes:
  - scene_id: A1S1
    act: 1
    scene: 1
    source_lines: [30, 88]
    location: 渡口候船室
    time: 当晚
    characters_on_stage: [林, 周]
    dramatic_purpose: 两人对离开一事持有不同理解，停航使双方必须共处
    scene_turn: 行程受阻，关系矛盾延续
    stageable_actions: [收拾行李, 等候停航通知]
    notes: "场面作用的解释，附 full_text.md:L30-L88"
```

`scene_id / source_lines` 用于切片；场内时空、人物及作用用于检索和分析。`act / scene` 依原文可省略。无人段落可用空人物列表；场内稳定、重复与悬而未决照实记录，`scene_turn` 仅在实际改变时填写。

上下场 `entrances / exits`、潜台词 `subtext`、独语 `monologue_or_soliloquy`、韵文形态 `verse_or_prose`、唱段或声画信息按需要加入。每条说明保留对象、知识与时点；独语对观众公开不等于向台上其他人公开。只标明“潜台词”不能替代对话语、行动与处境差异的解释。

## 场景索引

`dramatic_scene_index.jsonl` 每行一个 JSON 对象。必备场次身份、实际原文路径、查询字段及能解释该场的摘要；完整分析留在 Phase 文件。例：

```json
{"scene_id":"A1S1","work_id":"ferry-play","source_medium":"stage_play","genre":"contemporary-drama","lang":"zh","location":"渡口候船室","time":"当晚","characters_on_stage":["林","周"],"dramatic_purpose":"停航使关系已生分歧的两人继续共处","file":"scenes/scene_A1S1.md"}
```

- `file` 相对作品目录，使用 extract_scene 实际产出的 `scene_{scene_id}.md`。
- `genre` 沿用本作品 Phase 0 的实际类型，`lang` 指切片文本语言，`source_medium` 沿用本版本媒介。聚合兼容旧 `language`；新索引明确填写 `lang`。
- `characters_on_stage / subtext` 使用字符串列表，无证据时省略可选项或用空列表。完整解释和证据留在 Phase 5。`dramatic_form`、幕场、上下场、冲突、变化与表演动作按实际检索用途复用。
- 可选媒介信息：影视 `slugline / visual_progression`，音乐剧或歌剧 `musical_numbers / recitative_or_aria`，戏曲 `xiqu_program`。形式标签有实际依据再填。

聚合器与对白工具使用同一索引优先级：`dramatic_scene_index.jsonl`，其次历史 `scene_index.json`。改变源索引后的聚合与向量更新沿现有工具链进行，字段存在本身不证明召回或参考已被采用。

## 手艺标注

文件 `craft_notes/scene_{scene_id}_beats.md`，供既有技巧抽取和灵感提名读取。围绕有学习价值的机制组织：

1. 标明场次、原文行范围及当时人物和观众各自掌握的信息。
2. 按实际变化说明关键话语、行动、声画或上下场如何改变处境、关系或理解，并保留支持说明的原句或舞台指示。
3. 区分原文事实与分析解释，指出可迁移的条件、换媒介时需重选的载体；有文本依据的多义处保留不同解释。

例如人物已在场而别人退出躲藏，会改变后续言语的接收关系。分析须先核实出入场；“人物察觉监视”则需额外证据。无法确认时可比较不同解释如何改变表演，不能把推演写成剧情事实。

节拍数量与小节随机制决定。上下场、独语、唱段、状态变化或转场各有作用时相邻解释，无需为每类另建一套文件或填满模板。
