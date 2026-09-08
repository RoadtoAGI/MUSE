---
name: short-manuscript-revision
description: 修订当前短篇全文，按派发的 de-AI 或 reader 模式处理具体问题，保持人物和创作意图，输出既有 revision_summary.md。
---

# 短篇全文修订

读取当前 `story.md` 和 `pipeline/shortform/{conception,characters,outline}.yaml`。模式、当前审阅报告与有效参考由本次派发给出；必要输入缺失时报告具体问题。当前 outline 引用 INS-* 时，读取现有 inspiration_ledger.yaml 中对应 adopted 条目的来源、适用条件与 project_encoding。来源文件按本次有效路径读取，旧文件不自动成为修订依据。

## 定位与修复

- `de-AI`：读取当前 `wholetext_gate.yaml` 的触发位置与全文分布，按需加载本包 `prose-craft` 对应规则。普通统计线索按实际表达作用判断。报告中的明确 `density_contract` 按本次实际 `max_count / required_reduction` 执行，保留必要指代、人物和事实；不以风格理由解除合同，也不把同一问题改换成另一指代族。合同与必要内容冲突时具体回报主控。
- `reader`：读取本次明确指定的 `short_story_review.rN.yaml`，处理需修的 findings 与未满足的 requirements。引用无法在当前正文定位时先报告，避免用旧报告改新稿。

范围由问题机制决定。局部归属或措辞问题局部修复；因果、声音覆盖或规划痕迹影响连续段落时，重写相关段落的组织。疑似同类问题只扩查有相关证据的部分。

人物的判断回到当时的经历、目的、感官、已知信息和盲区，变化来自新事实与代价。仅替换术语、补“我认为”或加入回忆不能修复错误的认知主体。错误已写入人物或大纲时标记 `partial`，指出需回上游的字段与影响。

表达边界按原条件生效；人物可以有依据地坦白或解释。视角和呈现顺序按作者要求与全文组织判断。某 finding 的病理机制被具体上下文否定时保留原文，在回执给出理由；保留原有必要结果与来源条件。

## 写入与交接

就地修改 `story.md`，只读设计与审阅文件。复看改变的段落及相邻连接，确认原问题已解决且未引入新矛盾。

写入 `pipeline/shortform/review/revision_summary.md`，顶部为 `status: complete|partial|failed`，说明当前模式、实际改动、未决问题及保留原文的依据。`partial` 表示有问题需上游或作者处理；`failed` 表示输入或执行失败。主控刷新改变正文的检查并复审，修订者不代写 PASS。
