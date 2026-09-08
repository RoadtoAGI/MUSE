# 连载系列工作区文件契约

本文档规定连载工作区 `works/<slug>/` 的持久文件、章卡与派生视图的路径、字段、不变量和兼容规则。场景、role_view 和 role_move 的字段分别由对应消费模块维护，本文保留路径与指针。各执行者的输入权限和加载时机见[上下文协议](../../serial-chapter-writing/references/context-contract.md)。可直接复制的持久文件模板见 `templates/` 目录。

## 目录树

```
works/<slug>/
├── series/                          # 持久设计层（series bible）
│   ├── series_state.yaml            # 跨 session 状态机
│   ├── story_bible.yaml             # 总纲：frozen 区 + intent 区
│   ├── genre_profile.yaml           # 类型档案（大纲期判定后冻结，写作期只读）
│   ├── worldbook/                   # 分域设定集（一册一文件；公理册冻结/机制册追加）
│   │   ├── index.yaml               # 分册注册表（装配脚本的切片与摘要行来源）
│   │   ├── power-system.md          # 示例：公理册
│   │   └── military-life.md         # 示例：职业域册（分册清单由类型档案实例化，非固定）
│   ├── volumes/                     # 卷纲，一卷一文件，滚动追加
│   │   └── V01.yaml
│   ├── digests/                     # 多级投影 rollup（运行态产物）
│   │   ├── V01.yaml                 # 卷级 digest：1 句 + 1 段
│   │   └── V01-U03.yaml             # 单元级 digest：1 段
│   ├── ledgers/                     # 三台账（append-only 真值源）
│   │   ├── threads.yaml
│   │   ├── world_facts.yaml
│   │   ├── facts_current.yaml       # 派生视图：脚本从台账重算，非真值源
│   │   └── characters/<char_id>/    # 角色传记账本目录
│   │       ├── persona.md
│   │       ├── snapshots/
│   │       │   ├── V00.yaml
│   │       │   └── V01.yaml
│   │       └── biography.yaml
│   ├── decisions/                   # 共创决策档案
│   │   └── D-0007.yaml
│   └── character-skills/            # 角色 runtime skill 包家目录（系列级，章 workspace 经符号链接消费）
├── chapters/                        # 章工作层（目录名与 series/volumes/ 卷纲区分，防呆）
│   └── V01/C0005/                   # 章 workspace = mini-run
│       ├── chapter_card.yaml        # 章卡：仅章级字段
│       ├── pipeline/                # 与既有 run 内部同构
│       │   ├── serial_context.md    # 章级作者侧上下文（编排前选材装配，相关输入变化时刷新）
│       │   ├── phase5_scenes.yaml   # 章内场景编排真值（物化时生成骨架）
│       │   ├── prev_chapter_tail.md # 前章尾窗（物化时按 prev 链自动产出）
│       │   ├── aigc_clearance.yaml  # AIGC 防治放行凭据（绑定 draft hash，发布 gate 核验）
│       │   ├── story-character-skills   # → ../../../../series/character-skills 符号链接（物化时创建）
│       │   ├── scene_S01/
│       │   │   ├── scene_card.md     # 作者侧场景投影
│       │   │   └── role_views/<slug>.yaml # 逐角色合时输入
│       │   ├── staging/scene_S01/<slug>_role_move.yaml # 可选角色行动候选
│       │   └── scenes/scene_S01.md ...
│       ├── draft.md                 # 章成稿
│       └── recap.yaml               # 两段式 recap
└── published/                       # 发布冻结层
    ├── V01C0001.md                  # 发布稿（展示态文件名）
    └── manifest.yaml                # 发布序（全序真值）+ revision 勘误记录
```

三个海拔：`series/` 持久设计层（跨卷跨章长期有效）/ `chapters/` 章工作层（mini-run，一章一目录，收束后内容转录进台账与 `published/`）/ `published/` 发布冻结层（append-only，只有 `manifest.yaml` 的 revision 通道可做文字级勘误）。`pipeline/scenes/` 目录段名是场景相关校验触发契约的一部分，章 workspace 内不可改名。

## ID 与追加协议

- **机器字段裸章号 canonical**：章号 `C0001`–`C9999`，在作品内唯一。章级机器字段（`opened_at`/`last_seen`、`prev_chapter`/`next_chapter` 链、`cursor`、`causal_edges`）使用裸章号，如 `C0012`；支持场景出处的 `at`/`established_at`/`learned_at` 可使用章号加场景号，如 `C0012S03`（场景号局部于章内，`^S\d{2}$`）。带卷前缀的复合形态 `V01C0005` 仅用于展示态发布文件名和标题，不进这些机器字段。
- **顺序由链不由号**：阅读顺序 = 卷纲 `chapters` 列表序 + `prev_chapter`/`next_chapter` 显式链；发布全序 = `published/manifest.yaml` 的 `entries[].published_seq`。禁止用编号做加减法推断前后章——章号乱序（后插入的章号数字比相邻章小）是合法形态，编号只承担唯一性。
- **追加动作**：开新卷 = 新增 `series/volumes/V0N.yaml`；追加章 = 卷纲条目 `chapters[]` 里 append 一项 + 物化对应 `chapters/V0N/C00NN/` 章 workspace；插章 = 在卷纲 `chapters[]` 列表中插入 + 修正前后项的链字段，不重排既有编号。因果关系由章 `recap.yaml` 的 `causal_edges` 承载（append-only 边表）；张力曲线按卷局部维护。一切追加动作不得触碰 `story_bible.frozen` 区或 `published/` 下已发布物。

## series/series_state.yaml —— 跨 session 状态机

**路径**：`works/<slug>/series/series_state.yaml`

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `work_slug` | 是 | 工作区目录名（`works/<slug>/` 的 slug） |
| `collaboration_mode` | 是 | `volume` \| `chapter`；session 内可切换 |
| `active_session.session_id` | 否 | 单写者 marker；无活跃写者时为 null 或省略 |
| `active_session.started_at` | 否 | ISO 时间戳 |
| `cursor.volume` | 是 | 当前所在卷 |
| `cursor.working_chapter` | 是 | 在写/在审的章（裸章号，如 `C0039`）；`published_head` 不入状态字段，从 `manifest.yaml` 推导 |
| `cursor.stage` | 是 | `breaking` \| `outlining` \| `drafting` \| `reviewing` \| `publishing` \| `summarizing` \| `volume_closing` |
| `pending.type` | 否 | 非空即有待用户决策；无待决时 `pending` 整段为 `null` |
| `pending.question` | 否 | 一句话决策问题 |
| `pending.options_file` | 否 | 候选方案文件路径 |
| `buffer.drafted_unpublished` | 是 | 已定稿未发布的章号列表（`published`/`buffer`/`outline` 三段式缓冲区的中段） |

**不变量**

