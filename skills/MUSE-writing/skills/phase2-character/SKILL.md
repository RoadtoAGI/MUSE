---
name: phase2-character
description: 原创完整链的人物设计，形成追求、轨迹、对抗、关系和声音；由创作编排或指定阶段任务调用，有角色运行消费者时构建参考包。
---

# Phase 2: 人物系统

## 核心原则

人物塑造记录外在可观察的素质，人物性格通过有风险、有代价的选择得到揭示。表里反差与内在矛盾是形成深度的主要方法；按本作人物作用选择，其原著依据与项目适用范围见 `references/mckee-character.md`。

## 输入契约

从 Phase 0 接收：
- `core_value` — 人物冲突应体现核心价值的正负对立
- `premise` — 人物处境围绕前提设定
- `requirements / canon_reference_profile`（存在时）— 识别手选人物参考及其预期用途

从 Phase 1 接收：
- `setting(4D)` — 人物背景受世界设定约束
- `world_rules` — 世界规则决定人物的可能性边界
- `daily_life` — 仪式、价值观、权力结构为人物的日常和幕后故事提供素材

## Canon/design reference（按问题取材）

人物或关系的核心构思尚未确定、或被退回时，读取[大纲构思与回读](../story-writing/references/outline-exploration.md)：从人物经历和关系中发现新的理解，推演可能的行为及后果，提交作者选择。仅需人物设计时，候选保持在人物及关键处境的尺度。

需要补取参考时，附 `narrative_problem`，说明当前人物相信什么、关系中什么仍未被理解或展开。

已有适用参考直接消费。首次构思缺少参考、新问题出现或现有材料不足时，通过 `Skill design-doc-reference` 补取材料；用户明确不要参考时跳过。调用时传入：

```
phase=2
genre=<Phase 0 genre.primary>
signals=<JSON: 至少含 protagonist_register, antagonist_register, relationship_mode, primary_drive 中能填的>
```

调用成功 → Read `pipeline/references/phase2_design_ref.md`，学习：

- 同 register 名著人物的**维度与压力选择**（外在印象、内在冲突及选择的关系）
- **声音特征写法**（HOW 描述而非标签）
- **弧光模式**（transformative / revelatory / static / degenerative 各自的组织线）
- 原作如何使人物经历、信念、盲区与关系共同产生有辨识度的判断；这些行为让读者对人产生什么认识，迁入本作后哪些条件改变

**参考不可用时**：按已有材料与理论继续设计；作者指定的必要来源缺失时，保留该领域的待决问题。扩展包可用性未知时通过宿主入口确认；已确认不可用且条件未变时，沿用该结果。

## 名著人物档案参考（扩展包不可触发时的降级 fallback 表）

> 优先使用已有的适配人物材料；需要补材时调用上方参考入口。扩展包不可用或没有适配档案时，下表提供启发。

MUSE-canon-distill 扩展包可查询分析阶段的个体档案（`characters/{角色}.md`）及蒸馏参考包（`characters/{slug}/SKILL.md`）。按本作人物问题理解来源中的选择、声音、关系和轨迹，保留适用条件；无需与 Phase 2 逐字段对应。存在与当前人物 register 和场景职责真实匹配、且能补足信息缺口的档案时，先用最贴切的一份；只有另一份档案补足独立缺口时再增加。档案中的人物、设定、情节、专名与贴切表述可直接复用，以当前故事设计契约为准。主干 plugin 单独运行时此参考不可达，按下方表的"角色类型 / 学什么"两列即可启发设计。

### 推荐档案集（按 register 分类）

