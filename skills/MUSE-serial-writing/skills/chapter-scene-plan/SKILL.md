---
name: chapter-scene-plan
description: 连载章内场景编排。由 serial-chapter-writing 调用，从当前卷纲、章卡和系列上下文形成场景设计，完成选材与章卡同步；正文生成由 writer 负责。
---

# 连载章内场景编排

把当前章意图组织为人物可成立、能供 writer 实现的场景设计。产物是章工作区的 `pipeline/phase5_scenes.yaml`；本技能同时负责章卡选材与上下文同步，正文由 writer 生成，逐角色输入由 role-brief-deriver 派生。

开始时取得调用方给出的包根、作品根 `series_root`、章目录 `work_dir` 与 chapter_id，并加载本包[上下文协议](../serial-chapter-writing/references/context-contract.md)。`work_dir` 含本章 `chapter_card.yaml` 与 `pipeline/`；通过当前宿主支持的技能调用或文件读取取得依赖。

## 当前章输入与选材

| 输入 | 作用 |
|---|---|
| 当前卷纲 `series/volumes/V0N.yaml` 的本章条目 | logline、opened/closed 义务、本单元意图与前后依赖 |
| `chapter_card.yaml` | hook、主 POV、人物/实体/设定分册选材及场景索引 |
| `pipeline/serial_context.md` | 已确认创作锚、当前方向与未决问题，以及合时人物、事实、卷向和前章衔接 |
| 实际前章、角色目录、设定集索引与必要来源 | 定位本章需要的人物和局部事实，补上下文缺口 |
| 已有本章 `phase5_scenes.yaml` | 恢复或修订时保留当前有效设计，只改本次受影响部分 |

已有 Phase 0–4 文件只在包含本次需要且仍有效的设计时补读；章内编排使用上述系列资料即可。原作场景清单帮助理解事件与结构，本章 `scenes` 仅包含当前待写场景。

```text
本章意图与前章 → 章卡选材 → 装配并读取上下文
                                      ↓
                          场景作用、条件与呈现设计
                                      ↓
                 同步章卡；来源变化时刷新受影响设计
                                      ↓
                     phase5 → 场景卡与 role_view → writer
```

物化的初始上下文用于定位系列与本章；空实体列表表示尚未选材。按本章意图、前章衔接及必要索引，填写章卡 `recap_inputs` 的 characters / locations / items / threads / worldbook_sections，并选择主 POV。已登记人物使用真实 char_id，一次性功能角色按上下文协议使用明确 participant ID。

运行 `assemble_serial_context.py --work-dir <series_root> --chapter C####`，读取刷新后的上下文再设计。资料缺失不能解释成人物没有动机、关系或知识；影响本场成立的缺口先回对应来源。作者侧创作锚和当前方向约束设计，未决问题保持未定，角色所知按实际获知渠道另行判断。

## 场景作用与创作空间

麦基以人物欲望、行动、冲突和价值变化解释戏剧场景。MUSE 还让信息、母题和观察驱动的场景按其理解、关系、意义或感知作用组织；原著依据与项目扩展见[场景与编排](references/mckee-scenes.md)。

本场须有可指认的作用：推进事件，改变解释或关系，发展母题，形成观察、等待、余波或阅读节奏。删除后这些作用均不受损的重复材料可省略或并入邻场。信息重释、感知发展与稳定处境按其实际作用成立；价值标签的字面变化不作为取舍条件。

从人物现状、欲望、已知信息和限制推演压力、选择与后果。输入不能同时成立时修订场景设计或回交来源；动作、物件、对白和叙述手法作为候选，让 writer 选择具体写法。已发生事实、已确认必要结果与作者行为/披露禁界继续保留。

已有要求决定结构与强度，如作者指定章数或段落形式。场景数量由本章需要决定。插叙、倒叙、并行线和多 POV 可以改变呈现顺序；在可能混淆处安排读者可感知的时空或人物锚点。事件因果按发生顺序核对，跨线相邻场景可以由对照、追问或压力承接。

