---
name: short-story-review
description: 审阅短篇当前全文，定位硬要求、人物知识与声音、因果和表达问题；写现有 short_story_review.rN.yaml，保留作者审美裁决。
---

# 短篇全文审阅

读取当前 `story.md`、`pipeline/shortform/{conception,characters,outline}.yaml`、当前 outline 引用的 adopted ledger 条目；只读取本次派发明确给出的有效 reference pack 与 reader 报告。现有 `whole.*.yaml` 和 `wholetext_gate.yaml` 提供定位线索，按其对应正文版本判断是否适用。

## 依据与判断

- **事件与组织**：核对全文必要结果、实际因果、结局作用和 handoff。场景调序、合并、插叙或外部叙述可以合法；关键在读者能否重建关系、人物是否提前使用未知信息。角色不改变、起终标签相同或场景留白不单独构成问题。
- **人物与声音**：从经历、信息、当前目的和关系判断其思考与表达。检查有充分表现机会的人物是否被同一种声音覆盖；表达边界保留原条件。通用答案借人物发言时，指出缺失的人物前提及其影响。
- **表达与来源**：定位因果不清、对白归属混乱、语义复读或规划语言直译。过程、科学推理、程序与母题可持续改变状态或意义；词语、句数和密度本身不产生语义 finding。只核对已采用机制及有效 ref 的实际约定，不要求隐去合法出处、强行引用候选或把每条世界规则写成动作。
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

每条 finding 用 `severity`、`dimension`、`quote`、`note`；quote 引用原文，note 说明问题、影响与修复方向。dimension 延用 `冲突|价值转变|人物声音|POV|叙事组织|文本质量|灵感落点|遮名-饱和度`。

`BLOCKER` 用于硬要求未落实、必要结果或关键因果失效、确定的重大知识矛盾等；`MAJOR` 为显著局部问题或有证据的系统性表达损害；`MINOR` 为不妨碍当前交付的打磨。纯审美取舍保留作者裁决。

有 BLOCKER、未满足的 requirements，或确证的系统性缺陷需要修订时为 `REVISE`；其余为 `PASS`。数量、标签和风格偏好不代替严重性判断。输入不足时向主控报告，不能用无依据的 PASS 代替审阅。完成回复状态和报告路径，正文保持不变。