- **单写者**：一个 `works/<slug>/` 同时只允许一个 active session 写入。入会时若发现未释放的 `active_session` marker（`session_id` 非本 session），停下向用户确认接管或退出，不静默继续写；正常离会由认领的外层入口调用 reconcile_series.py --release-session 释放同 ID marker；内部调用复用外层 ID，不能提前释放。
- **入会协议**：入口读 `series_state` → 单写者检查 → 有 `pending` 则复述决策问题（附 `options_file`）→ 无 `pending` 则从 `cursor` 续跑。入会必跑机器对账，恢复点由产物存在性推导（见下方恢复矩阵），不能只信 `stage` 字段——session 可能死在任意半途，包括发布事务中途。
- **推进不变量**：`cursor.stage` 仅在该阶段产物完整落盘后推进（至少一次语义）；重入时以产物存在性作为断点判据，缺什么补什么。
- **缓冲区纪律**：`published`（已收录进 `published/`）/`buffer`（`drafted_unpublished` 列表内，定稿未发布）/`outline`（卷纲条目仍是 `status: outline`）三段。重写 buffer 中段的章时，其后 buffer 章一并降回 outline，或由用户显式声明保留；`published/` 内容永不因此改动。共创改向只作废 `outline` 段——已定稿的 buffer 章不因改向被作废；共创决策点打在 buffer 头部之前。

**入会恢复矩阵**（chapter 级；按产物存在性推导断点，不单信 `cursor.stage`）：

| `recap.yaml.deltas` | 台账已转正 | `published/` 文件存在 | `manifest.yaml` 条目存在 | 判定与动作 |
|---|---|---|---|---|
| 有 | 有 | 有 | 无 | 发布事务死于登记步：只补 `manifest.yaml` 登记 |
| 有 | 有 | 无 | 无 | 死于拷入 `published/` 之前：补拷入 + 登记两步 |
| 有 | 无 | 无 | 无 | 死于台账转正之前：从校验转正步整段重跑 |
| 有 | 部分转正 | 无 | 无 | 死于台账转正过程中：按幂等续跑转正 + 拷入 + 登记（台账 append 以来源 `chapter_id` + 条目序判重，已转正条目跳过） |
| 无 | — | 无 | 无 | 在写常态：章 workspace 已物化但发布事务尚未开始，无需恢复动作 |
| 任意缺失 | — | — | **有** | **硬失败**：`manifest.yaml` 已可见该章但链路残缺，停下请求用户确认，禁止继续写 |

**矩阵作用域**：只评估事务窗口内的章——已物化章 workspace 的章，或在 `buffer.drafted_unpublished` / `cursor.working_chapter` 内的章。`manifest.yaml` 已登记但章 workspace 整体不存在的章，是接管导入或发布后归档清理的正常形态，按已发布归档对待，不判硬失败。

**缺字段 fallback**：若既有 `series_state.yaml` 缺 `active_session` 段，按"当前无活跃写者"解释；缺 `pending` 段按"无待决"解释；新生成产物必须显式写出 `cursor` 全部子字段。

## series/story_bible.yaml —— 总纲

**路径**：`works/<slug>/series/story_bible.yaml`

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `frozen.premise` | 是 | 一句话前提 |
| `frozen.protagonist_want_need` | 是 | 人物的自觉欲望及有依据时的内在需要 |
| `frozen.world_ceiling` | 是 | 世界观全图与力量天花板；各卷只揭示、不修改 |
| `frozen.power_system_pyramid` | 否 | 力量体系金字塔骨架（若题材适用） |
| `frozen.spine_direction` | 是 | 主线方向与终点意象——方向性承诺，不是高潮场景设计 |
| `frozen.creative_anchors.title` | 是 | 作品名 |
| `frozen.creative_anchors.core_value` | 是 | 核心价值轴（正负极；全书叙事增量围绕它） |
| `frozen.creative_anchors.primary_drive` | 是 | 主驱动模式，enum: `desire \| information \| motif \| mix` |
| `frozen.creative_anchors.controlling_idea` | 是 | 主控思想一句（价值 + 因果） |
| `frozen.creative_anchors.unique_angle` | `primary_drive: mix` 时必填 | 独创角度；mix 时写清组成驱动及关系 |
| `frozen.creative_anchors.style_directives` | 否 | 作品级风格指令 |
| `intent.current_thrust` | 是 | 当前已确认的后续方向；未定可为空，不固定覆盖卷数 |
| `intent.open_questions` | 否 | 悬置的全书级 dramatic question 列表 |

**不变量**

- `frozen` 区的修改**唯一合法通道**是 `frozen_amendment` 决策：用户在决策点显式批准，落 `series/decisions/D-<seq>.yaml`（`kind: frozen_amendment`），获准修订先登记对应凭据再写入。lint 仅在有可比基线时识别差异，执行者仍须核对当前授权。已有世界边界内的揭示和细化沿原约定处理。
- 各卷只从 `frozen.world_ceiling` **揭示/细化**，不加层——卷纲 `world_reveal_plan` 条目的 `from_ceiling` 锚不上现有天花板即视为触碰天花板，须走 `frozen_amendment`。
- `intent` 区可随卷推进持续改写，不受 `frozen` 区写保护约束。

**缺字段 fallback**：`frozen.power_system_pyramid` 缺省按"本作品无独立力量体系分级"解释；`intent.open_questions` 缺省按空列表解释；既有工作区缺 `frozen.creative_anchors` 时各锚字段按未设置解释——消费方（outline-validation 的相关设计疑点、章级修订的设计意图对照等）对应检查降级跳过、不阻断；新生成产物两个顶层区与 `creative_anchors` 都必须存在。

总纲字段表约定持久键；初始化模板可以保留未决空值。冻结前确认正在委托创作所需的方向与边界；接管或尚未决定的 controlling_idea / spine_direction / current_thrust 不由模型自动补成作者结论。

## series/genre_profile.yaml —— 类型档案

**路径**：`works/<slug>/series/genre_profile.yaml`（大纲阶段类型判定后冻结；写作期只读）

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `substrate` | 是 | 世界底座，唯一；值域 = genre-packs 名（`history` \| `xianxia` \| `infinite`）或 `generic`（无专属插件的通用底座） |
| `engine.primary` | 是 | 爽点引擎主槽（如 `穿越` / `系统` / `副本闯关`） |
| `engine.secondary` | 否 | 副槽；缺省 `null` |
| `mainline_type` | 是 | `事业线` \| `关系线` \| `双线`——**声明位**：仅记录类型坐标，不驱动任何机制；消费形态待关系主导路径接入后再接 |
| `tags` | 是 | 元素标签列表——**声明位**：供对标反查/参考检索作过滤 key，受控词表待建 |
| `pacing_contract` | 是 | `免费快节奏` \| `付费标准` \| `慢热精品`——项目节奏配置；具体要求依作者确认，不由档名推导转折或表达配额 |
| `benchmark` | 是 | 对标作品列表（三轴反查 + 灵感检索用；可为空列表） |
| `substrate_config` | 否 | 底座专属配置 mapping，键由对应 genre-pack 声明（如写实系 `history_coupling: 正史贴线\|分岔架空\|架空借壳`；奇幻系 `realm_lineage`；无限流 `hub_space_mode`） |

