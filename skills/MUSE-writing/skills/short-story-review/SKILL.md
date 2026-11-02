---
name: short-story-review
description: 审阅原创短篇当前全文，定位明确要求、人物知识与声音、因果及表达问题；由短链主控派发，报告供全文修订和终验使用。
---

# 短篇全文审阅

读取当前 `story.md`、`pipeline/shortform/{conception,characters,outline}.yaml`、当前 outline 引用的 adopted ledger 条目，以及派发给出的写作简报 `pipeline/shortform/writer_brief.md`（看其中“范文”与“指令”两节）；reader 报告只读本次派发明确给出的。现有 `whole.*.yaml` 和 `wholetext_gate.yaml` 提供定位线索，按其对应正文版本判断是否适用。

## 依据与判断

- **事件与组织**：核对全文必要结果、实际因果、结局作用和 handoff。场景调序、合并、插叙或外部叙述可以合法；关键在读者能否重建关系、能否说出这个世界发生了什么与人物处在什么处境，以及人物是否提前使用未知信息。角色不改变、起终标签相同或场景留白不单独构成问题。
- **人物与声音**：从经历、信息、当前目的和关系判断其思考与表达。检查有充分表现机会的人物是否被同一种声音覆盖；表达边界保留原条件。通用答案借人物发言时，指出缺失的人物前提及其影响。
- **表达与来源**：定位因果不清、对白归属混乱、规划语言直译，以及 prose-craft 口癖模式库的四个机制（说破、姿态句、填充、同声）和模式库里脚本不查、要逐句读的几类（指称、碎切短分句、反复精确的时刻和计量、没有固定词形的空泛说法），可改可不改的口癖也报。`whole.ai_filler.yaml` 里 `per_sentence: true` 的逐句命中直接记 finding（`文本质量`，`subkind` 取命中的 `mechanism`）；observe 家族的词语、句数和密度本身不产生 finding。过程、科学推理、程序与母题可持续改变状态或意义。只核对已采用机制及有效 ref 的实际约定，不要求隐去合法出处、强行引用候选或把每条世界规则写成动作。
- **与范文语域的偏差**：简报有范文时，对照范文窗口判断。情节走向与人设一致的前提下，正文越像范文越成功，用了范文的原句、专名、人物或情节本身不是问题；借来的内容与本篇情节走向或人设不合时，按对应维度报。列出“范文里不会这样写”的句子及位置，说明偏在句子长短、用词、对白写法还是叙述者与人物的距离。不统计词频；本篇设计或作者要求另定口吻的地方、简报“指令”里主控另定的写法（如对白标点）不算偏差。
- **作者硬要求**：conception 的 requirements 按原顺序逐条定位实际正文证据；不把审美偏好改成硬约束。

规划说明被逐项改写成观察、判断、确认和结算时，找出决定性表达及其具体损害；问题仅在局部时按局部范围报告。全文性问题需有分散位置支持。修复方向回到最早失真的人物依据、设计、输入或正文实现。

## 报告

写入 `pipeline/shortform/review/short_story_review.r{N}.yaml`，N 由本次派发给出。沿用当前正文哈希字段供终验对齐：

```yaml
story_sha256: 当前审阅正文的哈希
status: PASS
requirements_coverage:             # 有 requirements 时与其一一对应
  - requirement: 用户的明确要求
    met: true
    evidence: 具体正文定位
findings: []
```

每条 finding 用 `severity`、`dimension`、`quote`、`note`；quote 引用原文，note 说明问题、影响与修复方向。dimension 取 `冲突|价值转变|人物声音|POV|叙事组织|文本质量|灵感落点|遮名-饱和度|范文语域`。

`文本质量` 的问题属于下列机制之一时加填 `subkind`：口癖的四个机制 `spelled_out`、`posture_line`、`filler_beat`、`uniform_voice`，以及 story-review 的两组 `narrator_self_corrects`、`emotion_naming_under_face_loss`、`monologue_padding`、`subtext_translated_by_narrator`、`planning_trace_leakage`、`carrier_then_explain`、`carrier_missing`、`omission_violated`，以及 `false_literary_diction`、`sensory_mismatch`、`abstract_judgment_without_action`、`stock_speech_tag`、`weak_character_expression`。各机制的说法见 [story-review 报告格式](../story-review/references/output-schema.md)与 [微观语言判读](../story-review/references/A_aesthetic-micro_language.md)；都不贴切时不填。下一版简报按 dimension 与 subkind 给写作者和修订者附对应条目。

```yaml
findings:
  - severity: MAJOR
    dimension: 文本质量
    subkind: abstract_judgment_without_action
    quote: 他显得复杂而沉重。
    note: 只给结论，读者看不到他做了什么；回到他此刻的动作或说出口的话
```

`BLOCKER` 用于硬要求未落实、必要结果或关键因果失效、确定的重大知识矛盾等；`MAJOR` 为显著局部问题或有证据的系统性表达损害；`MINOR` 为不妨碍当前交付的打磨。纯审美取舍保留作者裁决。

有 BLOCKER、未满足的 requirements，或确证的系统性缺陷需要修订时为 `REVISE`；其余为 `PASS`。数量、标签和风格偏好不代替严重性判断。输入不足时向主控报告，不能用无依据的 PASS 代替审阅。完成回复状态和报告路径，正文保持不变。
