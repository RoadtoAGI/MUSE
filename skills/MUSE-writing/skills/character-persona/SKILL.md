---
name: character-persona
description: 角色人格构建器 — Phase 2 完成后，将结构化人物设计转化为标准化的运行时角色 Skill 包。当 Phase 2 人物系统设计完成、需要为角色生成独立的人格 Skill 时使用。只构建，不执行角色扮演。
user-invocable: true
argument-hint: "build | rebuild <role-slug>"
allowed-tools: Read Write Edit Bash Glob
version: 1
---

# 角色人格构建器（Character Persona Builder）

## 执行总览

```text
build | rebuild <role-slug>
  -> 读取 phase2_character.yaml
  -> 确定目标角色集合
  -> 逐角色生成 / 更新 runtime package
       -> SKILL.md + build-meta.yaml + adapter
       -> rebuild 时保留既有 state.md
  -> 写 build-report.md
  -> verify_phase2_assets.py
       |-- 全部通过 -> 允许下游消费
       `-- 任一失败 -> 写失败明细并阻断
```

`phase2_character.yaml` 是完整人物设计的作者侧权威源。角色 `SKILL.md` 是从中编译出的 actor-facing 静态上下文，`state.md` 保存已记录时点的主观状态，adapter 是 SKILL.md 的只读派生物。

> 本 Skill 是**元技能/构建器**：把 Phase 2 的结构化人物数据转化为可被角色 Agent 加载的标准 Skill 包。
> 它不执行角色扮演、不触发排练。

## 接口约束（违反会导致下游断裂）

| # | 约束 | 违反后果 |
|---|------|---------|
| 1 | 使用 `role_slug` 作为 skill 目录名（小写字母 + 连字符，如 `li-an`、`xiao-long-nv`），不拼接故事前缀。隔离由工作目录承担（`pipeline/story-character-skills/`，每个 query 独立目录） | 角色 Skill 无法被当前运行时发现，或与同名角色（不同来源）冲突 |
| 2 | `pipeline/characters/{角色名}.md`（adapter）是 SKILL.md 的只读派生物，**禁止手改** | adapter 与 SKILL.md 出现双源漂移，审稿和校验以哪个为准不明确 |
| 3 | SKILL.md frontmatter 的 `version` 随人格更新；build-meta 保留当前来源与 adapter 校验信息 | 来源可追溯，adapter 物理校验由 `adapter_sha256` 锁定 |
| 4 | `rebuild` 绝不覆盖 state.md（state.md 包含角色 agent 的运行时记忆） | 角色失忆，破坏跨场景的主观状态连续性 |
| 5 | 资产写入路径固定：`pipeline/story-character-skills/.claude/skills/{role-slug}/` + `pipeline/characters/{角色名}.md` | 与 story-writing 全局目录契约（见 [pipeline-overview.md](../story-writing/references/pipeline-overview.md)）不一致，下游消费方读取失败 |

## 触发条件

- Phase 2（人物系统设计）全部步骤完成
- `pipeline/phase2_character.yaml` 已生成
- orchestrator 准备为角色创建独立的人格 Skill

## 输入

### 主输入（必须）

`pipeline/phase2_character.yaml` — Phase 2 产出的结构化人物数据。

构建器读取完整人物设计，再按 actor-facing 边界选择和编译字段：
- `protagonist`：characterization, desire_system, character_arc.start_state, characterization_vs_truth, voice_traits, voice_boundaries, backstory, daily_life, empathy_mechanism, inner_capacity
- `deuteragonist`（若存在）：结构同 protagonist，按同一路径读取
- `antagonist`：name, motivation, desire, voice_traits, voice_boundaries
- `supporting_cast[]`：name, function, relationship, voice_traits_summary, subjectivity_object
- `contrast_axes`：角色间的极化关系
- `relationships`：权力动态、关键张力

`character_arc.mode / end_state / transformation`、`backstory.narrative_use`、`subjectivity_object.potential_use` 等字段仍由 Phase 2 与后续作者侧阶段消费，构建器不把它们复制到新 runtime SKILL 或 adapter。

### 补充输入（可选，按需读取）

| 文件 | 读取条件 | 提取内容 |
|------|---------|---------|
| `pipeline/phase0_conception.yaml` | 角色声音需要与作品整体风格对齐时 | `style_directives`（风格指令）、`core_value`（核心价值） |
| `pipeline/phase1_world.yaml` | 角色身份与处境需要世界规则支撑时 | `daily_life`（日常生活）、`world_rules`（世界规则）、`creative_constraints`（创作约束） |

读取原则：**不整体吞入**，只提取与当前角色直接相关的片段。

---

## 执行流程

### Step 1：读取输入，确定构建范围

1. 读 `pipeline/phase2_character.yaml`
2. 角色筛选 + slug 命名：按下面"关于角色选择与 slug 命名"小节执行——先判断哪些角色需要构建，再为每个角色确定 `role_slug`，并推导 `story_slug`
3. 按需读取 phase0/phase1 补充输入

### 关于角色选择与 slug 命名

（story_slug 只作元数据与报告标题，不参与 skill 命名；role_slug 作为 skill 目录名与 build-meta 字段）

- 判断哪些角色需要构建独立 Skill：
  - **protagonist、deuteragonist（若存在）和 antagonist**：总是构建
  - **配角**：根据叙事需求判断——如果这个配角有独立对白场景、会与主角产生关键互动、或声音需要与其他角色区分开，就值得构建。Phase 2 阶段可能无法完全确定，Phase 5 场景分配后可通过 `/character-persona build` 补充
- 确定 `story_slug`（按优先级）：
  - 数据集创作：使用 `{数据集名}_{index}`（如 `writing-bench_184`）
  - 独立创作：从 `phase0_conception.yaml` 的 title 推导（如 `desert-outpost`）
  - 以上都不可用时：根据 premise 自拟简短 slug，并在 build-report 中说明
- 为每个角色生成 `role_slug`（小写字母 + 连字符，从中文名音译，如 `li-an`、`xiao-long-nv`、`chen-mo`），既是 skill 目录名也是 build-meta 中的字段

### Step 2：为每个角色生成 Skill 包

对每个角色执行以下操作。参考 `${SKILL_DIR}/references/skill-template.md` 中的模板；填写启发见 [`${SKILL_DIR}/references/runtime-writing-guide.md`](references/runtime-writing-guide.md)。

#### 2a. 生成 SKILL.md（静态人格定义）

从 Phase 2 数据中编译角色当下可用的人格上下文，按 skill-template.md 的新生成模板落盘。完整作者设计继续留在 `phase2_character.yaml`。

生成时遵循以下**创作启发**（质量倾向，不是硬约束；理论依据见 `${SKILL_DIR}/references/mckee-voice-principles.md`）：

- **用自然语言，不用结构化参数**：voice_traits 转化时保留倾向性描述，去掉"情感→修辞"映射关系
- **把作者诊断编译成行为**：可用 `desire_system.unconscious / core_flaw` 与 `characterization_vs_truth` 推导角色如何注意、归因、误判、选择或回避；成品只写当前成立的行为模式，不复制诊断标签
- **把极化差异编译到人物内部**：用 `contrast_axes / relationships` 校对差异，每份 runtime 只写实际承重的一项或若干项——注意、利益、误判或关系行动怎样从经历中产生；不把“甲理性、乙感性”这类对照标签复制给 actor
- **边界保持可归因**：只转写 Phase 2 已有的 voice_boundaries,不为填满模板另造禁令
- **写给"演员"看，不是写给"分析师"看**：角色 Skill 的读者是角色 Agent，需要经历与信念、自觉追求、判断习惯与行为盲区、声音和边界
- **保留来源注解**：skill-template.md 中的 `<!-- 来源：phase2_X → 字段 -->` HTML 注释必须原样保留在最终产出 SKILL.md 中，不得删除或转换为其他形式——这是下游 evidence-map / reviewer 追溯每节内容到 Phase 2 依据的唯一锚点

新生成的角色 SKILL.md 不包含 `不自觉欲望`、`核心缺陷`、`性格真相`、`character_arc.mode`、`end_state`、人物轨迹机制、作者侧采收说明或通用表演规则。角色特有的行为盲区由构建器行为化表达；通用表演方法由 `character-actor` 统一提供。

#### 2b. 生成 state.md（初始主观状态）

state.md 保存已记录时点的角色主观状态。actor / writer 只读，本构建器只初始化；后续消费结合本场 role_view 与相关已发生事实，不能假定文件已自动更新。

初始化内容：
- **当前情绪**：只从 `character_arc.start_state` 提炼故事入口正在发生的主观情绪和身体状态；不写入 mode、end_state 或轨迹机制
- **已知信息**：故事开始时角色知道什么（从 backstory + world 推导）
- **关系感知**：对其他角色的初始看法（从 relationships 推导）
- **经历摘要**：空（故事尚未开始）
- **内心冲突**：角色此刻能够体验到的拉扯、冲动或不适;可由 desire_system 的矛盾推导,不写成角色已经识别出的不自觉欲望或核心缺陷

初始化前核对当前情绪、已知信息、关系感知和内心冲突是否共同描述故事入口。`start_state` 只服务本次初始化，人物弧光终点继续由作者侧规划。

#### 2c. 生成 references/backstory.md（可选）

当既有经历较长、且按需回忆比常驻输入更合适时，将角色已经知道的 `event + impact` 整理为独立幕后故事参考文件，并在 SKILL.md 标明读取条件与相对路径。省略 `narrative_use` 与角色尚不知道的幕后事实。

#### 2d. 生成 build-meta.yaml（构建元数据 + provenance）

build-meta.yaml 是该角色 Skill 包的 provenance 证据——下游 verify_phase2_assets 凭此校验"产物来自本 builder"。

```yaml
generated_by: character-persona                          # 固定字符串，标记本 builder 产出
character_slug: {role-slug}                              # = skill 目录名 = SKILL.md frontmatter name
character_display_name: {中文角色名}
input_sources:                                           # 实际读取的输入文件列表（用于追溯）
  - pipeline/phase2_character.yaml
  # - pipeline/phase0_conception.yaml   （按需）
  # - pipeline/phase1_world.yaml        （按需）