中段推进可由阶段成果连接：本场取得的条件使后续行动成为可能，完成标准也可随人物认识而深化。铺垫既可在后文被重新理解，也可作为已知条件延迟生效，分别保留解释变化或条件传递的过程。多位主人公各有追求，共同事件对各方可以产生不同结果；切换照看原线留下的关切与接入线的作用。需要推敲跨线传递、读者先知、同期补叙或分批收束时，按问题读[场景与编排](references/mckee-scenes.md#事件顺序与读者呈现)及其中案例；铺垫与后续作用的区别见[鸿沟、伏笔与分晓](references/mckee-scenes.md#鸿沟伏笔与分晓)。成果与联系仍写入现有场景结果、因果链和 handoff，单线及纯对照按自己的作用成立。

## 形成场景设计

写产物前读[输出 schema](references/output-schema.md)，字段完整定义与机械接口由它维护。每场保留：

- `scene_id` 使用本章局部 S01–S99；下游路径为 `pipeline/scene_{scene_id}/`，ID 自身不含 `scene_` 前缀。编号容量是文件接口，节奏由场景作用判断。
- `arc_id`、title、location_time、participants、pov 与 narration_style 提供归属、定位和叙述条件。主 POV 不代表其他人物的所知范围。
- conflict、value_start/value_end 与 reader_track 说明人物面对什么、读者跟随什么、进入与离开时处境或理解有何异同。状态保持时写清持续存在的作用。
- scene_tasks 保存必要叙事变化与可选实现；handoff 说明下一场或下一章怎样承接。章卡已确认的 hook 作用要在完整收束段中成立，可由末场或此前留下的有效未决问题承担。

本章确有披露安排时，以 `reader_track` 保留当前阅读焦点，以 `scene_tasks` 保存本场应成立的事实与发现，把需要保留的答案及实际释放条件写入 `omission_plan`；人物知识仍依自己的获知渠道判断。该字段也可保留一般省略或永久留白意图，无额外要求时省略。读者已知答案时，继续组织人物的发现过程、原因或代价。

### scene_task 的意图与候选

`abstract_function` 保存本场意图，`reader_yield` 说明读者通过事件、证据或呈现取得什么，`rendering` 提示展开尺度。意图可以抽象，读者所得不保证某种情绪反应。

已有贴切动作、物件、声音或叙述安排时填 `physical_carrier`；没有候选时 `[]` 合法。每项的 `function_link` 说明它怎样实现意图，并随场景卡交 writer，使其能判断替换后作用是否仍在。只预写对人物、事件、世界、表达或阅读节奏有实际贡献的候选，普通移动和操作由 writer 自然衔接。

例如，“在公开记录上署名”能把私下态度变成可追责的选择，其条件是公开表态确有代价；若签字仅为例行手续，就不据同一动作名称预设关系转折。使用“紧张”或“氛围”保留动作时，说明具体压力怎样变化或它怎样形成必要体验。

关键场景需要明确转折机制时填 beat_direction，说明压力、期待或解释怎样改向；其他场景的微观节拍由 writer 展开。已经选定某种承载方式时可填 craft_carrier。需要比较写法时按问题读取[承载模式参考](../prose-craft/references/novel-craft-patterns.md)，保留作用条件与 writer 的候选取舍权。

张力描述压力何时接管、释放或改向，以及它怎样改变策略、信息、关系或选择空间。依据本章因果与近期节奏组织曲线；持续、反复、上升或余波都可具有作用。分别考虑场内活动速度、场景展开长度和结果后的停留，具体详略留给 writer。

### 按具体风险提供表达指导

本场有明确表达风险时填写 `prose_risk_contract`，如既有反馈表明同类场景的调度动作反复结算、人物声音被同一签名表达覆盖。先说明风险形成的条件，再给有用的 positive_strategy；bad_shape_examples 只在能澄清判据时提供。

该对象可省略，也可用 `used: false` 表示未启用，writer 仍取得通用 craft。对象存在时 used 为布尔值，列表内容遵循 schema；启用并有内容时投影到 scene_card。动作密集、沉默、克制或环境描写本身不构成必须防治的错误，不要求每场补无风险声明。

已有声音边界提示本场可能滥用签名表达时，可记录 signature_voice_overuse 及其具体语境。voice_gear 仅作声音突出或收敛提示。family 参考本包 prose-craft 的判据；字段语义、渲染与条件冲突处理见输出 schema。

## 参考与采用

已有材料足够时直接设计。具体组织难点需要参考时，通过宿主正式入口加载 `design-doc-reference`，传 `phase=5`、当前 narrative_problem 和可用 signals；genre 使用该来源包认可的类型，未确定时省略，表达目标写入问题。读取本次有效的 `pipeline/references/phase5_design_ref.md`，理解原作的变化机制、组织证据与成立条件，再决定本章如何采用。缺少扩展、KB 或匹配材料时，依据现有理论与作品输入继续；必需的指定来源缺失具体回交。

`inspiration_refs` 只记录实际改变本场设计的现有 INS-*。章场共同绑定防止跨章同号误用：当前章 ledger 中相应条目须为 accepted/bound 的 pattern，project_encoding 须匹配 phase=5、本章 chapter_id、本场 scene_id 与采用类型。完整接口及允许的 adoption_kind 见输出 schema，机械核对由 `validate_phase5_r10.py` / `extract_scene_card.py` 执行。无采用项时字段可省。

## 同步与交接

按最终场景核对章卡选材、主 POV 与 `scene_plan.scenes`；呈现顺序和场景内容由 phase5 持有。新增人物、实体或改变 POV 时，先补选材、重新装配并读取，再确认受影响设计；未变且仍有效的上下文直接复用。

交付前核对必要作用与因果、来源绑定、字段可消费性及实际使用的上下文。依赖矛盾回对应负责人，其余已授权工作继续。把当前 phase5 交章编排者生成或更新既有 Phase 6 索引，再由场景提取器与派生器提供 writer 输入；本技能不生成正文或另建审计产物。
