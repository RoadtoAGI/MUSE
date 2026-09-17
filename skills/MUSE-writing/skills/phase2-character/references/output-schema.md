# Phase 2 输出 Schema

交付物文件：`pipeline/phase2_character.yaml`

```yaml
protagonist:
  name: 姓名
  characterization:
    age: 年龄
    gender: 性别
    occupation: 职业
    appearance: 外貌特征
    background: 社会背景摘要
  desire_system:
    conscious: 自觉欲望（明确追求的具体目标）
    unconscious: null  # optional；行为支持的本人未察觉的追求；只有自觉目标也合法
    core_flaw: null    # optional；确实妨碍追求的稳定弱点，不为完整性补造
  character_arc:
    mode: transformative | revelatory | static | degenerative
    start_state: 初始状态（或 revelatory/static 下的稳定核初见）
    end_state: 最终状态（或 revelatory 下稳定核显形后的读者/人物认知；static 下同 start_state）
    transformation: 轨迹核心描述——transformative/degenerative 写转变 / 退化核心；revelatory 写揭示了什么稳定核、怎么揭示；static 写稳定核是什么、在压力下如何维持
  characterization_vs_truth:
    surface: 外在人物塑造（别人眼中的他）
    deep_truth: 压力下暴露的性格真相
    gap: 两者的反差、对照或一致关系及依据；表里一致时说明有代价的选择揭示了什么
  backstory:
    - event: 过去事件描述
      impact: 对当前人物的影响
      narrative_use: 可如何被 Phase 4-6 采收（闪回/对话/动机）
  daily_life: 主角在这个世界里的日常：怎么吃饭、工作、消遣、与人打交道
  voice_traits:
    vocabulary: 词汇特征描述（可选；有来源且当前故事承重时填写）
    syntax: 句法特征描述（可选；不写情境→句法公式）
    rhetoric: 修辞特征描述（可选；职业身份不自动生成隐喻）
    rhythm: 节奏特征描述（可选；只记录来源支持的倾向）
    catchphrase: 口头禅（可选）
  empathy_mechanism: 读者理解人物追求、处境与选择的入口
  voice_boundaries: "角色不会怎么说话的负空间描述（例：'不会在每次恐惧时都用技术隐喻'）"
  signature_lexicon: ["索引", "变量", "回滚"]   # （可选）签名声音可机检词面——领域名词 / 隐喻域词干；供文体量化指标按词表计数，缺省则机器环跳过
  inner_capacity:                    # optional；故事已建立此能力维持人物生活时使用
    primary: 幻想 | 写作 | 共情 | 信任 | 修复 | 信仰 | 自我说服 | <自定>
    why_load_bearing: 1 句——为什么这能力是 ta 的存在基础
    loss_trigger: null  # optional；具体事件怎样影响该能力，创伤不自动导致失灵
    loss_signal: null   # optional；已设计失灵的可辨后果，具体表达由 writer 决定
  recognition_path:                  # optional
    primary_method: direct_action | object_evidence | second_hand_story | misread_evidence | procedural_record | silence | bodily_reaction
    first_false_reading: 读者或其他角色最初可能误读什么
    correction_method: 后续如何修正
  backstory_harvest:                 # optional
    method: embedded_storyteller | object_trace | witness_chain | contradictory_testimony | sensory_trigger | official_record
    carrier: 具体承载物 / 讲述者 / 证据
    withheld_part: 故意不交代的部分
  misread_matrix:                    # optional, list of observer→target rows
    - observer: 谁
      target: 误读谁
      evidence_seen: 看见 / 听见 / 拿到的证据
      wrong_conclusion: 错误结论
      narrative_value: 制造反讽 / 冲突 / 迟滞 / 悬念
  canon_archetype:                   # optional
    - id: INS-A01
      weight: dominant
    - id: INS-A02
      weight: secondary
      merge_boundary: "只学习 X，不学习 Y"

antagonist:
  name: 姓名
  relationship_to_protagonist: 与主角的关系
  power_source: 威胁主角的能力来源
  motivation: 从对手视角看的合理动机
  desire: 对手追求的目标
  voice_traits:
    vocabulary: 词汇特征描述
    syntax: 句法特征描述
    rhetoric: 修辞特征描述
    rhythm: 节奏特征描述
    catchphrase: 口头禅（可选）
  voice_boundaries: （可选）对手声音的负空间描述
  signature_lexicon: []   # （可选）同 protagonist 同构——签名声音可机检词面列表
  subjectivity_object:               # optional；已选物件确实承担人物/关系作用时填写
    what: 具体物件描述
    created_when: 什么时候该角色创造的
    where_it_lives: 在故事中以什么形式存在（藏在脑海 / 写在纸上 / 留给他人 / 物理实体）
    potential_use: 如果该角色面临退场场景，此物件如何成为退场承载
  canon_archetype:                   # optional
    - id: INS-A04
      weight: dominant

deuteragonist: null
# optional。若存在，必须使用与 protagonist 完全相同的字段结构；不允许只写 name。
# deuteragonist.character_arc.mode 与 protagonist.character_arc.mode 使用同一 enum 和同一必填规则；canon_archetype 同样 optional。

supporting_cast:
  - name: 姓名
    function: 叙事功能
    relationship: 与主角的关系
    voice_traits_summary: 声音特征摘要（1-2句）
    subjectivity_object:             # optional；已选物件确实承担人物/关系作用时填写
      what: 具体物件描述
      created_when: 什么时候该角色创造的
      where_it_lives: 在故事中以什么形式存在（藏在脑海 / 写在纸上 / 留给他人 / 物理实体）
      potential_use: 如果该角色面临退场场景，此物件如何成为退场承载

contrast_axes: 主要角色之间的因果差异描述（差异怎样影响注意、判断、选择、代价或关系意义；相同选择也可成立）
relationships:
  power_dynamics: 权力动态描述
  key_tensions:
    - 关键关系张力
  potential_shifts:
    - 关系可能的转变
```

