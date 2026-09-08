# 人物设计输出

新作开工设计写入 `series/character-skills/phase2_character.yaml`。预置单篇工作区沿用 `pipeline/phase2_character.yaml`。它保存作者设计，人物的开场基线和已发生演化分别写入 [人物账本](../../serial-outline/references/workspace-schema.md)；接管不要求补造本文件。

## 作者侧设计

以下示意包含常见可选内容。按实际人物填写；空列表与可选字段缺省均有意义，不逐项补齐占位。

```yaml
protagonist:
  name: 角色显示名
  characterization:
    occupation: 当前职业
    background: 与当下处境相关的社会背景
  desire_system:
    conscious: 当前明确追求的目标
    unconscious: null             # 可选；仅在内在驱力确有依据时填写
    core_flaw: null               # 可选；人物的有害倾向及适用条件
  character_arc:
    mode: revelatory
    start_state: 开场时读者或他人对人物的认识
    end_state: 本次规划区间内拟揭示的稳定特征
    transformation: 什么压力与选择使其显现
  characterization_vs_truth:
    surface: 人物给他人的印象
    deep_truth: 代价面前显出的价值与选择
    gap: 对照、矛盾或表里一致时仍承受的张力
  backstory:
    - event: 已发生的过去事件
      impact: 对人物当下信念或关系的影响
      narrative_use: 可选的叙事用途，仍是作者候选
  daily_life: 与当前故事有关的生活细节
  voice_traits:
    vocabulary: 有依据的词汇倾向
    rhythm: 与对象和情境有关的表达节奏
  voice_boundaries: 有来源的限制、条件与强度；没有时可省略
  empathy_mechanism: 读者理解或关心人物追求的入口

antagonist: null                  # 对抗不具人格时可为空，压力来源在脊椎与卷纲表达
# 具名对手可填 name / relationship_to_protagonist / power_source /
# motivation / desire / voice_traits / voice_boundaries。
# 对手有独立轨迹时可使用与主角同语义的 character_arc。

deuteragonist: null               # 存在时按主角同等的必要信息填写
supporting_cast:
  - name: 配角显示名
    function: 当前叙事职责
    relationship: 与相关人物的关系及自己的利益
    voice_traits_summary: 当前场面需要的声音依据
contrast_axes: 主要人物在经验、利益与选择条件上的差异
relationships:
  power_dynamics: 谁在何种事情上能影响谁
  key_tensions: []
  potential_shifts: []            # 未来变化候选，不能写入开场已发生记录
```

`characterization` 可按需要保留 age / gender / appearance 等既有字段；未知不补造。

主角以及存在的双主角需有 `name`、身份与处境、自觉追求、人物轨迹及当前需要的表达依据。`backstory` 可为空，内在欲望、缺陷和外表反差有依据才写。人物重要性决定信息深度；其他角色可按需要使用同语义字段，不因角色 slot 限制而丢弃关键轨迹。

`character_arc.mode` 是本项目规划标签：

| mode | start / end / transformation 的含义 |
|---|---|
| `transformative` | 内在状态从何处走向何处，哪些压力与选择推动变化 |
| `degenerative` | 内在状态如何退化及其代价；悲剧结局也可能源于环境，不自动判为人格堕落 |
| `revelatory` | 读者或人物对稳定核的认识如何展开；不要求人物自身改变 |
| `static` | 本次故事不以转变或逐步显形组织人物，说明其保持的东西以及相应处境 |

新设计显式选择贴合的模式；已有文件缺 mode 时依据实际轨迹文字理解，不能仅因缺字段就假定人物必须转变。`end_state` 与机制属于作者计划，人物当前认知只可从已经成立的起点材料派生。

## 按需保留的创作机制

| 字段 | 使用条件与信息 |
|---|---|
| `inner_capacity` | 某种信念或习惯实际支撑人物生活时，记录 `primary` 与 `why_load_bearing`；本故事涉及其受损时再填 `loss_trigger` / `loss_signal`。表现是候选，不强制动作或反应缺席。 |
| `subjectivity_object` | 具体物件确与角色自身生活、关系或表达相关时，写 `what` / `created_when` / `where_it_lives`；`potential_use` 是作者的后续使用候选。 |
| `recognition_path` | 需要安排人物如何被认识时，写 `primary_method`、可选 `first_false_reading` / `correction_method`；方法用当前情节需要的文本，不强行制造误读。 |
| `backstory_harvest` | 某段往事有明确呈现需要时，写 `method` / `carrier` 与必要的 `withheld_part`；一般叙述可直接承载，无须一律借物件。 |
| `misread_matrix` | 误读影响当前故事时，记录 observer / target / evidence_seen / wrong_conclusion / narrative_value；与人物真正已知内容分开。 |
| `signature_lexicon` | 已有文体计数确实需要具体词表时填写；计数只作为线索，缺字段时跳过，不能要求正文补词。 |

声音的可选观察字段见 [voice-design](voice-design.md)。上述内容保留在作者设计，由卷纲、编排或派生器按实际缺口读取；当前成立的经历与倾向才进入 persona，尚未发生的用途不能进入快照与传记。

## 原型参考的引用

`canon_archetype` 可挂在主角、双主角或对手，引用同一工作范围的 `inspiration_ledger.yaml`；没有采纳卡时省略。每项保留 `id`、`weight: dominant | secondary`，secondary 填 `merge_boundary` 说明它补充的机制及与其他来源的关系。

引用卡须存在、`type=archetype`、`status` 为 accepted 或 bound，`archetype_target_slug` 与该角色 slot 相同。引用数量不证明整合优劣；多来源是否成立要看人物的追求、经验与选择是否连贯，不能由数组长度阻断。引用必须可追溯，未采纳的候选不伪装成已确认来源。

## 持久基线与兼容包

新作需要持续供给的人物使用同一 `char_id` 建立 persona、V00 快照及 biography 骨架；显示名、实际来源窗口、快照字段与类型扩展遵循 workspace-schema。开工设计可包含作者预想，基线只记录开场已经成立的内容。

兼容包由 [character-persona](../../character-persona/SKILL.md) 在有明确消费者时按指定角色构建。包、adapter 与构建报告都是派生资料，不能覆盖合时人物账本，也不是本包逐章创作的必交前置。其目录、模板和核验由构建器统一定义。
