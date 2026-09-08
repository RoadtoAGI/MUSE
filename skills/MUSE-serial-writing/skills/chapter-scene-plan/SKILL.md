---
name: chapter-scene-plan
description: 场景编排技能——把序列/章意图展开为具体场景清单，规划每场景的实质性叙事增量（按 spine_mode 解释：价值变化 / 信息揭示 / 关系重估 / 感知重构）、冲突和张力曲线，并为关键场景标注节拍方向。连载态是章节撰写第一步（serial-chapter-writing 章内编排触发，含章卡补全与重装配收束义务）；单篇/继承基线态由 pipeline orchestrator 触发。内部件，不直接承接用户自然语言入口。
---

# chapter-scene-plan — 场景编排

## 核心原则

麦基以人物的欲望、行动、冲突和价值变化定义戏剧场景。MUSE 据此要求场景承载**实质性的叙事增量**，并对信息、母题或观察驱动的故事采用项目扩展：证据改变解释，关系被重估，或呈现方式改变读者的感知。原著依据与扩展边界见 [场景与编排](references/mckee-scenes.md)。

**场景取舍判据**：说明本场对行动、认识、关系、感知或阅读节奏的实际作用。删除后这些作用均不受损的重复材料可省略或并入邻场；稳定处境中的观察、等待和余波也可以独立成场，不为字段差异虚构转折。

## 职责与执行总览

本 skill 拥有从序列/章意图到 `phase5_scenes.yaml` 的场景编排，以及章 mini-run 的上下文选材和章卡同步。正文写作归 writer，逐角色 `role_views` 归 `role-brief-deriver`。在连载章中，先读取[上下文协议](../serial-chapter-writing/references/context-contract.md)，按同一来源、时点与权限口径使用 scene card 和 `serial_context.md`。

```text
[识别工作区与输入]
  |-- 章 workspace -> [本章卷纲/前章 + 初始上下文]
  |                            |
  |                  [章卡选人物/实体 -> 装配并读取] -------------+
  `-- 单篇/继承基线 ---------> [Phase 0-4 输入] ------------------+
                                                                     |
                                                                     v
                    [按设计缺口取得或复用参考]
                                 |
                    [已有 phase5_scenes.yaml?]
                      | yes                 | no
                      v                     v
               [按衍生模式保留/补缺]   [从零展开场景]
                      `----------+----------'
                                 v
                 [逐序列展开 scene_card]
                                 |
              [按需选择呈现顺序与排布模式]
                                 |
              [关键节拍 -> 张力 -> 因果连接]
                                 |
              [非事件测试 + prose_risk_contract]
                                 |
                     [写 phase5_scenes.yaml]
                                 |
                       [章 workspace?]
                 | yes                         | no
                 v                             |
       [同步 recap_inputs / pov / scene_plan]   |
                 |                             |
       [章卡变化时刷新 serial_context]          |
                 |                             |
          [设计与所用上下文一致?]                |
             | yes       | no                  |
             |           `--> [停止；不 dispatch]
             `-------------+-------------------'
                           v
                 [完成校验，交接 Phase 6 writer]
```

## 输入契约

从 Phase 4 接收（核心依赖）：
- `arc_expansions[]` — 按 Arc 组织的序列设计（逐序列展开为场景）
- `causal_chain` — 序列级因果链（场景间因果应与之对齐）

从 Phase 3 接收（参考依赖）：
- `spine_statement` — 场景取舍测试：是否与脊椎相关？
- `story_climax_design` — 危机/高潮场景的设计依据
- `arcs[]` — Arc 的价值方向（场景的 arc_id 派生字段来源）

从 Phase 2 接收（核心依赖）：
- `protagonist`, `deuteragonist`（若存在）, `antagonist`, `supporting_cast` — 场景人物分配
- `voice_traits` — 涉及对白的场景需要声音特征参考

从 Phase 1 接收（核心依赖）：
- `generative_driver` — 题材的冲突生成机制；场景的具体威胁、可用资源、不可信/可信细节应从 driver 推导，禁止临场发明与之矛盾的世界事实
- `world_rules` — 物理 / 社会 / 心理规则；约束场景内人物行动可能性

