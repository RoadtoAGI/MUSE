# 角色 Skill 模板

本文件是 character-persona 构建器生成角色 SKILL.md 时的模板参考。

> **填写前建议**：装有 MUSE-canon-distill 扩展包且存在职责匹配的名著人物档案时，先用最贴切的一份；另一份档案只有能补足独立信息缺口时才增加。名著档案的结构、人物内容与贴切表述可直接复用，以当前角色设计契约为准。没有贴切档案时按下方模板与 [phase2-character/SKILL.md](../../phase2-character/SKILL.md) 的 register 表自行设计，不凑数量。

> **章节标注约定**：本文件内嵌入的角色 SKILL.md 模板中，每个顶级 `## 章节` 必须紧跟一行 `<!-- required -->` 或 `<!-- optional -->` HTML 注释。verify_phase2_assets 在校验生成的角色 SKILL.md 章节集时会**运行时解析**这些注释——必备章节集 = 实际章节集的子集；实际章节集 ⊆ 必备 ∪ 可选。任何修改本模板章节结构的提交都必须同步更新这些注释，且**不得**在 SKILL.md / verify 脚本中硬编码章节名。
>
> 本文件自身的章节锚（`## SKILL.md 模板` / `## state.md 初始化模板` / `## 填写指南`）不受此约束——它们是文档结构，不是被生成产物的章节。

---

## SKILL.md 模板

生成的角色 Skill 是 run 级 **file-backed 参考包**（reference package），不是任务 skill。actor / writer 通过明确文件路径按需 Read，获得角色当下可用的人格上下文。完整人物设计继续保存在 `phase2_character.yaml`，本模板只编译 actor-facing 信息。因此：
- **不设** `context: fork`（不需要独立 fork）
- **不给** Write/Edit 工具（角色 Agent 的写入由 orchestrator 统一落盘）
- 消费方只用 Read 访问 SKILL.md、state.md 和 references/，不依赖 `skills` 字段预加载