**不变量**

- 判定后冻结：修改唯一合法通道 = `kind: frozen_amendment` 决策且 `consumed_by` 含 `profile:genre`；无凭据的改动由结构性 lint 拦截（同 `story_bible.frozen` 写保护模式）。
- `substrate` 决定下游装载：worldbook 分册模板清单、角色状态 `extensions.<substrate>` 字段族、台账枚举扩展词表——定义随包住 `references/genre-packs/<substrate>.yaml`。
- 声明位纪律：`mainline_type` / `tags` 不允许实施任何"按它分支"的机制——它们只是坐标记录，防实施期擅自发明消费逻辑。

**缺字段 fallback**：整个文件缺失（V1 既有工作区）按"通用缺省"解释——substrate=`generic`、pacing_contract=`付费标准`、无扩展词表，消费方全部按通用核心行为运行，lint 只 WARN 不阻断；`substrate` 为 `null`（init 后尚未判定）按"类型未判定"解释，大纲 S1 判定前合法。

## series/worldbook/ —— 分域设定集

**路径**：`works/<slug>/series/worldbook/`——`index.yaml` 分册注册表 + 一册一 `.md` 文件（文件名 ASCII kebab-case = `section_id`）。

**index.yaml 字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `sections[].section_id` | 是 | 分册 ID（= 文件名去 `.md`）；章卡 `recap_inputs.worldbook_sections` 按它声明切片 |
| `sections[].file` | 是 | 分册文件名（本目录内相对） |
| `sections[].title` | 是 | 分册中文标题 |
| `sections[].mutability` | 是 | `axiom`（公理册，冻结）\| `append`（机制册，存在性冻结、内容延迟物化） |
| `sections[].summary_line` | 是 | 一句话摘要——装配脚本恒注的"设定集地图"行 |

**分册文件形态**（两段式，供 writer/checker 消费）：

1. **硬约束表在前**——该域的规则/参数/清单（表格或条目列表，带原文/设计出处锚）；
2. **素材库在后**——以 `## 素材库` 为标题，承载质感素材、可选细节、参考片段；装配器据此切分，标题前才是硬约束部分。

**不变量**

- **双层冻结纪律**：`axiom` 册（力量/社会公理、主神空间规则书、天花板细则）大纲期建成后冻结——改动唯一通道 = `frozen_amendment` 决策且 `consumed_by` 含 `worldbook:<section_id>`；`append` 册只允许**追加小节**（新地图/新势力细节随卷揭示落位，挂 `world_reveal_plan` 锚），不改写既有内容——追加不矛盾由连续性校验把关。
- **真值分工**：worldbook 承载**静态设定**（规则/体系/组织/地理/日常质感/年表）；`world_facts.yaml` 台账承载**运行期演化 delta**（易主/获得/扩散/errata）。多属性实体（装备/法宝）的参数表住 worldbook 对应分册的硬约束表；其履历与断章状态由台账 per-entity 过滤呈现（见 world_facts 一节的 dossier 视图注）。
- **分册即读取单位**：writer 按章卡 `recap_inputs.worldbook_sections` 声明加载分册切片；恒注例外仅 `index.yaml` 的 `summary_line` 全表（设定集地图）+ 公理册硬约束表（对齐"力量金字塔恒注"既有语义）。
- 分册从对应 genre-pack 的 `worldbook_sections` 选取，按作者已采用的世界机制与当前缺口建册；无需为类型标签建齐全套。已选规则所需的边界与来源必须可达。旧 pack 的 required 标记仅作设计提示，当前脚本不据此校验分册缺失。

**缺字段 fallback**：`worldbook/` 目录或 `index.yaml` 缺失（V1 既有工作区）按"本作品无分域设定集"解释——装配脚本跳过设定集段，仅保留 `story_bible.frozen` 短字段注入；`recap_inputs.worldbook_sections` 声明了但 index 无对应条目 → 装配 WARN + 跳过该项。

## series/volumes/V0N.yaml —— 卷纲

**路径**：`works/<slug>/series/volumes/V0N.yaml`（一卷一文件，`chapters` 列表滚动追加；只物化当前卷）

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `volume_id` | 是 | 如 `V02` |
| `status` | 是 | `planned` \| `active` \| `closed`（`closed` 即冻结） |
| `protagonist_delta.from` / `.to` | 是 | 卷首/卷末的处境、关系、认识或性格；稳定人物可保持立场并改变外部局面 |
| `volume_question` | 是 | 本卷 dramatic question，卷内必答 |
| `tentpoles[].beat` | 是 | 节拍描述 |
| `tentpoles[].value_shift` | 是 | 价值转变 |
| `tentpoles[].anchor` | 是 | `unresolved`（规划时悬空）或裸章号（物化后锚到具体章，如 `C0012`） |
| `world_reveal_plan[].reveal_id` | 是 | 稳定标识，如 `W-V02-01`；供章级 `recap.yaml` 的 `fact_deltas.source_reveal_id` 回指、供卷收束兑现核查引用 |
| `world_reveal_plan[].reveal` | 是 | 新地图/新势力/新规则条目描述 |
| `world_reveal_plan[].from_ceiling` | 是 | 对应 `story_bible.frozen.world_ceiling` 的锚点；锚不上即触碰天花板，须走 `frozen_amendment` |
| `world_reveal_plan[].status` | 是 | `planned` \| `fulfilled` \| `carried_to_next_volume` \| `dropped_by_decision` |
| `world_reveal_plan[].planned_at` | 否 | 预期揭示锚：单元 `U##` 或裸章号。有明确后续锚点时保留披露安排；已过锚点但仍 planned 时核对事实与计划。缺锚或无法定位时回查作者原意，不自动推定本章禁令 |
| `narrative_lines[].line_id` | 否 | 持续叙事线稳定 ID，格式 `LINE-*`；只有两条以上叙事线且章编排需要区分时生成 |
| `narrative_lines[].description` | `narrative_lines` 存在时 | 本线由谁或什么问题推动 |
| `narrative_lines[].active_at` | `narrative_lines` 存在时 | 该线活跃的卷内单元 `U##` 或裸章号 `C####` 列表；`U##` 覆盖该单元全部章节 |
| `chapters[].chapter_id` | 是 | 裸章号 |
| `chapters[].unit` | 是 | 卷内单元分组，如 `U03`（单元编号卷内局部，跨卷同名不串；单元语义按类型单元模板：境界段/战役/副本） |
| `chapters[].logline` | 物化前必填 | 保留本章人物、情境、行动及后果；`status: outline` 可后填，由章节撰写侧滚动编排，开卷 breaking 只需卷级框架 |
| `chapters[].hook_type` | 物化前必填 | `悬念` \| `反转` \| `情绪炸弹` \| `信息投放`（+ 类型档案扩展值）；`status: outline` 条目可后填 |
| `chapters[].opened` | 否 | 本章开启的伏笔（`threads.yaml` 的 `thread_id` 列表） |
| `chapters[].closed` | 否 | 本章回收的伏笔 |
| `chapters[].status` | 是 | `outline` \| `drafted` \| `published` |

