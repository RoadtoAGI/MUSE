---
name: phase3-spine
description: MUSE Phase 3 — 故事脊椎 + 幕/Arc 框架。设计激励事件、戏剧问题、按 spine_mode（desire/information/motif）构建故事组织力，并决定故事需要几个幕/Arc 及每个 Arc 的重大轨迹跃迁。由 orchestrator 在 pipeline 推进到 Phase 3 时触发（上游 Phase 0/1/2 产物已就绪，下游 Phase 4 结构设计的输入）。
---

# Phase 3: 故事脊椎 + 幕/Arc 框架

## 核心原则

脊椎 = 故事的**组织力**——**默认适用于单主角、冲突驱动、目标明确的戏剧型故事**（麦基框架"主角恢复生活平衡的深层欲望 + 不懈努力"；原文见 `references/mckee-spine.md §故事脊椎`）。群像 / 调查 / 拼图 / 反结构作品可用**信息脊椎**（真相显形 / 碎片聚拢）或**母题脊椎**（观念 / 意象 / 风格驱动的组织力）替代——脊椎类型由 `spine_mode` 字段显式声明（enum：`desire | information | motif`；边界定义见 Step 3）。

不论 `spine_mode`，每个场景要么推进脊椎，要么与脊椎形成张力——与脊椎无关的场景不属于这个故事（所有 mode 通用的场景取舍测试）。

## 输入契约

从 Phase 0 接收（核心依赖）：
- `premise` — 激励事件应回应前提
- `core_value` — 脊椎围绕核心价值运动
- `controlling_idea` — 结局的事件、认识及后果怎样体现本作的价值与成因
- `primary_drive` — **仅作 Step 3 `spine_mode` 判定的近端默认建议**，不作条件分支权威源（Phase 3 独立判定 spine_mode，不回读 primary_drive 做 if-else；发生具体冲突时回查创作意图与人物条件）

从 Phase 1 接收（参考依赖）：
- `setting` — 激励事件发生在这个世界内

从 Phase 2 接收（**mode-aware**，依赖强度按 `spine_mode` 调整）：
- `protagonist.desire_system` — **核心**（`spine_mode=desire`）/ **参考**（`information` / `motif`）：desire 下用于激发主角欲望、构建脊椎；非 desire mode 可参考但不强制构建欲望脊椎
- `protagonist.characterization` — **核心**（`spine_mode=desire`）/ **参考**（其他）：desire 下作为脊椎起点（主角初始生活平衡）；非 desire mode 仅作角色画像参考
- `protagonist.backstory / character_arc.start_state` — 当前判断的形成依据与故事起点
- 人物初始处境、已知信息与关系感知：已构建 actor 资产时按 `pipeline/story-character-skills/build-report.md` 的 name→slug 映射读取主角 `state.md`；剧本等设计调用链直接读取 Phase 2 的经历、`character_arc.start_state` 与相关作者输入。只使用人物此刻可知的信息。
- `deuteragonist`（若存在）— **条件依赖**：双主角 / 守护者形态下按 protagonist 等价结构读取，参与 spine 组织力判断
- `antagonist` — **条件依赖**：若对抗由人物承载（多数 desire mode + 部分 information mode）则读取；纯 information / motif 故事如对抗来自信息缺口或形式约束本身，可不读

## Canon/design reference（按问题取材）

核心剧情尚未确定或被退回时，读取[大纲构思与回读](../story-writing/references/outline-exploration.md)：从参考中提出新的思想联系，展开有实质差异的候选和关键剧情后果，由作者裁决。已选方向继续展开，固定结局保留。

需要补取参考时，附临时自由文本 `narrative_problem`，写清当前认识、已定条件与尚缺的思想或剧情关系。它服务本次阅读与回读，不写入 Phase 3 schema。

已有适用参考直接消费。首次构思缺少参考、新问题出现或现有材料不足时，通过 `Skill design-doc-reference` 补取材料；用户明确不要参考时跳过。调用时传入：

```
phase=3
genre=<Phase 0 genre.primary>
signals=<JSON: 至少含 spine_mode, protagonist_desire 或 information_goal, crisis_type 中能填的>
```

调用成功 → Read `pipeline/references/phase3_design_ref.md`，学习：

- 原作让读者获得什么关于人或世界的认识，怎样通过事件、人物选择和后果形成
- 激励事件怎样改变人物处境，后续选择怎样相互推动；揭露如何影响已有关系、人物自我理解与下一步行动
- **desire / information / motif spine** 三种模式各自的脊椎组织差异
- **幕/Arc 尺度的变化**：原作的重大轨迹在哪里改向，怎样改变后续序列的行动条件或解释范围