从 Phase 0 接收（参考依赖）：
- `core_value` — 场景的实质性叙事增量围绕核心价值的正负极（desire 下=价值变化 / information 下=围绕真相显形的认知正负极 / motif 下=母题展开的语义正负极）
- `requirements`（可选） — 用户的结构性约束（如章节数、段落格式）
- `style_directives`（可选） — 作品风格要求

## 章内编排（连载章 mini-run 态）

工作目录是章 workspace（`chapters/V0N/C####/`，其内有 `chapter_card.yaml` 与 `pipeline/serial_context.md`）时，本 phase 以**章内编排**形态执行，输入替代关系如下：

- **来源**：本章的 logline、opened/closed 义务取自 `series/volumes/V0N.yaml` 中当前章条目；`chapter_card.yaml` 持有 hook 设计、POV 和选材范围；`pipeline/serial_context.md` 汇集系列约束、卷单元意图、已发生事实、人物与前章衔接。它们承接上方 Phase 0–4 的相应语义，章内无需补造整篇 Phase 1/2/3/4 文件。
- **输出不变**：仍是本章 `pipeline/phase5_scenes.yaml`，schema 与下方执行步骤、字段判据全部原样适用；场景在 scene 域内**局部编号 S01 起**，只编排本章。
- **分级节拍映射**：卷的重大轨迹承担幕/Arc 尺度，单元承担序列尺度，章内 scene card 承担场景尺度；章节继续作为发布与阅读边界，微观节拍由 chapter writer 展开。
- **场景编号容量**：`S01`–`S99` 是当前文件接口的编号范围。确实超出时交回章结构设计处理；编号数量本身不能判断章节节奏。
- 章卡的 `hook` 设计必须落到末场景的 `handoff` / 节拍方向上——章末钩子在编排层就位，不指望 writer 临场补。

**编排前选材**：物化的初始上下文供定位系列与本章问题；实体列表为空表示尚未取得人物和局部事实。结合当前卷纲条目、前章衔接与必要的角色目录、设定集索引，在写场景前将本章相关 characters / locations / items / threads / `worldbook_sections` 填入章卡，并选章级主 POV。已登记人物采用实际 `char_id`，一次性角色按上下文协议使用明确的 participant ID；章级 POV 不代表其他人物的知情范围。运行 `assemble_serial_context.py --work-dir <工作区> --chapter C####`，读取刷新后的上下文再编排。缺关键人物或事实时回对应来源补足，不能把缺资料解释为人物没有动机、关系或知识。

**编排中分开处理三种信息**：

- 已发生事实、人物当前处境与知情边界约束场景可能性。计划中的转折、未来揭示和章末结果保持计划身份。
- 场景作用、人物面对的压力、入场与离场变化说明本场为何存在；人物怎样应对需与其欲望、能力、关系和已知信息相容。发生冲突时修订场景设计或交回人物/系列来源，不能要求执行者同时兑现矛盾输入。
- 动作、物件、对白或叙述手法是候选实现。保留表达意图和决定性条件，让 writer 在这些边界内决定具体写法。

**定稿同步**：从场景清单核对章卡选材和主 POV，将 `scene_plan.scenes` 同步为当前场景 ID 列表；场景内容与呈现顺序的真值在 `phase5_scenes.yaml`。新增人物、实体或改变 POV 时，先补选材、装配并读取相关约束，再确认受影响场景。章卡内容实际变化后刷新 `serial_context.md`；内容未变且上下文仍有效时直接复用。交接前确保最终场景和实际使用的上下文一致。

非章 workspace → 本节不适用，按上方输入契约清单原样执行。

## Canon/design reference（设计时按需读取）

需要设计参考时，通过当前宿主正式入口加载 `design-doc-reference`，提供：

```
phase=5
genre=<系列或作品已经确定的主要类型>
signals=<JSON: 至少含 scene_count_target, key_scene_types, pov_pattern, risk_families 中能填的>
```

