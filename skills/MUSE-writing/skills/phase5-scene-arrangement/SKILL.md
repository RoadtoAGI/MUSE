---
name: phase5-scene-arrangement
description: 原创完整链的场景编排，把序列展开为场景清单，形成阅读焦点、必要结果、人物关系及呈现顺序；由编排或指定阶段任务调用。
---

# Phase 5: 展开序列为场景 + 预留节拍入口

## 核心原则

场景编排使本段的行动、解释、关系或感知产生可指认的作用。麦基以欲望、冲突和价值变化解释戏剧场景：在欲望组织的场景中，人物追求受到回应，回应改变策略、代价或选择，后果成为下一步行动的条件。信息与母题组织按证据重释、意义发展或对位形成推进。依据见 `references/mckee-scenes.md §场景定义 / §转折点`。

呈现单元也可承担观察、余波、连接或体验积累；按其实际增加的认识、感受与结构作用取舍。必要结果与后续条件由设计确定，具体动作、对白和微观节拍由 writer 结合人物与现场展开。

## 输入契约

从 Phase 4 接收（核心依赖）：
- `arc_expansions[]` — 按 Arc 组织的序列设计（逐序列展开为场景）
- `causal_chain` — 序列级因果链（场景间因果应与之对齐）
- `narrative_threads[]`（可选）— 真实多线故事中定位当前序列相关线；字段缺失按单线或无需区分解释

从 Phase 3 接收（参考依赖）：
- `spine_mode` — 解释本场状态变化的主路径；缺字段按 `desire` 消费
- `spine_statement` — 场景取舍测试：是否与脊椎相关？
- `reader_spine` — 当前读者问题、知识边界和待释放答案
- `story_climax_design` — 危机/高潮场景的设计依据
- `story_climax_design.resolution` — 收束场景需要抵达的结果状态
- `arcs[]` — Arc 的价值方向（场景的 arc_id 派生字段来源）

从 Phase 2 接收（核心依赖）：
- `protagonist`, `deuteragonist`（若存在）, `antagonist`, `supporting_cast` — 场景人物分配
- `voice_traits` — 涉及对白的场景需要声音特征参考

从 Phase 1 接收（核心依赖）：
- `generative_driver` — 题材的冲突生成机制；本场相关威胁与资源依据适用的世界机制推导，禁止临场发明与之矛盾的世界事实
- `world_rules` — 物理 / 社会 / 心理规则；约束场景内人物行动可能性

从 Phase 0 接收（参考依赖）：
- `core_value` — 本场的选择、认识与体验怎样参与全篇价值表达；不把所有信息和母题变化换成正负二元
- `requirements`（可选） — 用户的结构性约束（如章节数、段落格式）
- `style_directives`（可选） — 作品风格要求

## Canon/design reference（按问题取材）

关键场景构思尚未确定或被退回时，读取[大纲构思与回读](../story-writing/references/outline-exploration.md)：围绕已选关系和成立条件探索事件，推演人物行动与读者理解的变化，由作者裁决；微观表演留给 writer。

需要补取参考时，附临时自由文本 `narrative_problem`，描述本场要展开的认识以及信息释放、跨线影响、时间呈现、道德压力或转折问题。它只服务本次检索。

已有适用参考直接消费。首次构思缺少参考、新问题出现或现有材料不足时，通过 `Skill design-doc-reference` 补取材料；用户明确不要参考时跳过。调用时传入：

```
phase=5
genre=<Phase 0 genre.primary>
signals=<JSON: 至少含 scene_count_target, key_scene_types, pov_pattern, risk_families 中能填的>
```

调用成功 → Read `pipeline/references/phase5_design_ref.md`，学习：

- **场景尺度的变化**：原作怎样让行动、知识、关系、价值或感知状态发生转折
- **叙事组织证据**：信息、POV、时间或叙事线怎样进入和切换，结果改变了什么
- **微观入口**：关键场景只取得压力方向、鸿沟位置和少量原文手艺，具体动作—反应留给 writer
- 本场如何使已选构思中的关系变得可感知，来源机制怎样进入本作的 `reader_track / scene_tasks / craft_carrier` 并影响后果