**参考不可用时**：按已有材料与理论继续设计；作者指定的必要来源缺失时，保留该领域的待决问题。扩展包可用性未知时通过宿主入口确认；已确认不可用且条件未变时，沿用该结果。

## reveal_ladder_seed 字段

`reader_spine.withheld_answer` 是单点字段——只说"哪个答案不能早说"。`reveal_ladder_seed` 是多段字段，只在事实、因果关系或身份需要分阶段释放时，承担**真相显形路径**的高层骨架。每一段都要改变人物行动、读者归因、关系判断或价值评价；普通母题重现、象征回声和伏笔不触发本字段。`information` mode 是常见适用情形，也需通过上述判据；单次揭示直接使用 `reader_spine`。

```yaml
reader_spine:
  reader_waits_to_know: "..."
  recognition_object: "..."
  withheld_answer: "..."          # 已有
  reveal_ladder_seed:             # 整块 conditional；未命中触发判据时省略，保留三个位置键，未使用的位置可为空数组
    early_signals:                # 早期信号：读者首次接触相关物件 / 行为 / 异常，价值未解释
      - "..."
    mid_reframes:                 # 中段重构：物件 / 行为意义被部分修正 / 升级
      - "..."
    final_confirmation:           # 终局确认：真相在具体载体上显形
      - "..."
```

**与 inspiration_ledger 的关系**：

phase3 `reveal_ladder_seed` 是**本作真相显形路径的高层骨架**，不强制引用 INS-*。本作已独立满足上述分阶段释放判据后，灵感卡的 `disclosure_ladder` 才可与本字段对齐：按本作实际阶段对齐 INS-* 的 disclosure_ladder；early/mid/final 表示相对位置，不要求凑足三次揭示。

phase5 scene_card 后再具体绑定 INS-* `disclosure_ladder[].scene_id` 到具体场景。

字段不存在时按一般披露设计；启用时保留 early/mid/final 键，仅填写实际发生的阶段。

## 执行步骤

### 1. 设计激励事件

欲望驱动故事用具体事件打破主角原有平衡，使其必须回应；事件可由主动决定（decision）或遭遇（accident）引发（原著依据见 `references/mckee-spine.md §激励事件`）。信息/母题组织的作品按实际结构记录信息缺口打开或母题被激活的时点，不另造不可逆灾变来套用欲望模型。

```
日常平衡 → 激励事件 → 失衡（正向或负向偏离）
```

### 2. 确定欲望对象（`spine_mode=desire` 时必填；其他 mode 可空或 null）

激励事件打破平衡后，按 `spine_mode` 决定是否以及如何提取欲望对象（`spine_mode` 的判定在 Step 3 收敛；本步骤先按用户 query / Phase 0 `primary_drive` 近端建议直观判定激励事件带起的是欲望、谜团还是母题激活）：

- **`desire` mode（麦基默认）**：激励事件在主角心中激起恢复平衡的欲望（原文见 `references/mckee-spine.md §激励事件`）。提取：
  - **自觉欲望对象**：主角明确追求的（必须具体——读者能想象主角得到它时的画面）
  - **不自觉欲望对象**：仅在 Phase 2 的行为与动机设计已支持时使用；缺省或 null 均合法
  - **张力**：存在双层欲望时解释二者关系，不为字段齐全补造冲突
- **`information` mode**：激励事件暴露待显形的真相或打开信息缺口；此时 `desire_object` 可为 null，核心是在 Step 3 的 `spine_statement` 中表述真相显形路径
- **`motif` mode**：激励事件引入或激活将在故事中展开的母题；此时 `desire_object` 可为 null，核心是在 Step 3 中表述母题如何组织叙事

### 3. 构建故事脊椎

**Step 3.1：判定 `spine_mode`**（Phase 3 独立判定——**不回读** Phase 0 `primary_drive` 做条件分支；`primary_drive` 仅作近端默认建议，Phase 3 根据故事组织力性质独立落选，按实际事件和创作意图判断其作用）：

| `spine_mode` | 语义 | 典型场景 |
|---|---|---|
| `desire`（麦基默认）| 主角有明确欲望对象，不懈努力追求 | 冲突驱动戏剧、单主角目标追求 |
| `information` | 真相逐步显形 / 碎片逐步聚拢 | 侦探 / 调查 / 档案拼图 / 解谜 |
| `motif` | 观念 / 意象 / 风格驱动的组织力 | 观念小说 / 文献拼贴 / 群像 / 氛围累积 |

形式约束型作品按实际组织作用选择 `motif` 或 `information`。

**Step 3.2：按 mode 构建脊椎陈述（`spine_statement`）**——所有 mode 都必须产出一句话 `spine_statement`，语义按 mode 解释：