当前章的场景组织难点会影响参考选择时，可附临时自由文本 `narrative_problem`，说明需要解决的信息释放、跨线影响、时间呈现、道德压力或场景转折问题。它只服务本次检索。

调用成功 → Read `pipeline/references/phase5_design_ref.md`，只学习：

- **场景尺度的变化**：原作怎样让行动、知识、关系、价值或感知状态发生转折；
- **叙事组织证据**：信息、POV、时间或叙事线怎样进入和切换，结果改变了什么；
- **微观入口**：关键场景只取得压力方向、鸿沟位置和少量原文手艺，具体动作—反应由 chapter writer 展开。

先核实当前宿主的技能入口；缺少扩展包、KB 不可达或无匹配时，依据已取得的理论和作品输入继续设计，并如实记录本次参考缺项。已取得且仍适用的参考直接复用；不猜测已加载，也不虚构调用工具。

## inspiration_refs[] 字段

`inspiration_refs` 记录本场采用的 `pipeline/inspiration_ledger.yaml` 中 `type=pattern` 的 INS-* 灵感卡：

```yaml
scenes:
  - scene_id: S07
    reader_track: ...
    scene_tasks: [...]
    craft_carrier: ...
    inspiration_refs:               # optional
      - INS-001                     # 引用 ledger 中 type=pattern 的卡
      - INS-007
```

只保留改变本场设计决策的引用；多个引用承担相同作用时选最贴切者。没有适用灵感时省略字段。

**字段引用闭环 hard gate**（脚本见 `validate_phase5_r10.py`）：

对每个 `scene.inspiration_refs[]` 中的 INS-*：

- ledger 内必须存在该 INS-*
- 引用的卡必须 `type=pattern` 且 `status ∈ {accepted, bound}`
- 该 INS-* 的 `project_encoding[]` 至少存在一项满足：
  - `phase == 5`
  - `chapter_id == 本 chapter_id`，再匹配 `scene_id == 本 scene_id`
  - `adoption_kind ∈ {scene_carrier, reveal_carrier, structure_carrier, craft_carrier}`

字段不存在 → 不报错（向后兼容）；存在则必须闭环自洽。

## 复用已有编排

已有 `pipeline/phase5_scenes.yaml` 时，先核对它对应当前章和本次任务，再保留有效设计、补足缺口。来源作品的场景清单供理解事件与结构；当前章 `scenes` 只列本次待写场景，使用本章局部 S01 起编号。续写锚定此前已成立的状态，改编范围按作者已定要求执行。

## 执行步骤

### 1. 逐序列展开场景

**结构约束优先**：如果 Phase 0 的 `requirements` 中包含结构性约束（如"分为 5 章"、"4-5 个自然段"），以用户要求为主框架。

展开场景前读取 [output-schema](references/output-schema.md) 的字段与语义；已加载且有效时复用。对每个序列或当前章意图，设计其内部场景。每个场景需要：

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
- **conflict**：这个场景中对抗什么
- **value_start / value_end**：进入和离开时的关键叙事状态。戏剧行动关注价值处境，信息或观察场景可关注认识、关系与感知；状态保持时说明本场仍承担什么作用，不补造正负翻转。
- **reader_track**（必填）：本场读者跟随的主要问题、行动或感知变化。任务应服务这一焦点；并行或对照场景写清各线如何共同改变理解，不强压成单一人物目标。
- **scene_tasks**：本场需要完成的叙事变化与可选实现材料。每条使用 scene_task object，意图与候选的不同权限见下方判据。
- **handoff**：如何衔接到下一个场景
- **narration_style**：叙事腔调锚。取值 `close-third`（紧贴 pov 角色内心）/ `third-omniscient`（全知叙述者）/ `first`（第一人称）。

场景数量由序列的冲突复杂度决定，不预设。

## scene_task：表达意图与候选实现