**参考不可用时**：按已有材料与理论继续设计；作者指定的必要来源缺失时，保留该领域的待决问题。扩展包可用性未知时通过宿主入口确认；已确认不可用且条件未变时，沿用该结果。

## inspiration_refs[] 字段

scene_card 新增 `inspiration_refs` 字段——本场承载哪些 `pipeline/inspiration_ledger.yaml` 中 `type=pattern` 的 INS-* 灵感卡：

```yaml
scenes:
  - scene_id: S07
    reader_track: ...
    scene_tasks: [...]
    craft_carrier: ...
    inspiration_refs:               # 新增字段（全 optional）
      - INS-001                     # 引用 ledger 中 type=pattern 的卡
      - INS-007
```

**引用范围**：阅读与联想可以广泛展开。`inspiration_refs` 只记录本场实际采用的材料，数量由它们对剧情的作用决定；多个来源能够共同支持同一关系，无需为每张卡额外安排兑现步骤。

**字段引用闭环 hard gate**（脚本见 `validate_phase5_r10.py`）：

对每个 `scene.inspiration_refs[]` 中的 INS-*：

- ledger 内必须存在该 INS-*
- 引用的卡必须 `type=pattern` 且 `status ∈ {accepted, bound}`
- 该 INS-* 的 `project_encoding[]` 至少存在一项满足：
  - `phase == 5`
  - `scene_id == 本 scene_id`
  - `adoption_kind ∈ {scene_carrier, reveal_carrier, structure_carrier, craft_carrier}`

字段不存在 → 不报错（向后兼容）；存在则必须闭环自洽。

引用 pattern 卡只证明本场采用了它的机制来源，不自动产生 `disclosure_ladder`。Phase 3 已按真实分阶段信息释放启用 `reader_spine.reveal_ladder_seed` 时，Phase 5 才把对应卡的 ladder 绑定到具体场景；普通手艺、母题、象征和单次载体直接编码进现有 `reader_track / scene_tasks / craft_carrier`，不另造 early / mid / final 三次兑现。

## 执行步骤

### 1. 逐序列展开场景

**结构约束优先**：如果 Phase 0 的 `requirements` 中包含结构性约束（如"分为 5 章"、"4-5 个自然段"），以用户要求为主框架。

`requirements` 约束故事事实与成品效果。题面提到的普通操作或物件不自动成为逐项呈现义务；只有用户明确要求描写某个过程时，才为该过程保留场景空间，并选择其中会改变目标、阻力、判断或后果的部分展开。不要把题面名词拆成 scene task 清单。

普通操作的唯一收益若是重复证明人物熟练、谨慎或专业，而同场的承重行动已经能显示这项特质，整项 `scene_task` 省略；不要留下 `summary` task 让 writer 结算。省略意味着相关清单退出设计，不迁移到 `craft_note`、备注或其他自创字段。让特质从人物处理真实阻力的方式中出现。

Phase 3 的 `story_climax_design.crisis` 在两难成立时向危机场景传递处境、不可兼得的代价、实际选择及后果；选项为空时，围绕实际压力或认识变化设计收束。Phase 5 不继承 `option_a / option_b` 的排列、复述结构和“宣布选择”的表达方式。正式谈判、审讯、分诊、投票、法律程序或仪式在故事世界内确实以明示选项运作时，场景可以列举选项。

对 Phase 4 每个序列，设计其内部场景。每个场景需要：

- **scene_id**：编号，**必须匹配 `^S\d{2}$` pattern**（S01 / S02 / ... / S99）。下游所有路径模板形如 `pipeline/scene_{scene_id}/`、`pipeline/scenes/scene_{scene_id}.md`——`scene_id` 自身**不得含 `scene_` 前缀**，否则路径会撞双前缀（如 `pipeline/scene_scene_1/`）