| `spine_mode` | `spine_statement` 范式 |
|---|---|
| `desire` | "主角想要 X，为此克服 Y，最终获得/失去 X" |
| `information` | "真相 T 如何逐步显形：从初见象到完整理解的路径" |
| `motif` | "母题 M 在故事中如何展开、呼应、变形" |

脊椎先按输入契约读取 Phase 2 的经历、初始状态及已有的主人公状态，确定人物进入故事时已有的经历、信念、已知信息与盲区。随后从人物内部生成决断：暂时进入这个人，让其信念和欲望成为判断起点；再让其只凭当前感官和新获得的信息继续生活、解释并选择。不要先用作者或 helpful assistant 的公共伦理、风险审计得出“客观答案”，再把人物经历补成论据；也不要让新刺激无因推翻此前已经形成的信念。角色化预演不写入产物，脊椎只保留“已有价值 → 新事实在人物眼中意味着什么 → 选择 → 后果”的因果结果。方法见 `references/mckee-spine.md §人物内部的决断链`。

**Step 3.3：desire mode 下的 spine_type 子类判定**（仅 `spine_mode=desire` 时适用）：
- 主角只有自觉欲望：自觉欲望 = 脊椎（`spine_type: conscious`）
- 主角存在贯穿选择的不自觉追求：用它统一脊椎（`spine_type: unconscious`）；空字段或心理标签不足以成立此类，须说明它怎样组织实际选择

`information` / `motif` mode 下 `spine_type` 字段为 null（不适用）。

**Step 3.4：场景取舍测试**（所有 mode 通用）——如果一个场景既不推进也不挑战脊椎，它可能不属于这个故事：
- `desire` mode：不推进"欲望 + 不懈努力"的场景可删
- `information` mode：不贡献"真相显形"关键碎片 / 不给出新信息差的场景可删
- `motif` mode：不呼应 / 不变形 / 不展开母题的场景可删

**Step 3.5：读者认知脊椎（`reader_spine`）**（所有 mode 通用）——脊椎是角色 / 信息 / 母题的组织力；`reader_spine` 是**读者**在整篇追踪、等待被确认 / 推翻的认知线。角色脊椎和读者脊椎可以错位（角色追欲望 X，读者真正等的是关于 X 的某个真相显形 / 误解推翻）。

```yaml
reader_spine:
  reader_waits_to_know: "读者真正等什么被确认 / 推翻"
  recognition_object: "最终通过什么动作 / 物件 / 图像 / 选择确认"
  withheld_answer: "哪些答案不能过早解释"
```

`recognition_object` 说明读者凭哪些事件、经验或叙述关系形成认识；只写“读者意识到 X”尚未解释形成依据。物件、行动、内心展开、转述和叙述者评论均可承载，具体手法由作品决定。`withheld_answer` 只记录确需延迟的答案及理由；无需保密时为空或 null。

`reader_waits_to_know` 应落在结果、真相、选择或人物认识怎样改变。作品可以让一种价值在行动、代价和后果中接受检验；不要把“艺术是否有用”“某种文明是否更善良”写成等待剧情证明的客观命题。

答案延后释放需要改变人物行动、读者归因、关系判断或价值评价。只把背景说明推迟到后文，且释放前后剧情可以原样成立，不写入 `withheld_answer / reveal_ladder_seed`。

### 4. 设定戏剧问题

记录读者持续追踪的核心关切。悬念驱动时可由激励事件提出、在高潮回答；结果早已揭示时，后续关切可以转为形成过程、代价或人物认识。开放结尾按已选意图收束，不强制给出唯一答案。

`dramatic_question` 同时是**全篇读者追问**——读者整篇跟随的最大问题。Phase 5 的 `reader_track` 是其在单场尺度的具体化（每场读者跟随的局部问题，最终汇入这条全篇主线）。

### 5. 确定对抗力量

根据故事需要，确定主角将面对的对抗力量。麦基将对抗分为内在（自我）、个人（人际）、外在（社会/环境）三层，但不必拘泥于此分类——按故事实际需要决定对抗的类型和数量。

### 6. 设计幕/Arc 框架

> 「根据亚里士多德的原理……作品越长，重大的逆转便越多。」
> 「三幕故事节奏就已成为故事艺术的基础。但它只是一个基础而已，不是公式。」
> —— 《故事》第九章

根据故事的长度和复杂度，决定需要几个幕/Arc。每个 Arc 必须有：
- **轨迹起点→终点**：进入和离开时关键叙事状态不同（重大逆转 / 重大跃升 / 重大变形），语义按 `spine_mode` 解释：
  - `desire` mode：**价值状态**起点→终点（重大价值逆转，麦基默认）
  - `information` mode：**信息 / 认知状态**起点→终点（重大信息跃升 / 真相显形的关键节点）
  - `motif` mode：**母题状态**起点→终点（重大母题变形 / 呼应 / 转调）