`abstract_function`、`physical_carrier`、`reader_yield` 与 `rendering` 分别保留意图、候选、读者所得和展开尺度，完整格式由 output-schema 定义。`physical_carrier` 只在章编排已有贴切的动作、物件、声音、感官或叙述安排时填写，没有合适候选时写 `[]`。非空项用 `function_link` 说明它怎样服务 `abstract_function`；这项作用依据随候选进入 writer 的场景材料，使其能判断替换后是否仍成立。

大纲只预写会改变事件、人物、世界规则、主旨、压力或阅读节奏的候选。普通移动和操作由读者补完。用“紧张”或“氛围”保留动作时，`function_link` 写明具体压力怎样变化，例如噪声暴露位置、踪迹留下、伤势恶化、时间损失或选择空间缩小。该判据只约束大纲取材，chapter writer 仍可自然使用必要的衔接动作。

`reader_yield` 指读者由事件、证据或呈现取得的变化，不保证某种情绪反应。意图可以抽象；候选应说明它怎样承载意图。下面的行动只在“公开表态会付出实际代价”这一条件下成立：

```yaml
abstract_function: "人物维持中立的立场遭到公开选择的检验"
physical_carrier:
  - text: "会议记录递到面前，他在支持一栏签名"
    function_link: "署名将私下态度变为可追责的公开选择"
reader_yield: ["他接受了公开站队的代价，中立声明失去可信度"]
rendering:
  default: expand
  expand_only_if: "犹豫或他人反应改变他是否署名及其代价"
```

若签名只是例行签到，它只承担衔接，不能据此推出立场变化。尚未选定合适承载时写 `physical_carrier: []`；不要用端杯、停顿等动作填满字段。非空候选仍须填写有实际含义的 `text` 与 `function_link`。

完整字段、语义判据与历史字符串的读取规则见 [output-schema](references/output-schema.md)。

### 1bis. 因果顺序与呈现顺序

`scene_causal_chain` 记录事件依赖；`scenes[]` 的列表顺序是本章 writer dispatch 与 `draft.md` 的读者呈现顺序。章内编排可使用插叙、倒叙、并行线和多 POV，对同一事件从不同位置进入。跳转需要读者可感知的时间、地点、人物或物件锚点，并遵守 `serial_context.md` 的已发布事实与人物知识边界。

叙事结构由本章压力与近期连载节奏决定。线性顺序有效时保留；重复的入口、时间组织、视角排列或钩子形态削弱本章作用时，再针对问题调整。具有表达作用的重复形式可以延续。

### 2. 标注关键场景的节拍方向

关键场景需要明确转折机制时，标注 `beat_direction`——例如：
- 激励事件场景
- 每个序列的高潮场景
- 每个 Arc 的高潮场景
- 故事危机/高潮场景

`beat_direction` 是给 Phase 6 的提示，不是逐节拍设计。示例：
- "从信任走到背叛，鸿沟在老板拿出审计数据时裂开"
- "从安全感走到不可逆的被困感，罗辑发现面壁者身份不可撤销"

`beat_direction` 写清压力、期待与反应怎样改向；信息或母题驱动场景可写证据、对照或感知如何改变解释。承载已有明确设计时填 `craft_carrier`，具体实现仍可由 writer 在场景边界内选择。

其他场景通常由 writer 展开微观节拍，无需为了字段完整补写方向。

### 3. 设计张力曲线

重复同一种压力和反应会钝化读者（原文见 `references/mckee-scenes.md §张力设计`）。张力曲线描述哪种压力在何处接管、释放或改向，以及它怎样改变人物策略、信息状态、关系或选择空间。高低交替、整体上升和高潮前加速都是可用形状，由当前故事的因果与阅读效果决定。

### 4. 验证因果连接

按事件发生顺序检查行动与后果的依赖。呈现顺序中的相邻场景可以来自不同时间或叙事线；此时说明切换怎样改变当前追问、解释或压力，不能为满足“相邻必有直接因果”而虚构事件关联。

### 5. 非事件测试（所有 `spine_mode` 通用）