| 角色类型 / register | 名著档案（canon-distill 内位置） | 学什么 |
|---|---|---|
| 表达力弱但感受力强的主角 | `斯通纳/characters/威廉·斯通纳.md` | 克制表达与叙述怎样共同呈现人物经验；按来源场景辨明其作用 |
| 沉默是主声形态的配角 | `白鹿原/characters/吴仙草.md` | 沉默与关键发言怎样在特定关系中取得分量，不按句数复制 |
| 压力下程序前置 / 悲伤后置的女性 | `白鹿原/characters/朱白氏.md` | "把悲伤推后 + 把程序提前"如何让强韧不靠自我陈述 |
| 精神胜利法失效的反英雄 | `阿Q正传/characters/阿Q.md` | 标志性"心理机制"如何在压力下失效（不是单一负空间，是结构性崩塌）|
| 关怀语调推进暴力的施害者 | `现实一种/characters/山岗.md` | "亲切语言 + 精密道具"承载暴力的非传统反派写法 |
| 身体反应承载心理的脆弱者 | `月亮与六便士/characters/勃朗什·施特洛夫.md` | 身体反应怎样呈现处境与感受；内心叙述按作品需要保留 |

### 使用规则

1. **正向复用**：参考档案的结构、层次与贴切内容可直接复用；人物字段与当前故事设计冲突时，以当前故事设计为准。
2. **按匹配与信息缺口选档案**：弱匹配不强行引用；没有能补足当前人物设计的档案时按理论完成，不凑数量。
3. **档案的"声音特征"和"关键对白"两节是 voice_traits / voice_boundaries 字段的最佳填写范例**——比抽象的"4D + 压力下确定性"更直观。
4. **`<!-- 来源 -->` 注解中引用档案路径**：从 phase2_character.yaml → 字段 → ref: 档案路径，让审稿能反查。

## canon_archetype 字段

当 `Skill design-doc-reference` 产出 archetype candidate 卡，且 orchestrator promote 到 `pipeline/inspiration_ledger.yaml`（status=accepted/bound）后，phase2 角色字段挂 INS-A* 引用：

```yaml
protagonist:
  name: ...
  desire_system: ...
  canon_archetype:                # 新增字段（全 optional）
    - id: INS-A01
      weight: dominant
    - id: INS-A02                 # 可选的补充来源
      weight: secondary
      merge_boundary: "只学习 X，不学习 Y"  # weight=secondary 时必填

deuteragonist:                    # 双主角同样可选
  canon_archetype:
    - id: INS-A03
      weight: dominant

antagonist:                       # 对手按需
  canon_archetype:
    - id: INS-A04
      weight: dominant
```

原型按实际作用选取；多来源说明各自适用范围，`secondary` 保留 `merge_boundary`，避免相互冲突的特征被同时当作人格要求。

**字段引用闭环**：

- 引用的 INS-* ID 必须在 `pipeline/inspiration_ledger.yaml` 内
- 引用的卡必须 `type=archetype` 且 `status ∈ {accepted, bound}`
- 引用 INS-* 的 `archetype_target_slug` 必须对应本 phase2 中真实存在的角色 slot

字段不存在 → 不报错；存在则必须闭环自洽。

## 执行步骤

### 1. 设计主角

**人物塑造**（外在）：年龄、性别、职业、外貌、社会背景等可观察素质。

**欲望系统**（内在驱动力）：

- **自觉欲望**：主角知道自己想要什么（具体的、可追求的目标）
- **不自觉欲望**：当行为与选择支持另一股本人未察觉的追求时填写，并解释它与自觉目标的关系。只有自觉目标也可充分驱动故事；缺少依据时省略或为 null，不把不自觉欲望等同于作者认定的“真正需要”。
- **核心缺陷**：项目可选设计，用于确有稳定弱点妨碍追求的角色；无此机制时省略或为 null，不为字段补造缺陷。