## 字段说明

| 字段 | 必需 | 下游使用 |
|------|------|---------|
| `protagonist.characterization_vs_truth` | 是 | Phase 5（设计压力选择）、Phase 6（行为的作者侧依据）；character-persona 只编译当前已成立的判断和行为材料，不复制诊断标签或补造隐藏动机 |
| `protagonist.backstory` | 是 | Phase 4（危机设计可引用过去事件）、Phase 6（闪回/对话素材）；character-persona 只向 runtime 提供角色已知的 `event + impact`，省略 `narrative_use` 与未知事实 |
| `protagonist.daily_life` | 否 | Phase 6（叙事细节素材） |
| `protagonist.desire_system` | 是 | Phase 3（构建故事脊椎）、Phase 4（设计危机两难）；character-persona 把 `conscious` 编译为自觉追求，把 `unconscious / core_flaw` 行为化，不复制作者标签 |
| `protagonist.voice_traits` | 是（mapping 至少含一项有来源的承重特征；不要求 vocabulary / syntax / rhetoric / rhythm 全齐） | Phase 6（对白差异化）、dialogue-craft（潜台词设计） |
| `protagonist.character_arc` | 是 | Phase 4（弧光轨迹在高潮体现；transformative/degenerative=转变、revelatory=显形、static=在极端压力下保持）；Phase 5 通过 value_start/end 语义间接消费轨迹语义。character-persona 只用 `start_state` 初始化 state.md，不把 mode、end_state 或 transformation 写入 runtime SKILL |
| `protagonist.character_arc.mode` | 是 | **phase-local operational enum**——声明人物轨迹类型。enum：`transformative`（经典弧光，从起点到终点的可识别变化）\| `revelatory`（暴露：人物稳定核原本就在那里，故事做"显形"不是"改造"；**vs static**——有无"揭示稳定核"的组织线，有即 revelatory）\| `static`（静态：不以转变为组织力，也不以逐步显形为主要组织力；固定透镜 / 讽刺常量 / 见证者 / 反结构稳定存在；**vs revelatory**——没有"揭示稳定核"的组织线，只是固定存在）\| `degenerative`（退化：堕落 / 悲剧 / 不可逆衰败轨迹）。**消费者**：Phase 4/5 作者侧结构设计。character-persona 不把 mode 暴露给 actor。**既有产物 fallback**：`phase2_character.yaml` 的 `character_arc` 缺 `mode` 字段时兼容层按 `transformative` 解释，新生成路径必须显式依据角色性质选择最贴近的一类，不允许以"不确定"为由跳过判定 |
| `antagonist` | 是 | Phase 3（对抗力量设计）、Phase 5（对手出现的场景） |
| `deuteragonist` | 否 | 双主角 / 守护者形态时使用（结构同 protagonist；若存在则 `character_arc.mode` 必填）；消费方与 protagonist 等价（Phase 3/4/5/6 各处按 optional 处理）；下游 character-persona 按 optional 派生 runtime skill 包 |
| `supporting_cast` | 是 | Phase 5（场景人物分配）、Phase 6（对白涉及的角色） |
| `relationships` | 否 | Phase 5（关系动态影响场景编排） |
| `protagonist.voice_boundaries` | 否 | Phase 6（负空间约束：角色不会做什么） |
| `protagonist.signature_lexicon` | 否 | 文体量化指标（signature 词表计数）；缺省机器环跳过 |
| `protagonist.recognition_path` | 否（enrichment） | Phase 6（把主角"被认出"的方式落到 action/evidence/转述/误读/沉默/身体反应，避免被解释化）；7-enum `primary_method`；下游暂未硬消费，纯数据层 |
| `protagonist.backstory_harvest` | 否（enrichment） | Phase 4-6（指明 backstory 用哪种采收方式呈现：内嵌讲述者 / 物件痕迹 / 见证链 / 矛盾证词 / 感官触发 / 官方记录）；6-enum `method`；下游暂未硬消费 |
| `protagonist.misread_matrix` | 否（enrichment） | Phase 6（提供 observer→target 误读对，制造反讽 / 冲突 / 迟滞 / 悬念）；list 结构允许 N×N 对；下游暂未硬消费 |
| `protagonist.canon_archetype` / `deuteragonist.canon_archetype` / `antagonist.canon_archetype` | 否 | 引用 `pipeline/inspiration_ledger.yaml` 中 `type=archetype` 的 INS-* 卡；字段不存在或空数组时走原创路径；字段存在时由资产校验检查引用闭环 |
| `protagonist.inner_capacity` | 否 | Phase 6 仅在本作已建立此机制时使用；具体失灵与恢复按已发生事件核对。character-persona 仅在该能力已成为人物当下习惯时，将其主观意义编入“经历与信念”或“判断习惯与行为盲区”；不复制 `why_load_bearing / loss_trigger / loss_signal` |
| `antagonist.voice_boundaries` | 否 | 对手声音的负空间约束 |
| `antagonist.signature_lexicon` | 否 | 同 protagonist——文体量化指标（signature 词表计数）；缺省机器环跳过 |
| `antagonist.subjectivity_object` | 否（物件作用已成立时） | Phase 6（退场场景的承载物——避免角色“消失”为空白）。character-persona 只在角色知道且影响当下行为时把物件事实编入经历或边界，不复制 `potential_use` |
| `supporting_cast[].subjectivity_object` | 否（物件作用已成立时） | 同上 antagonist.subjectivity_object |