| ❌ 错误 | ✅ 正确 |
|---|---|
| `scene_id: scene_1` | `scene_id: S01` |
| `scene_id: 1` / `scene_id: "1"` | `scene_id: S01` |
| `scene_id: s01` / `scene_id: S1` | `scene_id: S01`（大写 S + 两位零填充数字） |
| `scene_id: 第一场` | `scene_id: S01`（中文标题放 `title` 字段） |
- **arc_id**：派生字段，从所属序列的 arc_id 获得
- **title**：场景标题（供 Phase 6 场景标识 + 检索）
- **location_time**：时空坐标，何时何地发生（引用 Phase 1 世界观切片，如"破宅 / 黄昏"）
- **participants**：在场人物
- **pov**：从谁的眼睛看这个场景
- **conflict**：本场的追求与阻力、待解信息关系或母题联系，按输出 schema 的适用条件填写
- **value_start / value_end**：进入和离开时的**关键叙事状态**（保留平铺字段，按实际价值、信息、关系或感知记录；标签相同不能单独证明没有叙事作用）
- **reader_track**（必填）：本场读者跟随的阅读焦点及必要关联。scene_tasks 说明怎样服务当前焦点，允许多重关系与体验共同展开。例："小龙女判断陌生人证据是否可信，并决定是否纳入寻找杨过的行动"。
- **scene_tasks**：本场景彼此独立的**叙事增量** list。每条必须是 scene_task object，描述需成立的变化，不构成 writer 的执行步骤；见下方"scene_task 物理化判据"。
- **handoff**：如何衔接到下一个场景
- **narration_style**：叙事腔调锚。取值 `close-third`（紧贴 pov 角色内心）/ `third-omniscient`（全知叙述者）/ `first`（第一人称）。

场景数量由序列需要的变化、表达作用与呈现安排决定。

### 向 Phase 6 交付人物语义

`participants` 只记录在场人物。Phase 5 用现有 `conflict / reader_track / scene_tasks / value_start / value_end / handoff` 写清人物选择、信息差、关系代价与不同利益怎样改变本场；这些语义足够 Phase 6 判断普通场景直接 writer，或只为相关承重人物调用 isolated actor。Phase 5 不增加 `actor_needed` 路由字段，也不预写角色的解释、动作或台词清单。

### 场景节拍诊断

下列问题用于修复平坦场景，模型无需输出回答过程，也可以采用其他成立的推理路径：

- `desire`：人物期待什么，采用什么策略，对抗反应怎样制造裂口，结尾哪项状态改变；
- `information`：当前问题与暂定解释是什么，哪个证据或披露使其确认、失效或重构，新的判断怎样形成；
- `motif`：母题当前承载什么意义，本场怎样重复、变形或对位，人物、关系或读者感知怎样变化；
- 收束场景：主要轨迹是否抵达当前大纲规定的结果状态。

`reader_track / conflict / value_start / value_end / scene_tasks / handoff` 记录上述设计结果。诊断步骤和技巧名称不进入交付字段。

## scene_task 物理化判据

每条 scene_task 必含三字段；Phase 5 已经找到承重载体时再写 `physical_carrier`：

```yaml
scene_task:
  abstract_function: <str>          # 允许保留戏剧意图概括
  physical_carrier:                 # optional list of object；非空项为候选实现材料
    - text: <str>                   # 载体描述
      function_link: <str>          # 对应 abstract_function 子节点；去空白后非空
  reader_yield: [<str>, ...]
  rendering:
    default: summary | expand
    expand_only_if: <str>
```

### `physical_carrier` 提供候选承载

先写 `reader_yield`，再判断 Phase 5 是否需要替 writer 预选载体。`physical_carrier` 是条件字段：把候选动作、物件、声音、对白或感官换成同类通用实现后，场景的因果结果、人物选择、读者判断、来源复用或形式效果会随之改变，预选才有价值。没有这种差异时省略该字段；存量文件中的 `physical_carrier: []` 继续兼容。非空项用 `function_link` 写清候选改变了什么。Phase 6 writer 可按成品效果替换、合并或舍弃候选，不逐项兑现。

大纲只预先记录选择、方式或后果本身会改变情节状态、人物关系、世界认知、压力、节奏或类型体验的载体。读者能自行补完的普通移动和操作留给 writer。“渲染紧张”“控制节奏”“体现类型感”需要落到具体变化：声音暴露位置、出口被截断、伤势恶化、时间或资源损失、误判形成、选择空间收窄等。候选动作没有造成或显出这类变化时，抽象气氛理由不支持其进入大纲。

