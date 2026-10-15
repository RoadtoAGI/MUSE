---
name: short-phase0-conception
description: 原创短篇的构想阶段，从需求提炼具体前提、主要经验、类型和篇幅，保留明确要求及素材；由 short-story-writing 调用。
---

# 短链 Phase 0 构想

把用户需求收敛为一份可支撑全链的构想档。短篇的构想回答讲什么、探索什么经验、采用什么类型、需要多长篇幅。核心认识尚未确定时，模型承担发现和提出的工作。

## 执行步骤

构想尚未确定或被退回时，遵循同包的[大纲构思与回读](../story-writing/references/outline-exploration.md)，已加载且适用的指导直接复用。需要参考时，按 phase=0 的问题请求 `design-doc-reference`；读取成功返回或已有的适用材料，形成不同观察及具体情境。先修正事实与因果问题，再按既有共创授权处理候选。已有方向继续展开，不另开审批轮。采用的核心关系写进 `premise` 与 `core_value`，来源及转化理由留在已有参考或共创记录中；保持以下产物 schema。

### 1. 提炼前提（premise）

用一句话提出可展开的具体情境：可以是人物追求、认识问题或值得观察的关系。前提给故事起点；作者已固定的行动与结局直接继承。

### 2. 确定核心价值（core_value）

找出故事押上的那条价值轴（如 正义↔不公、归属↔放逐）。选择最能组织本篇的主要价值或经验轴，具体场景保留其人物、关系和感受上的差异。

### 3. 选择类型（genre）

> 「类型常规是讲故事的人的『诗歌』韵律系统。它并没有抑制创造力，而是对其进行激发。挑战来自既要恪守常规又要避免陈词滥调。」
> —— 《故事》第四章

写明主要类型及影响创作的混合类型或限定；类型惯例提供读者预期，具体取舍服从本作。

### 4. 确定目标篇幅（target_length）

以正整数记录本次目标字数；用户给出的区间、上限或下限按原有强度保留在 `requirements`，估计值不升级为硬要求。超出整篇生成能力时交 orchestrator 与作者判断。

### 5. 确定叙述人称（narration_person）

记 `first` 或 `third`：叙述者是故事里的“我”写 first，其余写 third，紧贴人物的第三人称也写 third。用户指定时照用，未指定时按本篇主要经验选择。取范文时按它过滤人称；大纲的 `pov` 只写人物 id，分不出这两种。

### 6. 确定交付语言（language）

记正文用什么语言写，两字母代码，如 `zh`、`en`。用户写明时照用；没写时取用户需求本身的语言。设计文档用什么语言写不影响它：用中文讨论、交付英文正文时记 `en`。范文按它取同语言原作。

### 7. 提取硬约束（requirements，条件字段）

用户需求中包含显式枚举或硬约束（如"至少要有一段对话"、"必须包含 X 场景"）时，提取为紧凑的单句列表——short-composer 逐条落实，short-story-review 逐项核销。**仅显式硬约束入列**，模糊的偏好（如"希望感人一点"）不算。

### 8. 收纳素材、风格指令与手选名著（条件字段）

- **`reference_materials`**：用户附带背景素材（历史资料、领域知识、技法要点）时原文收纳有创作价值的部分——保留事实、来源与未定内容的区别。没有则不生成。
- **`style_directives`**：用户有作品层面风格要求（如"现实主义细节描摹"）时逐条收入。没有则不生成。
- **`canon_reference_profile`**：用户指定名著及用途时记录作品、参考领域与复用方式。带 `intended_domains` 的 `prefer` 项是对应领域的首要来源；只含 `work / stance / reason` 的旧格式继续作为检索提示。

手选来源的世界规则会影响人物或事件可行性时，在设计前读必要机制与边界，写入既有 `reference_materials`；后续场景条件承接这些事实。已知事实不等于人物已经知道。仅用于文风的原文参考可在成稿前加载，材料足够时无需重复检索。

理论依据见[前提与价值](../phase0-conception/references/mckee-premise.md)；短篇沿用下面的轻量字段。

## 产物 schema（`pipeline/shortform/conception.yaml`，正向 allowlist——只有下列字段）

premise、core_value、style_directives、requirements 与 reference_materials 原样进入写作简报。校验打印前三项的合计字数；写短与否是本阶段的判断，约束一致性的事实不省。

```yaml
premise: 一句话故事前提                  # 必填
core_value: 核心价值轴（如 正义↔不公）    # 必填
genre: 类型                             # 必填
target_length: 8000                     # 示例；按本次目标填写
narration_person: third                 # 必填，first | third
language: zh                            # 必填，正文的交付语言
style_directives:                       # 可选 list[str]
  - 作品级风格指令
requirements:                           # 可选 list[str]，显式硬约束逐条单句
  - 至少包含一段完整对话
reference_materials: |                  # 可选 str，用户素材原文收纳
  ……
canon_reference_profile:                # 可选；与完整链共用字段语义
  desired_domains: [world_rule, scene_carrier]
  user_reference_materials:
    - work: "用户指定作品"
      stance: prefer                    # prefer | avoid
      intended_domains: [world_rule, scene_carrier]
      reuse_mode: maximize_apt_reuse    # maximize_apt_reuse | style_only
```

结构校验由入口按宿主是否触发 hook 执行；语义核对关注实际创作判断。

## 自检

- premise 提供具体情境，能够展开人物、事件或观察
- core_value 能组织本篇的主要经验
- narration_person 与本篇叙述者一致；language 是正文的语言，不是设计文档的语言
- requirements 里每条都能在终稿中被指认（可核销）
- 用户素材有创作价值的具体细节已进 reference_materials，而不是靠记忆携带
- 手选名著的用途已落入 intended_domains；未从单一作品外推题材专属规则

## 取本篇范文

构想通过校验后立即取范文：只需要构想，人物阶段要对着它写示范句，成稿时复用同一份。范文窗口是从名著场景正文里连续截取的段落，与本篇同语言、同人称，供写作者照着写。

1. 取确定参数：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/assemble_writer_brief.py --shortform --work-dir {work_dir} --retrieval-args
```

输出语言（取 language）、只取原作、人称（取 narration_person）、预算、渲染方式与输出目录，以及 `--style-hint`（由叙述人称、风格指令与类型拼成，决定选哪几部作品）；有手选名著时带 `--canon-reference-profile`。

2. 补 `--query`（人物处境与主要动作，一句话；它决定在选中的作品里取哪几场）；style_directives 写明口语或书面时补 `--register colloquial|literary`；同人、续写、改编点名原作时加 `--novel <原作>`。style hint 写得不像本篇口吻时可以改写，用文风卡的说法：叙述距离、用词、对白写法、节奏。用 canon 包 scene-reference 的 `kb_query.py` 执行，产物为 `pipeline/shortform/reference_pack.md`。
3. 先读文件头：`pool` 行是候选池的构成，`windows` 下每个窗口一行描述（人称、语域、对白占比、该作品的口吻与对白写法）。某部作品的写法明显不合本篇时，加 `--exclude-novel <作品>` 排除它重查，其他参数不变；`results: 0` 写明了清空条件，库中该语言原作不够时可去掉 `--original-only` 或 `--register` 重查。重查在交付说明里记录；找不到合用的范文时成稿按“本篇无范文”处理，不拿旧文件凑。

构想之后若改了叙述人称、语言或风格指令，装配简报时脚本会提示范文早于构想，按本节重取。