最终按开头的场景取舍判据核对实际作用。行动或认知变化需要可成立的前提与后果；等待、观察和余波需要说明其感知、关系或节奏作用。只重复相同结果且无其他作用时，删除或合并；`value_start` 与 `value_end` 的字面差异不作通过条件。

### 6. AI pattern 风险标注（必填显式声明）

每个 scene **必须**显式声明 `scene_card.prose_risk_contract.used`——写作层 AI pattern 预防的场景级触发开关。无风险场景也要写 `used: false`，**禁止字段 absent**（PostToolUse hook 会扫 phase5_scenes.yaml 每个 scene，缺 `used` → WARN）。

判断本场是否激活 contract：命中以下触发画像时设 `used: true`，否则 `used: false`：

- 高密度动作 / 搜寻 / 移动 / 调度场景
- 展厅 / 宴会 / 办公室 / 饭局等社交调度场景
- 高强情绪但角色克制不说破的场景
- 依赖物件 / 沉默 / 停顿 / 视线传递关系变化的场景
- 大量环境描写 / 氛围描写场景
- 上轮 review 已诊断出某 family 命中的同类场景
- 在场人物的 `voice_boundaries` 指出本场可能发生签名声音滥用时：`risk_families` 加 `signature_voice_overuse`，`positive_strategy` 说明哪些情境支持声音突出或收敛。`voice_gear` 可标提示，不替人物预排逐拍措辞；具体声音服从当下压力、表达目的与人物边界。

不写数字阈值（动作 N 次 / 对白 N 句之类）；按场景判断是否命中即可。

`risk_families` 填 `prose-craft/references/ai-cliche-patterns.md` 现有 family 名（F 类 snake_case 或 A-G/观察层中文短语都行）。字段语义 / 渲染契约 / 冲突兜底详见 [`references/output-schema.md`](references/output-schema.md) `## prose_risk_contract` 段。

## 输出

→ YAML 输出结构见 `references/output-schema.md`

Phase 5 交付物：`pipeline/phase5_scenes.yaml`（聚合 yaml），其 `scenes[]` 每元素是一个 **scene_card**（L2 逻辑单位），供 Phase 6 writer / orchestrator 调度消费。
逐角色 `role_views` 在 Phase 6 runtime 由 `role-brief-deriver` 派生，使用本章上下文与场景设计。

聚合 yaml 采用一种场景存储形态；张力与因果说明按设计需要填写，格式见 output-schema。

## 完成与交接

`pipeline/phase5_scenes.yaml` 落盘，并完成因果连接、非事件测试、字段闭环与风险声明检查后，本 skill 可交接。章 workspace 的选材、场景索引与所用上下文须和最终设计一致。下游 writer 读取 scene card，`role-brief-deriver` 依上下文协议派生各角色的 `role_views`。

## 常见错误

| 错误 | 后果 | 修正 |
|------|------|------|
| 视角或时间切换缺少锚点 | 读者无法判断何时、何地、谁在感知 | 在混淆点补时间、地点、人物或物件锚点 |
| 无实际设计作用仍逐场补 beat_direction | 重复预排正文实现 | 保留需要明确转折机制的场景提示 |
| 场景重复既有结果，行动、认识、关系、感知和节奏均无独立作用 | 拖延当前发展 | 删除或与相邻场景合并 |
| 用 `must_include` / `characters` / `setting` / `core_conflict` / `value_shift` 等禁用字段名 | 下游 schema 对齐失败 | 统一用权威字段名：scene_tasks / participants / location_time / conflict / value_start+value_end |

→ scene_tasks 的字段与完整语义见 [output-schema](references/output-schema.md)：保留意图，区分读者获得的信息与期待的情绪，候选承载可由 writer 调整。

→ 理论深度参考见 `references/mckee-scenes.md`
→ **承载模式参考**：[`prose-craft/references/novel-craft-patterns.md`](../prose-craft/references/novel-craft-patterns.md)（按需加载——A 类承载点 / B 类视角 / C 类高潮 / D 类人物 / E 类形态；设计 scene_card 的 `craft_carrier` / `beat_direction` 时可参考）