adapter_path: pipeline/characters/{中文角色名}.md          # adapter 文件路径
adapter_sha256: {adapter 文件实际内容 sha256 前 16 位}      # 防 adapter 手改的物理校验
```

**字段语义关键点**：

- `generated_by: character-persona` 是 verify 区分"本 builder 产出"vs"其他来源"的唯一标识，**禁止删除或改写**。
- `adapter_sha256` 锁住 adapter 文件不被手改。

#### 2e. 章节不变量（结构白名单运行时派生）

> **章节白名单的权威来源是 [`references/skill-template.md`](references/skill-template.md)，不在本 SKILL.md 或 verify 脚本中硬编码章节名**——避免与模板漂移、避免误杀历史合法章节。

具体规则：

- `references/skill-template.md` 中的新生成章节与 legacy 兼容章节均用 HTML 注释声明：
  - `<!-- required -->` → 必备章节（生成的角色 SKILL.md 缺此章节即 fail）
  - `<!-- optional -->` → 旧包迁移期间允许保留的 legacy 章节；新生成路径不主动写入
- 生成本角色 SKILL.md 时，顶级 `##` 章节集合必须满足：
  - 必备章节集 ⊆ 实际章节集
  - 实际章节集 ⊆ (必备 ∪ 可选)
- verify_phase2_assets 在校验时**运行时解析**这两个 HTML 注释组装白名单——本 SKILL.md / verify 脚本不允许出现章节名硬编码列表。
- 修改 skill-template.md 必备/可选标注前，先 audit 旧高质量样本下的角色 SKILL.md 章节集。旧章节保持 optional 让 `rebuild` 可安全迁移；rebuild 生成新章节并保留 `state.md`。