**不变量**

- **world_reveal_plan 四态 + reveal_id**：每条揭示条目在卷收束时必须归入 `fulfilled`（须能列出对应 `fact_id`/`chapter_id`）、`carried_to_next_volume`、`dropped_by_decision` 三态之一；存在仍为 `planned` 的条目即阻断卷关闭。`reveal_id` 是贯穿全周期的稳定标识——章级 `recap.yaml` 的 `fact_deltas[].source_reveal_id` 用它回指"这条事实是兑现哪个揭示计划产生的"；卷收束核查据此比对 `world_reveal_plan` 与已入账事实是否对得上。
- **threads 双向闭合**：已发布章的 opened/closed 与台账的 opened_at/payoff 相互对应；发布预检通过 `--pending-chapter C####` 将当前 recap 的 thread_events 只读投影后比较，转正使用同一转换逻辑。未来 outline 的 opened/closed 保持计划，不能要求先入账；已入账事件仍须能回指实际卷纲条目。
- `tentpoles[].anchor` 从 `unresolved` 到裸章号的回填只发生在对应章物化时，不得提前手工填入未物化的章号。
- `status: closed` 的卷视为冻结——其 `chapters[]` 与对应已发布章卡不再允许改动（矛盾走 `world_facts.yaml` 的 `errata` 通道）。
- `narrative_lines` 负责军事线、政治线、关系线等持续剧情线的章级定位；`threads.yaml` 继续负责伏笔、悬线、承诺和谜团生命周期。跨线因果写入 tentpole、单元或章设计，不增加交叉表。

**缺字段 fallback**：`chapters[].opened`/`closed` 缺省按空列表解释（本章不涉及伏笔开启/回收）；`world_reveal_plan` 缺省按"本卷无新增世界揭示"解释（卷收束核查该字段视为空数组，直接通过）；`narrative_lines` 缺省按单线或本卷无需章级区分解释。

## chapters/.../chapter_card.yaml —— 章卡

**路径**：`works/<slug>/chapters/V0N/C00NN/chapter_card.yaml`（物化时由对应卷纲条目展开生成；只承载章级新字段，章内场景编排真值另住同目录 `pipeline/phase5_scenes.yaml`）

本章 `logline`、`unit`、`opened`、`closed` 等意图从对应卷纲的 `chapters[]` 条目读取；章卡不另存一份同义大纲。编排以本章条目为入口，并结合选材后的上下文形成场景设计。

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `chapter_id` | 是 | 裸章号 |
| `prev_chapter` | 是 | 前一章裸章号；首章为 `null` |
| `next_chapter` | 是 | 尚未物化下一章时为 `null`，物化下一章时回填 |
| `hook.type` | 是 | 章末钩子类型 |
| `hook.design` | 是 | 章末实际承接的处境、问题或余波，供章级审阅对照 |
| `hook.strength` | 否 | `强` \| `中` \| `弱`——启发式标注，供同型连击/强弱交替 review 信号，缺省按"未标"解释，不做机器阈值 |
| `pov` | 是 | 本章主视角角色 `char_id`；场景视角以 `phase5_scenes.yaml` 为准。该字段不用于删去作者上下文中其他角色所需的秘密或事实 |
| `recap_inputs.characters` | 是 | 本章涉及、需要取得人物资料与相关事实的角色 `char_id` 列表；包含规划所需的非 POV 角色 |
| `recap_inputs.locations` | 是 | 同上，地点 |
| `recap_inputs.items` | 是 | 同上，物件 |
| `recap_inputs.threads` | 是 | 同上，伏笔 `thread_id` |
| `recap_inputs.worldbook_sections` | 是 | 本章触及的设定集分册 `section_id` 列表——writer 按需读取设定集的声明源 |
| `scene_plan.scenes` | 编排后回填 | 章内场景 `scene_id` 索引；以 `pipeline/phase5_scenes.yaml` 为真值回填，编排改变场景集合时同步刷新 |

**不变量**

- `recap_inputs` 是台账切片过滤 key 的**唯一来源**——本章写作与审阅注入台账时只按这里声明的 characters/locations/items/threads 过滤，未点名的条目不注入（力量体系金字塔与 `frozen` 区护栏级规则例外，恒定注入不走此过滤）。
- `prev_chapter`/`next_chapter` 是显式前后链，不由章号数字推算；实际发布全序另取 manifest 的 published_seq。
- 钩子字段（`hook.type`/`hook.design`）非空是结构性校验项。正文末段是否兑现既定承接，按实际处境和后续关系判断；情绪收束、阶段完成、开放余波与悬念均可成立。
- **编排前选材与装配**：物化提供初始章目录和通用上下文。章内编排前，读取对应卷纲的本章条目、前章衔接及人物/世界册索引，填写已有 `recap_inputs` 与 `pov` 后运行装配。规划中的人物、实体或设定范围变化时更新章卡并刷新，避免先在缺人物资料的条件下决定其行动。编排后回填场景索引；进入派生和写作前使用当前有效的装配。
- **刷新范围**：人物、事实、场景来源或章卡变化影响输入时，刷新受影响的 serial_context、场景投影与 role_view；已取得且仍有效的材料直接复用。`serial_context.md` 早于 `chapter_card.yaml` 是过期信号，缺失或明确过期时阻止依赖它的写作；mtime 通过不证明实际输入已正确更新。

**缺字段 fallback**：`next_chapter` 缺省即视为 `null`（下一章尚未物化）；旧产物缺 `recap_inputs` 某一子列表（含 `worldbook_sections`）时，装配按空列表处理，规划实际需要该类材料时补选后刷新。缺 `pov` 保持未指定，由编排者按实际视角补齐，不用人物列表首位猜测角色认知；场景视角另由场景设计确认。缺 `scene_plan` 按“章内编排尚未完成”解释；缺 `hook.strength` 按“未标”解释。

## chapters/.../pipeline/ —— 章级上下文与场景输入

以下文件是持久设计、台账和正文的派生消费面，不成为新的来源权威：