`rendering.default` 由读者需要亲历什么决定。局部逆转、选择或不可逆代价依赖动作次序与过程时用 `expand`；读者只需知道结果，或过程可以由常识补完时用 `summary`。`expand_only_if` 只能指向本场已经规划发生的具体变化。可能提高效率、可能降低风险、展示职业习惯等潜在收益不触发展开；也不要为了保留候选动作，临时补造事故、威胁或解释句替它证明价值。

### 用边际叙事增量收敛载体集合

Phase 5 同时比较一场内的全部 `scene_tasks / physical_carrier`，也利用全篇场景视野检查重复实现。同一 `reader_yield` 是复核信号：只复述同一结果的 task 或 carrier 合并；重复本身继续改变行动、关系、压力、读者理解、形式效果，或承担来源复用义务时，它仍是独立增量。

跨场重复的选择播报、回答复述、程序确认或母题回收只保留真正改变局势的实现；其余场景可以用抢先行动、误判、失败、关系反应、环境后果或省略推进。多人共同施压、证词累积、仪式复沓、喜剧节奏、形式回环和来源文本要求的重复，在重复本身产生新效果时保留。这项判断不要产生去重台账或新字段，结果直接体现为彼此独立的现有 scene task。

专业程序的每一步实际改变安全窗口、证据效力、权限、危险、资源或人物自由时，多步程序整体保留。多人只用近义话重复同一责任边界，或步骤只让记录多一栏时，它们没有独立增量。

同一个“离开”表面动作可以产生两种设计结果：

- `主人公转身、背包、下楼、回头`，`reader_yield: 紧张感`：动作身份不改变危险与选择，省略 carrier，给结果或交给 writer 自然衔接。
- `主人公松开防火门去抢药，门回弹发声，引来感染者并封住原路`：动作次序改变资源、噪声与退路，可写 carrier；正文需要读者经历这次取舍时设 `expand`。

判据落在变化与后果，同一动词在不同语境中可以省略，也可以承重。该判据只约束大纲取材，不限制 Phase 6 writer 自然使用必要的衔接动作。

近边界修复对：

```yaml
# 负例：本场没有发生限时取物，潜在便利不能授权展开
abstract_function: "表现人物做事有条理"
physical_carrier:
  - text: "司机把钥匙、手电和地图按取用顺序装袋"
    function_link: "排序可能在紧急时加快取用"
reader_yield: ["职业习惯"]
rendering:
  default: expand
  expand_only_if: "以后可能更快"

# 处置：省略 physical_carrier，给出已整备的结果；不要另造险情替排序自证。

# 正例：本场实际发生的取用方式改变了路线和危险
abstract_function: "让预先整备在突发断电中产生代价差"
physical_carrier:
  - text: "隧道断电时，司机从外袋直接摸到手电，赶在后车逼近前看见侧洞并改道"
    function_link: "取用位置缩短黑暗窗口，侧洞从不可见变成可选退路"
reader_yield: ["危险窗口缩短并产生新路线"]
rendering:
  default: expand
  expand_only_if: "手电的取用时点实际改变可见信息和撤离路线"
```

缺少功能连接的 carrier 项（schema error）：

```yaml
physical_carrier:
  - text: "裴怀璧端起酒杯"
    function_link: ""               # 触发 schema error
```

历史双 marker 字符串（如 `[核心][main] ...`）仅保留为下游渲染兼容；Phase 5 新产物不再以字符串任务作为主结构。详细校验见 [references/output-schema.md](references/output-schema.md)。

### 1bis. 因果顺序与呈现顺序

`scene_causal_chain` 记录事件依赖；`sequence_expansions[].scenes[]` 的列表顺序是交给 Phase 6 和 Phase 7 的读者呈现顺序。编排者可使用插叙、倒叙、并行主线和多 POV，对同一事件从不同位置进入。跳转需要读者可感知的时间、地点、人物或物件锚点，并遵守各 POV 的知识边界。