```markdown
---
name: {role-slug}
description: {中文角色名} — {一句话角色定位}
version: 1
allowed-tools: Read
---

# {中文角色名}

## 身份与处境
<!-- required -->

{简述角色身份、当下处境与相关经历。}
{不突出职业标签——"黎安，29岁，在沙漠哨站撑着临时病房"比"黎安，29岁，战地医护兵"更好。}
{职业是背景，不是定义。}

<!-- 来源：phase2_character.yaml → protagonist.characterization + daily_life；补充来源（如需）：phase1_world.yaml → daily_life, world_rules -->

## 经历与信念
<!-- required -->

{只写角色在故事入口已经经历、记得或相信的内容，以及这些经历怎样影响 ta 对人、世界与自己的理解。}
{事件与影响可以来自 backstory；`narrative_use` 等作者侧采收说明不进入本节。角色尚不知道的事实不进入本节。}

<!-- 来源：phase2_character.yaml → backstory.event + backstory.impact + daily_life；补充来源（如需）：phase1_world.yaml → 已被角色知晓的 world_rules / daily_life -->

## 自觉追求
<!-- required -->

{角色在故事入口知道自己正在争取、保护、回避或完成什么。写成角色能够承认的具体追求。}

<!-- 来源：phase2_character.yaml → desire_system.conscious + 当前处境 -->

## 判断习惯与行为盲区
<!-- required -->

{用角色会怎样注意、归因、误判、选择或回避来描述稳定倾向。写可表演行为，不写作者诊断标签。}
{从 Phase 2 人物设计提炼当前已经成立的行为模式；不预告未来，不把盲区变成角色已经知道的自我分析。}

<!-- 来源：phase2_character.yaml → 当前已成立的判断与行为材料（由 character-persona 行为化编译） -->

## 声音框架
<!-- required -->

{用散文描述角色有来源、且对成品判断真正承重的说话倾向;不规定维度和数量。}
{描述倾向，不描述映射——"偶尔借手边的东西说理"而非"恐惧=盐水隐喻"。}
{身份标签偶尔影响语言，但不是默认修辞模式。}
{Phase 2 对受压变化有依据时,说明人物在相关刺激下怎样选择合作、隐瞒、行动、沉默或表达;不为未设计的压力类型补全反应，也不预设句法变化方向。}

<!-- 来源：phase2_character.yaml → voice_traits 中实际存在的观察项 -->

### 压力下的表达（按依据选填）

- {只写 Phase 2 或既有经历支持的压力触发与反应倾向;可写逼问、羞辱、误解,也可写本角色更相关的刺激}
- {直说爱 / 恨 / 怕 / 愧疚、沉默、行动、转移或长句解释均可成立,以人物自知和关系为准}

### 身体与物件锚点（按依据选填）

{有来源且承重的动作或物件习惯；保留其触发条件，日常习惯也可成立，不为填栏添加动作。}

### 不说出口的内容

- {只记录有来源的不可说内容;没有时写"暂无可归因的固定禁区"}
- {替代表达是候选:动作 / 沉默 / 玩笑 / 专业术语 / 离开 / 赠物 / 破坏物件 / 直接说明}

## 边界（Layer 0 硬规则）
<!-- required -->

只收录 Phase 2 字段能够支持的边界，不规定类别或条目数量。每条保留适用时点、关系、触发条件与约束强度；标题不把倾向或当时承诺升级为终身禁令。有明确依据的强底线保持强度；没有可归因边界时写明暂无，保持本节存在即可。以下分类是可选落点。

### 语言边界（language_boundary）
{在什么对象与处境下避免哪些表达；说明依据与例外，原设计明确绝对限制时保留}

### 行动边界（action_boundary）
{来源确立的行动限制及其适用条件；压力检验支持的强底线保持明确}

### 沉默边界（silence_boundary）
{什么情境下会停止解释 / 停止争辩 / 保持沉默}

### 物件边界（object_boundary）
{重要关系物 / 身份物 / 创造物会如何被保护 / 毁坏 / 回避}
{无关键物件互动的配角可省略本节}

### 误读边界（misread_boundary）
{别人最容易如何误读 ta；ta 是否纠正}
{无误读功能的配角可省略本节}

<!-- 来源：phase2_character.yaml → voice_boundaries + voice_traits.misread_pattern -->

```

---

**Legacy optional 章节（只供校验）**

以下章节只进入校验白名单，供旧角色包在 `rebuild` 期间兼容。新生成的角色 `SKILL.md` 不写这些章节；作者侧内容继续保存在 `phase2_character.yaml`，通用表演方法由 `character-actor` 统一提供。

## 核心欲望
<!-- optional -->

## 性格真相
<!-- optional -->

## 人物轨迹
<!-- optional -->

## 弧光
<!-- optional -->

## 内在生存能力
<!-- optional -->

## 主体性物件
<!-- optional -->

## 表演规则
<!-- optional -->

---

## state.md 初始化模板

```markdown
# {中文角色名} · 主观状态

> 本文件保存已记录时点的主观状态。actor / writer 只读，并结合当前 role_view 核对时点。

## 当前情绪

{故事开始时角色正在体验的情绪与身体状态。只用 character_arc.start_state 帮助定位故事入口；不把 mode、end_state 或轨迹机制写入 state.md。}

## 已知信息

{故事开始时角色知道的事实}
{从 backstory + phase1_world 推导}

## 关系感知

{对其他主要角色的初始看法}
{从 relationships + 角色自身视角推导 — 可能与客观关系不一致}

## 经历摘要

（故事尚未开始，此节为空）

## 内心冲突

{角色此刻能体验到的拉扯、冲动或不适}
{可从 desire_system 的矛盾推导,但不写成角色已经识别出的不自觉欲望或核心缺陷}
```

---

## 填写指南

详见本 skill 的 [`runtime-writing-guide.md`](runtime-writing-guide.md)——身份、经历与信念、自觉追求、判断习惯与行为盲区、声音、边界的编译启发。
