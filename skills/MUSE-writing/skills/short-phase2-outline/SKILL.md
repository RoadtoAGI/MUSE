---
name: short-phase2-outline
description: 原创短篇的大纲阶段，将人物、情境与创作意图组织成全文脊椎和场景；由短链编排调用，完成后交同一作者大纲裁决。
---

# 短篇大纲

读取 `pipeline/shortform/conception.yaml`、`characters.yaml` 与相关有效来源。脊椎与场景在一个阶段共同形成，给 composer 必要事实、事件关系和表达意图；微观动作、对白、修辞与详略由正文实现。

## 构思与取材

核心认识未定、参考可能改变设计或作者退回方案时，按[大纲构思与回读](../story-writing/references/outline-exploration.md)推进。先消费已有适配材料；不足时通过宿主加载 `design-doc-reference`，按问题请求脊椎或场景组织参考。传当前情境、未定关系、来源范围与篇幅，读原作机制、具体事件、阅读作用及迁移条件。

会改变人物和事件可行性的世界规则须在大纲成型前读到。手选来源的规则保留机制、条件与限制，采用结果进入既有材料或场景字段；纯文风参考留到成稿阶段。用户关闭参考时沿用其要求。

提出不同剧情关系时说明关键事件与阅读后果，作者选择方向；已认可部分继续深化。一个候选的心理病因和故事答案不预填为所有候选共同的人物事实。

## 组织故事

`spine_statement` 表达全文组织力，可以是欲望行动、真相显形、关系或观察的展开；`dramatic_question` 表达读者持续追问的结果或认识；`ending_pressure` 表达结局集中显现的处境、压力或理解。

人物根据当时的经历、信息、概念和盲区解释新事实并行动。关键选择与后果由已建立条件产生，避免先给目标结论再补人设。多层转折可在构思时用幕与序列帮助判断，产物仍为同一份轻大纲；单场故事直接展开其变化。

场景数量和详略按全文需要决定：

- `conflict` 写人物与当前阻力、关系或处境的冲突。
- `value_start/value_end` 记录相关处境、关系、认识或感受的起终状态。用它们判断场景贡献，允许人物保持立场、读者改变理解；过渡作用明确时也可保持状态。仅替换状态词不能制造事件。
- `task` 说明本场职责、条件与必要结果。具体动作、道具或措辞只在它们本身影响情节、人物或表达意图时预先指定；说明可按含义分句。
- `handoff` 保留需要后文承接的实际后果或条件，指向相关事件；不把列表邻接当作因果依赖。
- `participants` 引用人物 id；`pov` 用人物 id 或 `narrator:<叙述位置>`。这是默认叙述方案，composer 可在作者要求和知识边界内组织全文。

每场的 location_time、conflict、value_start、value_end、task 与 handoff 投影成事实句进入写作简报，spine 三项不进简报。task 与 handoff 承担一致性事实：谁知道什么、数字、物件去向、时间，这些写全，逐行原样进简报。校验打印每场字数；写短与否是本阶段的判断，少写的是规定性的节拍、措辞和逐项动作，留给正文。

短篇的读者要在开头几段知道这个世界发生了什么、什么在威胁人物、人物在今天之外面对什么。题材自带世界设定时（末世、科幻、玄幻等），开头那场的 task 写明这些信息及交代它们的渠道：回忆、亲历、媒介、传闻或现场证据。成因与运作取自手选来源、范文所在作品或构想，写定后进 task；长篇里成因始终不明的写法靠几百页的累积，几千字里读者只会读不懂。

关键解法沿已建立的条件与人物选择产生后果；核对获得机会、形成阻力或付出代价的原因是否在故事中成立。具体道具和转折方式依本作的因果关系确定。

## 输出与引用

写入 `pipeline/shortform/outline.yaml`：

```yaml
spine:
  spine_statement: 全文组织力
  dramatic_question: 读者持续追问的问题
  ending_pressure: 结局处的压力或认识
scenes:
  - scene_id: S01
    pov: chen-mo                  # 人物 id；外部叙述可填 "narrator:外部观察"
    participants: [chen-mo]
    location_time: 地点与故事时点
    conflict: 人物与处境的冲突
    value_start: 相关起点状态
    value_end: 相关终点状态
    task: 本场职责与必要条件
    handoff: 后文需承接的条件       # 确有交接时填写
    inspiration_refs: [INS-001]    # 引用了 adopted 条目时填写
```

采用需要显式追踪的来源机制时，先写 `pipeline/shortform/inspiration_ledger.yaml`，再在实际场景挂引用：

```yaml
inspirations:
  - id: INS-001
    type: pattern
    status: adopted               # candidate | adopted
    source: 来源及可回读位置
    project_encoding: 该机制在本作成立的条件与作用
```

普通背景事实直接保留在 conception 材料或场景条件中。当前有效的 `inspiration_refs` 只指向 `adopted` 条目；未采用候选不进入正文要求。

结构校验按入口的宿主规则执行。交作者前核对关键因果、人物知识、必要结果、来源机制和 requirements 落点；视角、状态词及场景数量不是创作效果的替代判据。完成后回到 short-story-writing 的同一大纲裁决。