- **高潮事件**：一句话描述导致本 Arc 轨迹跃迁的关键事件（desire 下是价值逆转、information 下是真相披露、motif 下是母题变奏）
- **后续影响**：高潮怎样改变下一 Arc 或下游序列的行动条件、解释范围、价值排序、母题意义或选择空间

Arc 数量由真正的重大**轨迹跃迁**决定。外部声量可以降低，只要困境性质、代价、不可逆性、信息状态或选择空间继续变化。

**Schema 字段语义**：Arc 的 `value_at_start / value_at_end` 字段名沿用，语义按 `spine_mode` 解释，承载 Arc 轨迹的起点与终点关键状态。Phase 4 读取本字段时同时读取 `spine_mode / reader_spine / story_climax_design.resolution`。

采用道德含混时，让同一选择的所得、损失与未偿代价在后果中可见。设计结果允许多种成立评价，无需另交两难分析表。

### 7. 设计故事高潮

故事级的危机、高潮和结局——与 `inciting_incident`、`spine_statement` 同级的故事层决策：

- **危机**：结局前集中显现的压力、选择或认识变化。确有互斥选择时，`option_a / option_b` 在作者层记录选择、排斥另一条路的已知条件及其后果；能够兼做、合作或延后的行动按实际条件推演。观察或真相显形的收束没有两难时，将这些选项留空，在 `dilemma` 中描述实际待解处境；字段排列与说明不取得正文表达权
- **高潮**：压力下的行动或认识变化及其结果，让本篇组织的关系在结局处显现
- **结局**：高潮后的新平衡状态

> 「故事高潮必须充满意义……当价值处于最大负荷时所发生的绝对而不可逆转的价值摇摆。」
> —— 《故事》第十三章

**高潮形态参考**：既有 `climax_form` 提供下列兼容标签；成功、失败与收束方式按实际因果选择，不适用时省略该可选字段：

- **`hero_fails_world_completes`**：主角失败，但世界机制 / 副角色欲望 / 长期伏笔完成结果（《指环王》末日裂隙：弗罗多失败，咕噜夺戒坠落毁掉魔戒）
- **`withdrawal_as_resolution`**：事件尺度收缩，主角主动退场作为解决；不是更大的对抗，而是从对抗中抽身（《三体Ⅲ》终局从宇宙广播收缩到 5kg 生态球）
- **`silence_after_truth`**：最终胜利伴随不可修复损伤；真相揭示后角色沉默不解释，由读者承担余味（《指环王》终章山姆回家但弗罗多必须离开）

收束须有足够的前因与认识依据。主角无力行动、他者介入或世界机制完成结果均可成立，前提是已建立其条件与后果；不靠终局突然添加解法。`reader_spine.recognition_object` 说明读者凭什么理解这一结果的意义。

## 输出

→ YAML 输出结构见 `references/output-schema.md`

交付物写入 `pipeline/phase3_spine.yaml`，包含：inciting_incident, spine_mode, spine_statement, reader_spine, dramatic_question, opposing_forces, arcs[], story_climax_design。`desire_object` 与 `spine_type`：仅 `spine_mode=desire` 时必填，其他 mode 下为 null。`reader_spine` 所有 mode 通用；`story_climax_design.climax.climax_form` 可选（默认 `hero_succeeds`，失败型高潮三档详见"故事高潮"段）。

**既有产物 fallback**：`phase3_spine.yaml` 缺 `spine_mode` 时兼容层按 `desire` 解释，下游读取既有产物不视为缺必需字段。新生成路径必须依据故事组织力性质显式选择最贴近的一类，不允许以"不确定"为由跳过判定。

## 常见错误

| 错误 | 后果 | 修正 |
|------|------|------|
| 核心问题回答后没有后续关切 | 读者失去继续追踪的理由 | 按故事意图保留悬念，或让已知结果引向形成过程、代价和认识 |
| 激励事件与前提脱节 | Phase 0 的构想被浪费 | 激励事件应是前提的具体化 |
| 先给外部正确答案，再用人设补论证 | 人物借第一人称说出作者或 helpful assistant 的风险审计，既有信念与行动沦为事后拼接 | 先进入人物，以其经历、已知信息、概念和盲区完成主观推演，再收敛价值形成、事实判断、选择与后果 |
| Arc 数量预设而非由故事决定 | 结构刚性 | 先确定有几个重大轨迹跃迁（按 `spine_mode` 解释：desire=价值逆转 / information=信息跃升 / motif=母题变形），再划分 Arc |
| 危机/高潮放在 Phase 4 设计 | 故事层决策与序列层混杂 | 危机/高潮是故事级决策，在本阶段完成 |

→ 理论深度参考见 `references/mckee-spine.md`
