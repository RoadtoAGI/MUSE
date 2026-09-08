# 读者审阅报告

```yaml
input_snapshot: pipeline/review/snapshots/story.semantic.round1.md
reader_findings:
  - location: "第二节末：引用足以定位问题的原文及相邻语境"
    feeling: "我无法理解她此时为什么认定来信是伪造的"
    absence: "前文没有提供她见过原信、认得笔迹或取得其他证据的信息"
```

`input_snapshot` 记录本次实际受审正文路径，相对 work_dir；完整链固定使用上例快照，其他调用方可传 `story.md` 等实际路径。它标识输入，不能单凭路径证明正文没变化；有效性由调用方的既有快照或当前任务检查判断。

`reader_findings` 为列表。每项必有 `location` 与 `feeling`：位置附足够原文语境，感受说明具体阅读影响。`expectation` 仅在正文建立相应期待时填写；`absence` 仅在确有缺失信息时填写，重复或过载无需硬填缺失项。

上例反馈需要补足的是判断依据，是否补一句对白、调整顺序或保留为有意误判由设计和修订负责人决定。单纯希望人物多反应、每人都有结局或独白更短，属于作者可选的审美意见。

完整读完且无发现时仍写输入身份与 `reader_findings: []`。输入错误或未读完时返回未完成原因，不写完成空报告。