### canon_archetype（optional）

引用 `pipeline/inspiration_ledger.yaml` 中 `type=archetype` 的 INS-* 卡。可挂在 `protagonist` / `deuteragonist` / `antagonist` 角色节点下，字段不存在或空数组时不报错。

| 子字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 必填 | INS-A* 格式 ID |
| `weight` | enum | 必填 | `dominant` / `secondary` |
| `merge_boundary` | string | weight=secondary 时必填 | 与 dominant 原型的合并边界 |

资产校验核对引用的 ID、类型、状态、角色目标及 `secondary` 的合并边界。多来源按实际作用与兼容性选择，不设数量或主次配比。

## 角色资产：双层结构

Phase 2 完成后，通过调用 `character-persona` 构建器生成两类角色资产：

### 1. actor-facing 运行时 Skill 包（主资产）

```
pipeline/story-character-skills/
├── .claude/skills/
│   └── {role-slug}/           # 直接以 role-slug 命名（如 li-an）
│       ├── SKILL.md           # actor-facing 人格上下文（静态）
│       ├── state.md           # 当前已接受的主观状态（actor / writer 只读，物理写入归 orchestrator）
│       ├── references/
│       │   └── backstory.md   # 幕后故事（可选）
│       └── build-meta.yaml    # 构建元数据
└── build-report.md            # 构建决策记录
```

- 需要目录挂载的宿主将 `pipeline/story-character-skills` 加入可访问范围；支持直接文件读取的宿主使用明确路径
- actor / writer 通过明确文件路径按需 Read，orchestrator 负责写入与事务衔接
- 命名隔离由工作目录承担：每个 query 的 `pipeline/` 互不可见，`role-slug` 只需在单 query 内唯一
- `story-slug` 仅作为 build-report 标题与 build-meta 元数据保留（独立创作用 phase0 title，数据集创作用 query_index），**不参与 skill 命名**
- 新生成的 SKILL.md 只承载身份与处境、经历与信念、自觉追求、判断习惯与行为盲区、声音和边界。完整作者设计继续保存在 `phase2_character.yaml`；旧包的作者侧章节只作为 legacy optional 供 rebuild 迁移。

### 生成时机

完整链的 role-view 派生器与 writer 需要角色包时，Phase 2 步骤 7 调用 `character-persona`。新增场景参与者沿 Phase 6 交接回人物设计后补建；详见 `character-persona/SKILL.md`。

### 既有产物

既有 `character_arc` 缺 `mode` 时按 `transformative` 理解，并结合原设计判断。新生成产物按实际人物轨迹显式填写。存量 adapter 文件及旧元数据保留在原工作区，当前角色资产检查不消费它们。