当前目标尚不足以解释人物为何选择某种办法时，读取[从追求到具体办法](references/mckee-character.md#从追求到具体办法)，补清他同时顾惜的关系与生活条件、相信该办法有效的经历，以及可接受的代价。依据继续写入已有欲望、幕后经历和关系文字。

**人物轨迹**（`character_arc`）：角色在压力下的存在方式——**不必然是"转变"**，由 `character_arc.mode` 字段声明轨迹类型：

| `mode` | 轨迹描述模式 | 典型 |
|---|---|---|
| `transformative` | 从初始状态到最终状态的可识别转变：`初始状态 → 触发 → 认知失调 → 蜕变节点 → 最终状态` | 经典弧光、成长、觉醒 |
| `revelatory` | 稳定核**原本就在那里**，故事做"显形"不是"改造"——start/end 是读者/人物**认知**的变化，角色本身的核没动 | 侦探型主角 / 见证者 / 讽刺小说扁平主角 / 压力下被看清的人 |
| `static` | 不以转变为组织力，也不以"逐步显形"为主要组织力——固定透镜 / 讽刺常量 / 见证者 / 反结构稳定存在 | 卡夫卡式被结构碾压者 / 观察视角承担者 |
| `degenerative` | 退化 / 堕落 / 不可逆衰败轨迹 | 悲剧主角 / 道德滑坡叙事 |

**边界钉（`revelatory` vs `static`）**：有没有"揭示稳定核"这条**组织线**。有，就是 `revelatory`（故事在做显形动作）；没有，角色只是固定存在，就是 `static`。

**字段范围**：`protagonist.character_arc.mode` 必填；`deuteragonist` 存在时同样填写。对手与配角的必要变化由现有动机、关系和后续事件设计表达，不因主角分类补造相同字段。

**与 Phase 0 `primary_drive` 的关系**：`character_arc.mode` 是 phase-local operational enum——**Phase 2 不回读 `primary_drive` 做条件分支**。Phase 2 根据角色性质独立判定 mode。人物轨迹与全局组织力共同服务本作意图；出现具体冲突时回到相关设计判断。

**人物塑造与压力选择**：明确外在印象与有代价的选择之间的关系。麦基将主要人物的表里反差作为深度要求，采用这一方法时解释反差怎样在压力中显露。MUSE 同时保留表里一致的稳定人物作为项目创作选择：写明压力怎样揭示其坚持的程度、代价与后果，不为字段补造面具或外界误读。

**幕后故事**：选择足以解释当前选择、关系和盲区的关键事件。只需少量可被 Phase 4-6 “采收”的种子（闪回、对话中提及、动机具体化），不为凑数量补造经历。幕后故事应与 Phase 1 世界设定一致。

> 欲望系统 / 弧光 / 反差 / 幕后故事的原文依据与理论展开见 `references/mckee-character.md`。

**日常生活**：

基于 Phase 1 的 `daily_life`，具体化主角在这个世界里的日常：怎么吃饭、怎么工作、怎么消遣、怎么与人打交道。这些细节为 Phase 6 提供叙事素材，避免模型临场泛化。

**移情机制**：让读者能够理解人物在乎什么、处境怎样压迫其选择，以及自己可能怎样经历这份处境。好感、同情、好奇或熟悉感都可成为入口；理解人物不要求赞同其行为或先添优点。

**内在生存能力**（`inner_capacity`，可选案例机制）：当故事确已建立幻想、写作、信任等能力在维持人物生活时，记录它的作用；仅在具体事件会改变这一能力时设计失灵及其表现。创伤本身不推出能力失灵；故事无需此机制时省略。案例与迁移条件见 [名著手艺](../prose-craft/references/novel-craft-patterns.md#d1-内在生存能力的失灵inner_capacity_loss)。

```yaml
inner_capacity:
  primary: "幻想 | 写作 | 共情 | 信任 | 修复 | 信仰 | 自我说服 | <自定>"
  why_load_bearing: "为什么这个能力是 ta 的存在基础（1 句）"
  loss_trigger: "可选；具体事件怎样影响该能力；无失灵设计时为 null"
  loss_signal: "可选；失灵造成的可辨后果，呈现方式由 writer 决定"
```

**辨认与误读**（可选字段）：故事需要逐步修正人物认识、采收过去经历或运用误读时，选择下列相关字段写清实际机制。直陈、自省和外部叙述也可成立；没有这些作用时省略，不补造误会或物证。

```yaml
recognition_path:
  primary_method: "direct_action | object_evidence | second_hand_story | misread_evidence | procedural_record | silence | bodily_reaction"
  first_false_reading: "读者或其他角色最初可能误读什么"
  correction_method: "后续如何修正"

backstory_harvest:
  method: "embedded_storyteller | object_trace | witness_chain | contradictory_testimony | sensory_trigger | official_record"
  carrier: "具体承载物 / 讲述者 / 证据"
  withheld_part: "故意不交代的部分"

misread_matrix:
  - observer: "谁"
    target: "误读谁"
    evidence_seen: "看见 / 听见 / 拿到的证据"
    wrong_conclusion: "错误结论"
    narrative_value: "制造反讽 / 冲突 / 迟滞 / 悬念"
```

### 2. 设计对手

人物承担对抗时，写清其目标、行动依据和能实际改变主角处境的力量（压力选择依据见 `references/mckee-character.md §对手设计`）。对手可以相信自己正当，也可以明知残酷；关键行为有连贯理由即可。内在冲突、人际和环境压力按故事需要组合，不预定哪类最强。

### 3. 设计配角

根据配角的实际作用决定展开程度。承重关系、选择或声音应有足够人物依据；集中完成一种功能的配角可以简洁，也不要求每人与主角形成对照。

**主体性物件**（`subjectivity_object`，可选）：已有物件能让对手或配角的创造、选择与关系在退场后继续发生作用时记录。死亡或失踪本身不要求留下物件；话语、后果、他人的记忆或直接退场也可成立。

```yaml
subjectivity_object:  # 仅 supporting_cast / antagonist / victim 类角色
  what: "<具体物件描述>"
  created_when: "什么时候该角色创造的"
  where_it_lives: "在故事中以什么形式存在（藏在脑海 / 写在纸上 / 留给他人 / 物理实体）"
  potential_use: "如果该角色面临退场场景，此物件如何成为退场承载"
```

### 4. 设计声音特征

词汇、句法、修辞、节奏、压力反应、非语言、负空间与误读模式是观察人物声音的八个面。按来源与当前故事职责选择真正承重的面，不逐维填满（“演员级极简”原则见 `references/mckee-character.md §声音设计`）：


**避免过度设计**：

- **定义有来源的倾向，不定义映射**：写来源中反复成立的注意、措辞与行动习惯；不写“越接近执行，语言越短”“恐惧=技术隐喻”这类情境→句法公式。一个时期或一个场景出现的短句，只能证明当时的表达，不能冻结人物整条弧光。
- **身份标签是背景，不是修辞引擎**：角色的职业/身份影响他的思维方式，但他首先是一个人。不要把身份标签定义为角色的默认修辞模式。一个程序员在恐惧时不会每次都用代码隐喻——他会像任何人一样恐惧。
- **认知语言来自人物真正拥有的材料**：人物用其教育、信仰、职业实践和亲历形成判断。设计时先带入角色本人，再让他只凭当前感官、记忆与已建立事实继续生活；新事实怎样被注意、关联、相信或误读，也是人物声音。职业知识负责人物实际处理的具体对象，不自动把情绪改写成行业分析标签；helpful assistant 的均衡结论和作者判断也不能冒充人物思想。
- **为 Phase 6 留有余地**：声音特征是倾向性指南。Phase 6 在执行时应根据场景的情感需要自然调整，高潮中是否保留标志性修辞同样由人物处境与表达作用决定。

**可选观察面的 YAML 示例**（只填写有来源且会被下游使用的项；详细定义见 `references/voice-design.md`）：

```yaml
negative_space_voice:
  never_says_directly:
    - "关系尚未确定时，很少直接承认害怕失去对方；关系改变后重新判断"
  converts_into:
    - "来源支持的候选表达及适用对象；不规定情感一律改成动作"
pressure_certainty:
  when_accused: "不急于辩解，先指出对方证据链的一个漏洞"
nonverbal_voice:
  - "做决定时先处理手边物件，而非看人"
misread_pattern:
  often_misread_as: "{别人最容易给 ta 的标签}"
  by_whom: "{最常误读 ta 的人}"
  ta_corrects: false
```

→ 声音框架详细指南见 `references/voice-design.md`

### 5. 用人物因果建立极化差异

当故事中有两个以上重要角色时，让各自的经历、利益与关系位置真实影响他们在同一压力下的注意、判断、选择或代价。从注意对象、利益排序、知识来源、误判方式和关系策略中选择真正承重的差异；这些是观察镜头，不是必填维度。人物可以作出相同选择，只要理由、承担的代价或关系意义仍由各自经历产生。

例如，同一份被涂改的失踪名单到手后，配给站管理者先算谁会因公布真相失去口粮，失踪者家属先找删改痕迹和经手人。前者暂压名单以保住发放，后者当场公开以逼出证人。差异体现在他们改变了什么，职业名词和口头禅只提供背景。

用换角测试收束：互换两人的注意对象、判断路径或关键选择后，若故事因果仍然原样成立，当前差异只停在标签层。同一机构、社区或时代的人物可以共享制度语域和公共事实；他们对共同材料的服从、利用、误读或抵抗仍由各自的因果产生。

### 6. 构建关系网络

绘制人物之间的关系图，标注：
- 权力动态（谁对谁有权力？）
- 亲密与信任（谁在何种事务上信任谁，双方认识是否相同）
- 潜在变化（关系可能如何转变？）

关系会改变关键选择时，在现有关系文字中保留相关经历、顾忌和实际支配条件；拥有资源、能够调动与愿意相助分别判断。需要解释同一人为何在不同关系中采用不同办法时，沿[人物依据](references/mckee-character.md#从追求到具体办法)展开。

### 7. 为实际 actor 消费者构建角色包

先按调用链判断产物用途：story-writing 的 Phase 6 有 actor，执行下述构建与 gate；screenplay-writing 直接消费人物设计，完成 step 4–6 后返回，不生成 runtime 角色包或 adapter。用户自定义调用链按其实际消费者决定是否需要构建。

Phase 2 **决定**要为哪些角色生成资产（主角、对手、值得构建 Skill 的配角），然后**调用** `character-persona` 构建器落盘。产物目录结构、adapter 派生规则、字段 / 章节白名单等详见 [`character-persona/SKILL.md`](../character-persona/SKILL.md)，**字段权威以 character-persona 为准**。

`pipeline/phase2_character.yaml` 保留实际成立的作者设计与叙事用途；可选欲望、缺陷或能力机制缺省时不补齐。character-persona 将这些材料编译成 actor-facing runtime SKILL：经历与信念、自觉追求、判断习惯与行为盲区、声音和边界。新 runtime 资产不复制弧光终点、作者诊断标签或通用表演规则；`character_arc.start_state` 只用于初始化 `state.md`。

**4 产物（每角色齐全才放行）**：

| # | 产物 | 路径 |
|---|---|---|
| 1 | actor-facing runtime Skill | `pipeline/story-character-skills/.claude/skills/{slug}/SKILL.md` |
| 2 | 初始主观状态 | `pipeline/story-character-skills/.claude/skills/{slug}/state.md` |
| 3 | 构建元数据 | `pipeline/story-character-skills/.claude/skills/{slug}/build-meta.yaml` |
| 4 | 兼容 adapter | `pipeline/characters/{中文角色名}.md`（sha256 与 build-meta.yaml `adapter_sha256` 一致） |

**核验**：构建完成时执行；Phase 5→6 复用未变资产的有效结果，仅对新增、变更、缺失或先前失败的资产重新检查：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_phase2_assets.py <work_dir>
```

退出码：
- **0** → 通过；在回复中明示 "phase2 hard gate PASS"
- **非 0** → abort：不进入下一阶段；在回复中粘贴脚本 stdout 失败原因；修复后重跑；**严禁**"继续往下，回头补"

**详细字段断言与错误码以脚本为权威**：
[`skills/MUSE-writing/scripts/verify_phase2_assets.py`](../../scripts/verify_phase2_assets.py)。
脚本防的是 Phase 2 角色资产缺漏 / 4 产物不完整 / sha 不一致；执行者只需关心脚本调用 + 退出码处理。

**未构建例外**：仅"只在他人叙述中出现 / 纯背景人物 / 无对白无关键行动"的配角可跳过 Phase 2 构建，需在 build-report.md "未构建"表填非空 `skip_reason`（builder 自检；脚本兜底校验）。

**绝对硬线**：凡在 `phase5_scenes.yaml` `participants` 中登场的角色不得作为 Phase 2 例外——Phase 5→6 过渡时补建 gate 会拉回。

**硬约束**：`pipeline/characters/{角色名}.md` 不再手写；凡由 Phase 2 直接写入该目录的内容视为绕过构建器。

## 输出

→ YAML 输出结构见 `references/output-schema.md`

**step 4-6 交付物（设计层）**：
- `pipeline/phase2_character.yaml`：结构化数据（protagonist, antagonist, **deuteragonist**（可选）, supporting_cast, relationships, contrast_axes, voice_boundaries）；其中 `protagonist.character_arc.mode` 必填，`deuteragonist.character_arc.mode` 若存在也必填（enum：transformative / revelatory / static / degenerative，边界见 Step 1 "人物轨迹"段）；`deuteragonist` 是麦基双主角 / 守护者形态的可选字段（结构同 protagonist），下游 character-persona / story-writing 按 optional 处理

**step 7 交付物（调用链需要 actor 时）**：
- `pipeline/story-character-skills/.claude/skills/{slug}/SKILL.md` / `state.md` / `build-meta.yaml`：每角色 actor-facing 运行时 Skill 包
- `pipeline/characters/{中文角色名}.md`：兼容 adapter（由 character-persona 从 SKILL.md 派生，保持 actor-facing 的身份与声音内容，供兼容审稿链读取；writer 直接读取 runtime SKILL.md）
- `pipeline/story-character-skills/build-report.md`：构建决策记录 + 已构建 / 未构建角色清单

**硬约束**：`pipeline/characters/{角色名}.md` 不再手写；凡由 Phase 2 直接写入该目录的内容一律视为**绕过构建器**，违反 hard gate。

**既有产物 fallback**：`phase2_character.yaml` 的 `character_arc` 缺 `mode` 字段时兼容层按 `transformative` 解释，下游读取既有产物不视为缺必需字段。新生成路径必须显式依据角色性质选择最贴近的一类，不允许以"不确定"为由跳过判定。

## 常见错误

| 错误 | 后果 | 修正 |
|------|------|------|
| 人物轨迹与核心价值脱节（按 mode 各有表现：transformative 下是成长方向偏离主题 / revelatory 下是稳定核与主题无关联 / static 下是稳定核所抵抗的压力和主题无关联 / degenerative 下是退化轨迹与主题无关联）| 人物轨迹不承担价值表达，故事主题失重 | 轨迹的终点（或 static 的维持对象 / revelatory 的显形核）应体现核心价值的某种立场 |
| voice_traits 给出"情感→隐喻"映射表 | Phase 6 逐条执行，全文被同一类修辞淹没 | 定义有来源的倾向、条件与强度，不给情感—修辞映射 |

→ 理论深度参考见 `references/mckee-character.md`