#### 2f. 描述性质量信号（reviewer HOW 判据，不计数）

> 不在本 SKILL.md 或下游 reviewer 中规定「`<!-- 来源：` 出现 ≥N 次」「确定性标记 ≥N 次」等人肉计数门槛——这种门槛会诱导 builder 凑数。

落盘的角色 SKILL.md 需满足以下**描述性信号**（reviewer 据此做 HOW 判定，无固定数量阈值）：

1. **经历与信念保持信息边界**：只写角色在故事入口已经经历、记得或相信的内容；作者侧采收用途和未知事实不进入。
2. **盲区可表演**：「判断习惯与行为盲区」说明人物怎样注意、归因、误判、选择或回避，不贴作者诊断标签，也不泄露未来终点。
3. **声音段解释可预测的 HOW**：「声音框架」写出当前角色有依据的节奏、句法、用词或受压变化,选择真正承重的方面即可;成品应能据此判断某个具体回应是否来自这个角色。
4. **边界段保持来源与理由**：沿用模板章节名，只收录 Phase 2 可追溯的边界，保留适用时点、关系、触发条件与原有强度。倾向、当前承诺和强底线分别表达；不因章节名将前两者升级为绝对禁令。没有来源时保留空边界说明。
5. **来源注解覆盖关键断言**：`<!-- 来源：phase2_X → 字段 -->` HTML 注释应覆盖每一节的核心断言，让 reviewer 能反查 Phase 2 依据；**不规定具体数量**——一条覆盖一节的核心断言、还是按子项分散覆盖，由 builder 按节内容密度判断。
6. **预测性可执行**：读完角色 SKILL 后,应能从人物依据预测贴合当前刺激的一类回应;沉默、行动、物件处理、直说或长句都可以成为结果。