暂搁当前线、补写另一线的来历时，先确定读者为何在此需要这段经历，再说明接回后的行动或理解怎样变化；遇到进入时机或时间归属难点，读[同期补叙的编排示例](references/mckee-scenes.md#同期补叙怎样接回当前行动)。

叙事结构由故事压力决定。线性顺序有效时保留；相同组织已使阅读焦点或节奏钝化时，调整有关场景；有效复沓可以保留。这里不设技巧种类、次数或配额。

### 1ter. 读者信息与世界规则的定向

本场涉及 `reader_spine` 中已规划的秘密时，沿呈现顺序判断读者此刻需要理解什么、可以看见哪些事实、哪项确认需延迟，以及延迟怎样影响后续判断。阅读焦点写入 `reader_track`；本场要成立的发现及其依据写入 `scene_tasks`；仍需保留的答案、适用范围和实际释放条件写入现有 `omission_plan`。这条交接适用于一般原创秘密；世界规则继续使用下方 `world_disclosure_plan`，实际采用来源 ladder 时继续保留既有绑定。

`omission_plan` 同时保留作者明确的一般省略意图，包括无需后文解释的心理、背景或永久留白；这些安排按既定作用保持，无需设定解除或兑现时点。本场没有额外省略要求时省略该字段。

例如，女儿在复印件上发现疑似父亲的签名：本场可以呈现字迹相似及她怀疑的依据，核对原件前仍不替读者确认签名真伪。`scene_tasks` 保存这项发现，`omission_plan` 保存延迟确认的条件。若读者已看见父亲签名，阅读焦点可转为女儿何时发现、发现后付出什么代价，已有答案继续成立。

读者披露意图属于作者侧安排，由场景卡交 writer；人物当前能知什么，仍由 deriver 按经历、事件时点与可见刺激派生。人物已知而读者暂未知时，依照现有视角与叙述距离选择呈现，保留人物据此行动的能力；读者已知而人物未知时，人物继续受自己的知识条件约束。

跨线切换涉及知情差异时，分别判断人物知道哪项事实、如何取得，以及读者已从其他线看见什么；需要辨认相近知识的区别时，读[伪信示例](references/mckee-scenes.md#切换保留读者已知与人物未知)。

`world_disclosure_plan` 只安排当前场景需要释放或暂缓的信息。它服从用户要求、Phase 1 `generative_driver`、手选 canon 绑定和人物知识边界。大纲应在合适场景完成最低读者定向，让读者获得理解当前危险、选择与因果所需的世界信息；信息可以通过回忆、亲历、媒介、传闻或现场证据进入，方式由 POV 与场景压力决定。

延迟某项信息需要形成后续判断或转折。隐藏本故事所依赖的灾变机制、把手选世界观降格为传闻，或以“留白”为由让当前危险失去类型差异，都会削弱场景因果。`forbid` 只记录当前 POV 尚不可知或有明确延迟收益的内容，不默认隐藏终极成因。

Phase 4 提供 `narrative_threads` 时，按当前 `seq_id` 的 `sequence_refs` 识别相关线。场景不复制线程标签；跨线影响在发生的场景中写成 `conflict`、状态变化和 `handoff`。POV 轮换没有改变另一条线的资源、代价、解释或选择空间时，按人物呈现处理。

安排较晚援助或资源使用时，保留所需的早期状态及中间事件造成的变化，把必要依赖写入 `scene_causal_chain / handoff`。已有条件可以直接支持后续行动；需要区分这种兑现与早期事实的重释时，读[伏笔与分晓](references/mckee-scenes.md#伏笔与分晓)及其项目编排应用。

### 2. 标注关键场景的节拍方向

对以下关键场景，标注 `beat_direction`——节拍的大致方向和鸿沟位置：
- 激励事件场景
- 每个序列的高潮场景
- 每个 Arc 的高潮场景
- 故事危机/高潮场景

`beat_direction` 给 Phase 6 提供关键变化方向，不生成逐拍动作清单：

- `desire`：行为方向、期待裂口和结果状态；
- `information`：判断变化和需要被释放的信息；
- `motif`：意义怎样变形，以及读者需要感知的结果。

示例：
- "从信任走到背叛，鸿沟在老板拿出审计数据时裂开"
- "从安全感走到不可逆的被困感，罗辑发现面壁者身份不可撤销"

`beat_direction` 写清压力或信息在哪里改向，避免只写“情绪升高”。动作、物件、对白、微观反应和句法由 writer 选择；Phase 5 已有贴切来源材料时，可以作为候选写入 `craft_carrier`。

非关键场景不标注 beat_direction——节拍在 Phase 6 创作中自然生长。

### 3. 设计张力曲线

重复同一种压力和反应会钝化读者（原文见 `references/mckee-scenes.md §张力设计`）。张力曲线描述哪种压力在何处接管、释放或改向，以及它怎样改变人物策略、信息状态、关系或选择空间。高低交替、整体上升和高潮前加速都是可用形状，由当前故事的因果与阅读效果决定。

### 4. 验证因果连接

沿 `scene_causal_chain` 核对关键结果怎样影响后续事件，所需前提是否已建立；沿呈现次序核对读者能否理解当前片段。倒叙、并置或母题回响不要求相邻呈现场景直接互为原因；需要因果的选择与后果不能仅用“然后”连接。

### 5. 非事件测试（所有 `spine_mode` 通用）

最终检查：删除或合并本场后，读者是否失去具体的因果、认识、关系、体验或结构作用？没有损失时删并；必要观察、余波与连接有作用时保留。不能只凭 `value_start` 与 `value_end` 标签相同判定非事件。

### 6. AI pattern 场景提示（可选）

只有 Phase 5 已能指出本场特有的高风险叙述形态时，才写 `scene_card.prose_risk_contract` 并设 `used: true`。缺整个字段与 `used: false` 都表示没有场景级补充，writer 继续使用通用 Craft Preflight；不要求逐场评估或显式填写关闭状态。

`risk_families` 只标出值得关注的风险面；`positive_strategy` 与 `bad_shape_examples` 提供候选处理方向。它们不规定 writer 的实现路径，也不能单独证明正文违规。writer 与 scene-reviewer 都以最终正文中的实际形态和影响为准。

若 Phase 0 `style_directives`、文风 ref 或本场设计已经明确采用碎段、留白、静默、短切等风格形态，可在 scene_card 写 `literary_device` 作为成品审阅的语境锚：`naked_line`（克制裸句 / 静默留白）、`staccato_action`（动作短切碎段）、`archive_cold`（档案体冷叙述）、`storyteller_voice`（说书腔套语声口）。字段缺失保持合法；正文中的风格功能也可由成品本身举证。

`risk_families` 可引用 `prose-craft/references/ai-cliche-patterns.md` 现有 family 名。字段格式与渲染契约见 [`references/output-schema.md`](references/output-schema.md) `## prose_risk_contract` 段。

## 输出

→ YAML 输出结构见 `references/output-schema.md`

Phase 5 交付物：`pipeline/phase5_scenes.yaml`（聚合 yaml），其 `scenes[]` 每元素是一个 **scene_card**（L2 逻辑单位），供 Phase 6 writer / orchestrator 调度消费。
逐角色 `role_views/{slug}.yaml` 与可选 `{slug}_role_move.yaml` 都属于 Phase 6 runtime；Phase 5 只交付其语义来源，不生成这些文件。

聚合 yaml 同时包含：sequence_expansions[]（按序列分组的场景）、tension_curve、scene_causal_chain。

## 常见错误

| 错误 | 后果 | 修正 |
|------|------|------|
| 视角或时间切换缺少锚点 | 读者无法判断何时、何地、谁在感知 | 在混淆点补时间、地点、人物或物件锚点 |
| 所有场景都标注 beat_direction | 过度设计，挤压 Phase 6 创作空间 | 仅关键场景标注 |
| 删除或合并场景后，具体的因果、认识、关系、体验或结构作用均无损失 | 缺少独立或累积作用 | 删除或并入邻场；有效的连接、等待、观察与余波按实际作用保留 |
| 用 `must_include` / `characters` / `setting` / `core_conflict` / `value_shift` 等禁用字段名 | 下游 schema 对齐失败 | 统一用权威字段名：scene_tasks / participants / location_time / conflict / value_start+value_end |

> scene_tasks 的完整语义（禁写抽象读者反应 / 氛围目标 / 道具清单等）单一权威见 `references/output-schema.md §scene_tasks 语义`——Step 1 的 ✅/❌ 示例与之一致。

→ 理论深度参考见 `references/mckee-scenes.md`
→ **承载模式参考**：[`prose-craft/references/novel-craft-patterns.md`](../prose-craft/references/novel-craft-patterns.md)（按需加载——A 类承载点 / B 类视角 / C 类高潮 / D 类人物 / E 类形态；设计 scene_card 的 `craft_carrier` / `beat_direction` 时可参考）