| 路径（相对章 workspace） | 职责与字段权威 |
|---|---|
| `pipeline/serial_context.md` | 装配作者侧的系列/卷/本章意图、设定、事实、人物与前章衔接，供编排、派生器、writer 和审阅消费；信息权限见[上下文协议](../../serial-chapter-writing/references/context-contract.md) |
| `pipeline/phase5_scenes.yaml` | 当前章的完整场景设计，字段见[章内编排 schema](../../chapter-scene-plan/references/output-schema.md) |
| `pipeline/scene_{scene_id}/scene_card.md` | 从当前场景设计投影给 writer，保留必要因果、结果及候选材料的作用依据 |
| `pipeline/scene_{scene_id}/role_views/{slug}.yaml` | 每角色一份合时人物输入，六字段由[人物派生器](../../role-brief-deriver/SKILL.md#输出契约)定义；writer 读取当前参与者的 views，actor 只读本人 view |
| `pipeline/staging/scene_{scene_id}/{slug}_role_move.yaml` | 可选、逐角色的行动候选，字段由[排练输出约定](../../character-rehearsal/references/output-schema.md)定义；writer 只读本次 dispatch 明示的文件，空 moves 合法 |

`serial_context` 中的事实可超出某一角色的知识。装配按选材与来源窗口提供作者资料，不用主 POV 过滤掉其他人物所需事实；派生器根据每场故事时点和实际获知渠道生成各角色 view。章主 POV 缺失不赋予第一名人物知情权，多个角色的 view 也不能相互补齐隐藏知识。

人物文件键使用台账 `char_id` 或明确映射，场景一次性角色使用设计中稳定的 participant ID；绑定规则见上下文协议。旧 `role_briefs.md` 和 `*_rehearsal.md` 保持原样，新链路从来源重新派生，不机械换名、自动读取或转成新 schema。

## series/ledgers/threads.yaml —— 伏笔/悬线台账

**路径**：`works/<slug>/series/ledgers/threads.yaml`（append-only：运行态变化只追加不回写）

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `threads[].thread_id` | 是 | 如 `T-017` |
| `threads[].kind` | 是 | `伏笔` \| `悬线` \| `承诺` \| `谜团` |
| `threads[].opened_at` | 是 | 裸章号 |
| `threads[].statement` | 是 | 开启时已成立的问题；后续信息按章进入 `events`。初始提问须结合窗口内事件判断是否仍未解 |
| `threads[].intended_payoff.horizon` | 新创 open 候选必填 | 当前获准的预期回收卷；接管无原作者计划时 `intended_payoff` 可为 null，已发生回收记入事件 |
| `threads[].intended_payoff.note` | 否 | 怎么收的当前设想 |
| `threads[].tier` | 否 | `短线` \| `中线` \| `长线`——伏笔层级（回收周期与"超期未重提"review 信号按层分档；启发式，不做机器阈值） |
| `threads[].intended_payoff.planned_close` | 否 | 章级预期回收锚（裸章号）——比 `horizon`（卷粒度）更细的可选锚；缺省用 `horizon` |
| `threads[].status` | 是 | `open` \| `advanced` \| `paid` \| `abandoned` |
| `threads[].events[].at` | 是 | 裸章号 |
| `threads[].events[].kind` | 是 | `advance` \| `payoff` |
| `threads[].events[].note` | 是 | 推进/兑现说明 |

> 最近重提章不设冗余字段——由 `events` 内最后一条 `advance` 事件推导（投影可从事件层重算的，不入字段，见文末写入职责）。

**不变量**

- **双向闭合校验**：卷纲条目 `opened`/`closed` 必须与本台账条目双向引用一致，两侧同用裸台账 ID 与裸章号，单向悬空即校验失败（详见卷纲一节）。
- `intended_payoff.horizon` 超期未回收是卷 breaking 时的提醒信号（启发式提示，不阻断）。
- `events` 只能追加，不能改写或删除既有事件；顶层 `status` 表示当前汇总态。注入时区分初始 `statement`、来源窗口内已发生的推进/兑现事件与当前设计的回收方向。历史来源窗口不直接反投最新 `status`；后续事件已解决的部分不能因初始 statement 再次成为未知。

**缺字段 fallback**：有回收计划时，`note` 缺省表示仅锚定回收卷；接管没有计划时保持 null。创作侧发布新的 open 候选须带获准的 `horizon`。

## series/ledgers/world_facts.yaml —— 世界事实台账（含 facts_current.yaml 派生视图）

**路径**：
- 真值源：`works/<slug>/series/ledgers/world_facts.yaml`（append-only）
- 派生视图：`works/<slug>/series/ledgers/facts_current.yaml`（脚本从台账重算生成，**非真值源**，可随时丢弃重建，不手工编辑）

**字段表**（`world_facts.yaml`）

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `facts[].fact_id` | 是 | 如 `F-0142` |
| `facts[].entity` | 是 | 人物使用角色目录 `char_id`（所有 kind 均如此）；物品、地点、组织等使用与 `recap_inputs.items/locations` 对应的稳定实体名 |
| `facts[].kind` | 是 | 通用核心值 `item` \| `rule` \| `state` \| `geo` \| `org` \| `ability` \| `secret` \| `relation`；类型档案可按 genre-pack `enum_extensions` 追加扩展值（如奇幻系 `duel`）——扩展值之外的 kind 由 lint WARN 提示，不阻断 |
| `facts[].attribute` | 是 | 属性名，如"持有者" |
| `facts[].value` | 是 | 本时点成立的属性值，保留适用条件及行动的计划、进行或完成状态 |
| `facts[].established_at` | 是 | 来源章或场景锚，如 `C0005` / `C0005S02`；表示何处已确立该事实，故事中的发生时间按原文判断 |
| `facts[].supersedes` | 否 | 状态演化：指向被本条目压住的旧 `fact_id`（新条目压旧条目，不改旧条目内容） |
| `facts[].limitation` | `ability`/`rule` 必填 | 能力/规则类必填的边界描述；非空才合法 |
| `facts[].origin` | 是 | `normal` \| `errata`（`errata` = 发布后矛盾修正，只约束未来章，不改已发布物） |
| `facts[].status` | 是 | `active` \| `retracted`（`retracted` = 误入账作废，不删除原条目） |
| `facts[].retracted_by` | `retracted` 时必填 | 触发作废的 decision/复核事件 ID |
| `facts[].retraction_reason` | `retracted` 时必填 | 一句话作废理由 |
| `facts[].note` | 否 | 可选备注 |
| `facts[].known_by` | 仅 `kind: secret` | 同一秘密内容扩散时累计保留仍成立的既有记录；内容改变需另判谁知新内容。获知证据表：`[{char_id, learned_at}]`；`learned_at` 为对应人物获知的章或场景锚，不能由事实确立锚代填 |

**来源窗口与角色知情**：发布序及当前 `prev_chapter` 链限定可读取的来源；装配过滤晚于该窗口的 `established_at` 和 `known_by[].learned_at`，并在作者事实段保留可用来源及获知锚。无法定位的获知记录不作为已知证据。`known_by: []` 表示没有登记可用获知依据，不表示事实不存在；普通事实没有 known_by 也不表示人人知道。场景编号与发布顺序不能决定倒叙的故事时间，同章获知也不等于入场已知；派生器按实际人物、故事时点和正文中的获知渠道进一步过滤。

**入账粒度判据**：记录跨章持久且影响后续判断的状态，如装备易主、能力变化、规则揭示、秘密扩散、关系变化。一条记录须有共同的生效时点与条件，不同时点成立的独立事实分条；同一属性的后续变化用 `supersedes`。场内瞬态留在 `recap.summary` 与正文。

**人物标识**：章卡 `recap_inputs.characters`、`pov`、事实 `entity`、关系对方与 `known_by[].char_id` 沿用同一 `char_id`。显示名在 persona 的 `name` 中记录。存量姓名仅在明确的人物字段中按唯一、精确匹配解析：章卡人物、关系双方与知情者；旧 persona 无 name 时只以完整一级标题作匹配，不拆标题、不猜别名、不改原账本。其余事实的 entity 可能是同名物品或地点，需在来源确认后使用人物 ID，装配器不据姓名猜主体。同名角色或同一 ID 同时点名为人物和非人物时需显式消歧；无关条目的旧姓名不阻断当前章。接管可只为活跃人物蒸馏角色目录，其他关系方仍保持既定 ID，无需为字段检查补造角色资产。

**`kind: relation` 行约定**（人物关系的结构化归宿；复用 EAV 四元组，不开新账本形态）：`entity` = 发起方 `char_id`、`attribute` = `relation:<对方 char_id>`（有向——A 视 B 与 B 视 A 是两行，允许不对称）、`value` = 当前表面关系态、`note` 承载暗层张力/债务方向；演化走 `supersedes`、出处走 `established_at` 章锚，与其余 kind 同语义。最新关系可从 `facts_current.yaml` 按 `attribute` 前缀取得；历史关系须先按来源窗口筛选原台账，再结合故事时间定位实际关系状态。CP 关系对的独立建模留待关系主导路径接入时定案，本版不实现。

**多属性实体 dossier 视图**（装备/法宝/资产的 per-entity 聚合）：静态参数表住 worldbook 对应分册的硬约束表（如装备册）；运行期履历 = 台账按 `entity` 过滤的条目序列（含 `supersedes` 链与最新态）。二者合并呈现即"参数表 + 履历 + 断章状态"的 dossier——是**读取视图不是新真值源**，需要时由脚本按 entity 聚合生成，不手工维护。

**facts_current 三步重建算法**（唯一解释，脚本据此重算 `facts_current.yaml`）：

1. 取全部 `status: active` 行为 `active_rows`；
2. **仅从 `active_rows`** 的 `supersedes` 字段收集 `suppressed_ids`（`retracted` 条目的压旧边随之失效，不参与收集）；
3. 输出 `active_rows − suppressed_ids`。

推论：retract 一个已被某条 `active` 新事实压住的旧条目，对视图无效果（该旧条目本就已被压住、不在输出里）；retract 当前的 superseder（含 `errata` 条目）会使被它压住的旧事实重新出现在视图里——若不希望恢复旧状态，应追加一条新的 `active` 修正条目，而不是仅 retract 当前 superseder。

**不变量**

- 装备/招式/战力等状态演化走新条目 `supersedes` 旧条目，保留旧条目及来源；事实演化可据此追踪。完整历史状态仍取决于来源锚与修正时间是否可用。
- 误入账走 `ledger_tools.py retract`：保留原事实内容与 fact_id，在该条目记录 `status: retracted`、`retracted_by` 和 `retraction_reason` 后重建视图；不复制同 ID 事实或删除原条目。普通状态演化仍追加新事实并用 supersedes 关联。
- 发布后发现矛盾不改已发布物，立 `origin: errata` 条目（可 `supersedes` 旧事实），只约束未来章。
- `facts_current.yaml` 是最新视图，服务当前续写与当前态校验。较早来源窗口的装配读取原台账，先按 `established_at` 筛选可用来源，再仅用窗口内有效条目的 `supersedes` 压旧；不能先用最新条目删掉历史事实再裁剪。存量 retract/errata 缺少完整发生时间时，不承诺历史重放；涉及该事实的历史场景回读原文，不将最新修正反投过去。

**缺字段 fallback**：`facts[].supersedes` 缺省按"无前序条目"解释；`facts[].limitation` 仅当 `kind` 为 `ability`/`rule` 时必填，其余 `kind` 缺省按"不适用"解释；`known_by` 仅 `kind: secret` 需要，其余 `kind` 缺省按"无信息差表"解释。

## series/ledgers/characters/<char_id>/ —— 角色传记账本

**路径**：`works/<slug>/series/ledgers/characters/<char_id>/`，含三类文件：

- `persona.md`：最早有证据的人格基线（声音/欲望/判断倾向）；后续身份、关系与人格变化按卷记入快照，不回写早期基线。新文件用 YAML frontmatter 记录 `name: <显示名>` 与 `through_chapter: C####`，截止章不得晚于首份快照，正文只使用该范围证据。证据稀少可写短基线。装配器按实际发布序决定是否加载，去除 frontmatter 后供给正文；合时基线可早于整卷快照供给。新作开工设计用 `through_chapter: null` 且必须有 V00 快照；存量文件缺截止字段时，仅最新续写兼容读取，历史时点略过并提示。
- `snapshots/V0N.yaml`：卷级快照，`extends` 前一卷快照、只记 delta（通用四键 `state` / `relationships` / `capabilities` / `voice_shift`）；`V00.yaml` 是新作开工设计投影；接管从首个实际出场卷起链，可无 V00、首份 extends 为 null。可选 `through_chapter` 标记实际已发布覆盖截止章（含部分卷）；旧包缺字段时按卷已发布章推定，无法确定则不注入。上下文读取 persona 及按 extends 从早到晚的链，不能只读末份 delta；晚于当前章的快照和经历不进入上下文。**类型扩展**：快照可含 `extensions.<substrate>` 命名空间段（字段族由 genre-pack 声明——写实系 `status_ladder`（rank/position/assignment 三分列）+ `promotion_history`（带章锚）+ `political_capital`（语义槽：水位/最近动用/对手方预期）；奇幻系 境界/功法清单/法宝物权/资源/瓶颈；无限流 scope 三层（series 持久/arc 半持久/instance 临时）+ 副本继承清单）。通用四键不因类型增删；扩展段缺失按"该类型维度未启用"解释。
- `biography.yaml`：append-only 传记账本（字段见下）。

**字段表**（`biography.yaml`）

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `char_id` | 是 | 角色标识 |
| `growth_track[].segment` | 是 | 弧段序号（多段弧，一个角色可有多段弧，不限单弧单值） |
| `growth_track[].mode` | 是 | 弧类型，如"幻灭弧" |
| `growth_track[].from` / `.to` | 条目存在时 | 段首/段末真实变化，可涉及认识、关系、身份或处境；稳定人物可无成长轨迹 |
| `growth_track[].spans` | 是 | 覆盖的卷列表，如 `[V01, V02]` |
| `milestones[].at` | 是 | 已发生章 `C0012` 或场景 `C0012S03`；章锚须有实际发布文件或章工作区，存在场景索引时还须匹配场景 |
| `milestones[].kind` | 是 | 通用核心值 `认知转变` \| `能力获得` \| `关系变化` \| `创伤` \| `誓言` \| `退场`；类型档案可按 genre-pack `enum_extensions` 追加（如奇幻系 `境界突破`、写实系 `衔职变动`）——扩展值之外由 lint WARN 提示，不阻断 |
| `milestones[].before` / `.after` | 是 | 非空的事前/事后状态，体现该次变化；普通目标与一次选择按其实际作用归类，无承诺事件不归为誓言 |
| `milestones[].evidence` | 是 | 能定位并支持该变化的正文锚句，保留必要上下文 |
| `last_seen` | 是 | 最近登记的出场章；现 promote 只随人物 milestone 更新，可能滞后，不据此断言后续缺席 |

**不变量**

- 章级人物资料由合时人格基线、来源窗口内可见的快照继承链与本卷已累计的 `milestones` 增量组成；卷进行中的变化可由 milestones 补给。派生器再按每场故事时点与角色获知渠道生成 role_view，writer/actor 消费该切片，章级资料不等于人物完整自觉知识。
- 快照序列、传记账本与既有正文保存角色演化依据。为最新续写重建 runtime 包时采用当前快照继承链；历史场景从合时资料派生，不让最新包覆盖过去的身份、关系或知识。
- `milestones` 只能追加，锚点必须是已发生的场景，不得预写未来。

**缺字段 fallback**：无适用成长轨迹时 growth_track 可为空；milestones 仅记录实际重要变化，last_seen 可按有据的出现更新。不得为了刷新它虚构 milestone。

现有 `serial_lint --check all` 中的 `consumer-fields` 校验传记五项必需字段与卷转折的 `beat/value_shift/anchor`，缺字段或无效章锚为 FAIL；未知类型枚举继续 WARN。合法空列表保留，卷规划的未定位转折可用 `unresolved`。装配器在实际消费这些字段前使用同一校验，避免把缺值渲染成正文输入。结构校验只确认字段与定位，来源是否支持变化由生成和审阅判断。

## series/character-skills/ —— 角色 runtime skill 包（系列级）

**路径**：`works/<slug>/series/character-skills/`——角色 runtime skill 包（`.claude/skills/<char_slug>/` 形态，与单篇 pipeline 产物同构）在连载态的唯一家目录；有实际兼容消费者时按需生成并复用；作者侧 phase2_character.yaml 与可选的 .claude/skills 包分别承担设计和执行参考。

- 物化脚本在章 workspace 创建 `pipeline/story-character-skills` → 本目录的符号链接，供需要正式角色包的消费者定位。链接存在不证明已经加载，也不证明包内动态资料代表本场时点。
- 人物台账与既有正文继续拥有身份、经历和变化依据。本目录承载可复用的角色表达与执行资料；派生器有实际缺口时按明确映射读取，并核对其时点。writer 和 actor 通过 role_view 的 `character_basis` 取得本场可用依据，不直接读取共享最新包或 `state.md` 覆盖切片。

**缺目录 fallback**：既有工作区无此目录时，物化脚本自动补建空目录并照常建链，不阻断物化。接管人物可直接从人物台账与正文派生，无需补建 Phase 2 或整套 runtime 包；一次性功能角色的稳定 participant ID 与简短依据按上下文协议确定。

## chapters/.../pipeline/aigc_clearance.yaml —— AIGC 防治放行凭据

**路径**：`chapters/V0N/C00NN/pipeline/aigc_clearance.yaml`，由 AIGC 防治环节通过后签发（不通过不产此文件）。

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `chapter_id` | 是 | 与所在章 workspace 一致 |
| `draft_sha256` | 是 | 签发时 `draft.md` 全文（UTF-8 字节）的 SHA-256 hex——凭据与正文的绑定位 |
| `verdict` | 是 | `pass` \| `pass_with_notes` |
| `mode` | 是 | `full`（首签，完整防治）\| `verify_only`（改文后复检重签；发现具体问题时交回既有修订动作） |
| `cleared_at` | 是 | ISO 时间戳 |
| `notes` | 否 | `pass_with_notes` 时的备注 |

**不变量**

- `draft.md` 任何字节改动即凭据失效（hash 不再一致）；发布 gate 比对当前 hash 与 `draft_sha256`，不一致即阻断发布。
- 失效后的重签唯一通道 = AIGC 防治 `verify_only` 复检通过后重写本文件；发布前的读者审阅修订改文同样触发失效与复检。

**缺文件 fallback**：凭据缺失时发布 gate 降级 WARN 放行（按防治链未接管的工作区解释）；存在但 `verdict` 非放行值 / hash 不一致 / 缺 `draft_sha256`，一律阻断。

## chapters/.../recap.yaml —— 两段式 recap

**路径**：`works/<slug>/chapters/V0N/C00NN/recap.yaml`

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `chapter_id` | 是 | 裸章号 |
| `summary` | 是 | 段落摘要，供下章全局层注入 |
| `deltas.causal_edges[]` | 否 | `{cause: <裸章号>, note: <因果说明>}`；effect 侧隐式 = 本章 `chapter_id` |
| `deltas.character_deltas[]` | 否 | milestone 候选，字段同 `biography.yaml.milestones` 加 `char_id` |
| `deltas.fact_deltas[]` | 否 | facts 条目候选，字段同 `world_facts.yaml.facts`（不含 `fact_id`，由台账转正时机器分配）加 `source_reveal_id`（兑现某条 `world_reveal_plan` 时回指其 `reveal_id`，否则为 `null`） |
| `deltas.thread_events[]` | 否 | `kind: open` 时：`{kind: open, statement, thread_id, thread_kind, intended_payoff{horizon, note}}`；`kind: advance\|payoff` 时：`{thread_id, kind, note}` |

**不变量**

- **两段式**：章审阅与防治完成后，同时生成 summary 与 deltas，纳入 buffer 供后续章消费。发布获授权后经预检转正，manifest 最后登记。转正前候选可随本章重写而更新；发布事务已经开始转正时，按恢复矩阵处理，不能再按普通 buffer 删除或改写候选。
- 已有创作章的 `recap.yaml` 是下一章物化的前置；接管历史章无章工作区时，manifest 登记的发布原文供尾窗，卷纲已发布条目的 logline 供摘要。已有章工作区却缺 recap 仍按未完成处理，不据发布文件绕过。
- 已输出候选有误时回其来源负责人修正，必要字段或已确认义务不能略过；尚无证据成立的可选变化不创建候选。需改变作者既定事实时再请求裁决。
- 单元结束时生成一次单元 digest；卷收束时生成一次卷 digest。来源后来改变才更新受影响摘要，发布环节不重复追产同一 digest。

**缺字段 fallback**：`deltas` 各子列表缺省按空列表解释（本章无对应类型的候选变化）；`fact_deltas[].source_reveal_id` 缺省按 `null` 解释（本条事实不是某个揭示计划的兑现）。

## series/decisions/D-<seq>.yaml —— 共创决策档案

**路径**：`works/<slug>/series/decisions/D-<seq>.yaml`（如 `D-0007.yaml`）

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `decision_id` | 是 | 如 `D-0007` |
| `kind` | 是 | `volume_direction` \| `beat_choice` \| `thrust` \| `veto` \| `frozen_amendment` |
| `content` | 是 | 决策具体内容 |
| `scope.level` | 是 | `volume` \| `unit` \| `chapter` |
| `scope.volume_id` | 是 | 决策所属卷 |
| `scope.unit_id` | `level: unit`/`chapter` 时按需 | 卷内局部单元编号 |
| `scope.chapter_id` | `level: chapter` 时必填 | 裸章号 |
| `scope.applies_until` | 是 | 过期界；缺省 = `volume_id` 所指卷 `closed` 即过期 |
| `consumed_by` | 是 | 规范 artifact id 列表，初始为空，消费后回写 |

**不变量**

- **机械命中键**：`level: volume` 按 `volume_id` 命中；`level: unit` 按 **(volume_id, unit_id) 联合键**命中（`unit_id` 卷内局部编号，跨卷同名 `U03` 不互相命中）；`level: chapter` 按 `chapter_id` 命中（`volume_id` 仅作一致性校验，不参与命中判定）。
- `consumed_by` 值域只允许规范 artifact id 形态：`volume:V02` \| `unit:V02-U03` \| `chapter:C0039` \| `bible:frozen` \| `profile:genre` \| `worldbook:<section_id>`，禁止混用裸文件名或裸 ID——过期未消费的比对与审计输出都按这个规范形态比较。bible/profile/worldbook 三类仅用于 frozen_amendment；volume:V## 同时承载普通卷决定的消费回执，修改 closed 卷时 lint 另要求该决定为 frozen_amendment。
- 普通决定在产物采用后回写 consumed_by；冻结修订取得用户本次授权后，先登记现有目标凭据再执行获准写入，以适配写保护检查。历史 token 不替代当前批准。具体时序见[共创协议](collaboration-protocol.md)。
- 决策消费是独立机制，与"预置文件已存在时在其上完善"的机制不复用同一套语义。

**缺字段 fallback**：`consumed_by` 缺省按空列表解释（尚未消费）；`scope.unit_id`/`scope.chapter_id` 在不适用的 `level` 下缺省按 `null` 解释。

## published/manifest.yaml —— 发布序真值

**路径**：`works/<slug>/published/manifest.yaml`

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `entries[].chapter_id` | 是 | 裸章号 |
| `entries[].file` | 是 | `published/` 下展示态文件名（带卷前缀，如 `V01C0001.md`） |
| `entries[].published_seq` | 是 | 发布全序（唯一真值；前文检索的时序过滤按此排序，不按章号） |
| `entries[].ts` | 是 | 发布时间戳 |
| `revisions[].chapter_id` | 是 | 被勘误的章 |
| `revisions[].reason` | 是 | 文字级勘误说明（错字/语句润色，不动设计事实） |
| `revisions[].ts` | 是 | 勘误时间戳 |

**不变量**

- `published/` + `manifest.yaml` 是唯一发布真值。设计事实回改禁止——发布后发现矛盾走 `world_facts.yaml` 的 `errata` 条目或卷纲新增侧，不改 `entries` 已记录的历史。
- 文字级勘误允许：修订发布稿文件内容，同时在 `revisions[]` 追加一条记录保留可追溯性；不产生新 `entries` 条目。
- **发布是一个事务，`manifest.yaml` 登记是最后一步**：① 预检 recap deltas 可转正（schema 校验 + 双向闭合预检 + AIGC 防治凭据核验——`pipeline/aigc_clearance.yaml` 存在时其 `draft_sha256` 须与 `draft.md` 当前 hash 一致，不一致即阻断；缺失降级 WARN，见该文件一节）→ ② append 三台账 + 重建 `facts_current.yaml` → ③ 拷入 `published/` → ④ manifest 登记 + 冻结推进。任一步失败，`manifest.yaml` 不推进，靠入会恢复矩阵定位断点续跑（见 `series_state.yaml` 一节）。第②步幂等：台账 append 以来源 `chapter_id` + 条目序判重，已转正条目跳过，重跑事务不产生重复 append。

**缺字段 fallback**：`revisions` 缺省按空列表解释（该作品尚无勘误记录）。

## series/digests/V0N.yaml —— 卷级 digest

**路径**：`works/<slug>/series/digests/V0N.yaml`（卷收束时由 chapter-summarizer 产出）

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `volume_id` | 是 | 如 `V01` |
| `one_liner` | 是 | 一句话摘要——远卷层注入用 |
| `paragraph` | 是 | 一段摘要 |

**不变量**：本文件是运行态产物，不手工编写初稿——卷收束流程产出后供全局层注入直接读取，不再现场压缩。

**缺字段 fallback**：本文件缺失即视为对应卷尚未收束，读取方按"该卷无 digest 可用"降级，不阻断，仅远卷层跳过该卷摘要。

## series/digests/V0N-U0M.yaml —— 单元级 digest

**路径**：`works/<slug>/series/digests/V0N-U0M.yaml`（单元末章回灌时由 chapter-summarizer 产出）

**字段表**

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `1` |
| `volume_id` | 是 | 所属卷，如 `V01` |
| `unit_id` | 是 | 单元编号（卷内局部），如 `U03` |
| `paragraph` | 是 | 一段摘要——本卷前单元层注入用 |

**不变量**：远卷与前单元读取摘要，本单元前章保留 recap。该分层降低逐章读取全文的成本；卷数和未决资料仍会增加上下文，不能宣称始终为常量。摘要缺失按实际来源恢复。

**缺字段 fallback**：本文件缺失即视为对应单元尚未收束回灌，读取方按"该单元无 digest 可用"降级。

## 写入职责与保护

字段按其实际职责更新，不因同在一个文件而采用统一写法：

| 对象 | 更新方式与边界 |
|---|---|
| 已发生事实和发布记录 | 台账事实、人物 milestone、线程事件及 manifest 记录保留来源；误记走现有 retract/errata，发布事务按来源幂等 |
| 未转正候选与未冻结设计 | recap.deltas 随定稿修订；intended_payoff、未兑现揭示的结转/废弃、场景安排由获授权的设计负责人更新 |
| 派生状态与索引 | facts_current、线程状态、已兑现 reveal 回指、章节发布状态等按原来源重算；章卡和场景索引保留真实编排顺序 |
| 已冻结内容 | story_bible.frozen、genre_profile、worldbook axiom 册及 closed 卷按本次授权与对应 frozen_amendment 凭据处理；发布稿文字勘误走 manifest revision |

结构性 lint 使用可取得的 git 基线比对，缺基线时只能提示，无法证明所有写入受保护。内容权限由执行者核对本次授权；不能以旧凭据或脚本未报错代替该判断。worldbook append 册继续只追加既有约定允许的小节。