reviewer 校验落点：读完该节能否判断一条成品台词或反应是否与角色来源相容？能 = 通过；只有无法落到成品的形容词标签 = fail。

### Step 3：生成兼容 adapter

为每个角色在 `pipeline/characters/{中文角色名}.md` 生成兼容 adapter 文件，保留既有路径与 sha 校验契约。

**adapter 是从 SKILL.md 单向生成的只读文件**，内容保持 actor-facing：

```markdown
# {角色名}

## 身份与处境
{从 SKILL.md 的"身份与处境"章节提取}

## 经历与信念
{从 SKILL.md 的"经历与信念"章节提取}

## 欲望
{从 SKILL.md 的"自觉追求"章节提取}

## 判断习惯与行为盲区
{从 SKILL.md 的同名章节提取}

## 声音
{从 SKILL.md 的"声音框架"章节提取}

## 边界
{从 SKILL.md 的"边界"章节提取}
```

adapter 不复制 `不自觉欲望`、`核心缺陷`、性格真相标签、`mode / end_state / transformation` 或人物轨迹机制。需要作者侧人物设计的阶段直接读取 `phase2_character.yaml`。

### Step 4：生成 build-report.md（应构建集声明 + 决策记录）

在 `pipeline/story-character-skills/build-report.md` 生成 `build-report.md`，记录本次应构建集判定与每个角色的决策。本文件同时承担 **name → slug 映射桥梁**——下游 verify_phase2_assets 凭它把 phase2_character.yaml 中的 `name`（真实 schema 主键）反查到 builder 产出的 `slug`，**不要求** phase2_character.yaml 自带 slug 字段。

#### 应构建集声明（两阶段）

> **真实 phase2_character.yaml schema**：`protagonist.name` / `deuteragonist.name` / `antagonist.name` / `supporting_cast[].name` —— 全部以 `name` 为主键，没有 `slug` 字段。本 builder 在 build-report 中显式建立 name → slug 映射。

| 阶段 | 必建 | 推迟（Phase 5 补建） |
|---|---|---|
| **Phase 2** | `protagonist.name` + `deuteragonist.name`（若该键存在）+ `antagonist.name` + 满足上文判据的 `supporting_cast[].name`（独立对白场景 / 关键互动 / 声音区分） | `supporting_cast[].name` 中"背景人物 / 转述人物 / 群体敌人"等不满足判据的 |
| **Phase 5+** | `phase5_scenes.yaml.participants` 中"直接登场且有对白或关键行动"但 Phase 2 未建的 name | — |

Phase 2 阶段调用本 skill 时，**phase2 列出的每个 name 必须在 build-report 已构建表或未构建表里出现一次**——任一 name 缺判定 = builder 漏过判断 = phase2 hard gate fail。

#### build-report.md 模板

```markdown
# Build Report — {story_slug}

构建时间：{ISO 时间}
来源：pipeline/phase2_character.yaml
本次阶段：{phase2 | phase5_supplement}

## 已构建

| name | slug | 类型 | 深度 | 4 产物落盘 |
|------|------|------|------|------------|
| {phase2 中的 name} | {role-slug} | protagonist | 完整 | ✅ |
| ... | ... | ... | ... | ... |

## 未构建

| name | 类型 | skip_reason |
|------|------|-------------|
| {phase2 中的 name} | supporting_cast | {为什么本阶段不需要独立 Skill；引用本 SKILL.md §"是否构建独立 Skill 的判据" 段判据} |

## 补充输入

{是否读取了 phase0/phase1，读取了哪些字段，为什么}
```

**字段约束**：

- 已构建表的 `name` 必须在 phase2_character.yaml 中存在（不允许幻觉构建未授权角色）
- 未构建表每行必须填 `skip_reason`（缺失 = phase2 hard gate fail）
- `4 产物落盘` 列指向下文 §Step 4.1，4 件产物全齐才标 ✅

#### Step 4.1：4 产物清单（builder 自检参考）

每个落入"已构建"表的角色，必须产出以下 4 个文件——builder 自查路径：

| # | 产物 | 路径 | 生产步骤 |
|---|------|------|----------|
| 1 | 角色 SKILL.md | `pipeline/story-character-skills/.claude/skills/{slug}/SKILL.md` | Step 2a |
| 2 | state.md | `pipeline/story-character-skills/.claude/skills/{slug}/state.md` | Step 2b |
| 3 | build-meta.yaml | `pipeline/story-character-skills/.claude/skills/{slug}/build-meta.yaml` | Step 2d |
| 4 | adapter | `pipeline/characters/{display_name}.md` | Step 3 |

**Phase 2 hard gate**：4 产物 + 应构建集声明完整后，由 `verify_phase2_assets.py` 校验。
**详细字段断言与错误码以脚本为权威**：[`skills/MUSE-writing/scripts/verify_phase2_assets.py`](../../scripts/verify_phase2_assets.py)。
脚本调用与退出码处理见 [`phase2-character/SKILL.md §7`](../phase2-character/SKILL.md)。

### Step 5：验证

**接口约束自检**：对照本文件顶部"接口约束"逐项核验，外加 frontmatter 完整性（包含 name、description、version、allowed-tools）。必须全部通过，否则构建失败。

**builder 写作动作自检**（脚本兜底之前 builder 自身要做的事）：
- `<!-- 来源：phase2_X → 字段 -->` 注解是否覆盖每节核心断言（脚本不校验注解内容，靠 builder 自觉）
- 角色 SKILL.md 章节是否按 §Step 2e 不变量从 skill-template.md HTML 注释派生（不照抄硬编码章节名）
- build-report.md 中 phase2 列出的每个 name 都已落入"已构建"或"未构建"任一表（漏判 = builder bug）

字段断言、4 产物完整性、sha 一致性等结构校验以 `verify_phase2_assets.py` 为权威。

**创作质量自检（描述性 HOW 信号，reviewer 判定，不计数）**：
- SKILL.md 是否用 actor-facing 章节覆盖这个角色真正承重的信息，并省略作者诊断、未来轨迹与通用表演方法？
- 「经历与信念」是否只含角色在入口时点可知的内容；「判断习惯与行为盲区」是否落成可观察倾向？
- 「声音框架」是否用来源支持的注意、措辞、沉默或话语行动解释 HOW，而不是堆 trait 标签或补齐固定维度？
- 「边界」每一条是否给出 reason 或具体反例，而不是单一禁令清单？
- `<!-- 来源：phase2_X → 字段 -->` 注解是否覆盖每节的核心断言？（不规定具体数量；按节内容密度判断）
- 多角色场景中，各角色在注意、判断、关系行动或声音中是否有能改变选择的差异（参照 `contrast_axes`）？
- state.md 初始状态是否与故事起点一致

### Step 6：汇报

向 orchestrator 汇报构建结果：

```
✅ 角色 Skill 包构建完成

已构建：
- {角色名} → pipeline/story-character-skills/.claude/skills/{role-slug}/
  adapter → pipeline/characters/{角色名}.md
- ...

决策详情见 pipeline/story-character-skills/build-report.md

提醒：确保当前运行时已挂载或可发现 `pipeline/story-character-skills`；若运行时需要显式加入项目目录，按其目录挂载机制加入该路径。
```

---

## 输出目录结构

```
pipeline/
├── story-character-skills/
│   ├── .claude/skills/               ← 当前兼容挂载点
│   │   ├── {role-a}/                 # 直接以 role-slug 命名（如 li-an）
│   │   │   ├── SKILL.md              # 静态人格定义
│   │   │   ├── state.md              # 初始主观状态
│   │   │   ├── references/
│   │   │   │   └── backstory.md      # 幕后故事（可选）
│   │   │   └── build-meta.yaml       # 构建元数据
│   │   └── {role-b}/
│   │       └── ...
│   └── build-report.md               ← 构建决策记录
│
└── characters/                       ← 兼容 adapter
    ├── {角色名A}.md
    └── {角色名B}.md
```

---

## 职责边界

本 Skill **只负责**：
- 把结构化人物设计编译成 actor-facing 角色 Skill 包
- 初始化 state.md
- 生成兼容 adapter
- 生成 build-meta.yaml

本 Skill **不负责**：
- 触发运行时情境排练（那是 character-rehearsal 的职责）
- 决定 scene-local objective（那是运行时推导的）
- 执行角色扮演（那是角色 Agent 加载 Skill 后的事）
- 修改 Phase 2 的设计（如果设计有问题，回 Phase 2 修改）

---

## rebuild 命令

当 Phase 2 数据更新（如设计修订后调整了 voice_traits）或需要重新生成某个角色的 Skill 时：

```
/character-persona rebuild li-an
```

这会：
1. 重新读取 phase2_character.yaml 中对应角色的数据
2. 按当前 actor-facing 模板重新生成 SKILL.md 和 adapter；legacy optional 章节不再主动写入
3. 更新 build-meta.yaml 时间戳
4. 维护 SKILL.md frontmatter 的 version

state.md **不会被覆盖**（它包含运行时状态）。

也可用于 Phase 5 后为新确认的重要配角补充构建：
```
/character-persona build
```
此时会重新扫描 phase2_character.yaml，为尚未构建 Skill 的配角生成新的 Skill 包。
