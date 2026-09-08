# 全文整合产物

| 产物 | 职责与直接消费者 |
|---|---|
| `story.md` | 当前整合正文，供独立审阅与全文修订；发布验证通过后交读者 |
| `review/wholetext_gate.yaml` | 当前稿机器结果，由主控决定是否启动 de-AI 修订 |
| `review/snapshots/story.semantic.round{N}.md` | 受审冻结稿；reader 使用 round 1，A 使用对应轮次，保持审阅对象明确 |
| `review/reader_review.yaml` | 独立阅读观察及 input_snapshot；由修订负责人核实，由终态检查其输入和修后衔接 |
| `review/A_aesthetic.manuscript.yaml`、`.post_revision.yaml` | A 全稿初审/复审，绑定各自冻结稿 |
| `review/global_findings.yaml` | 本次明确选中报告的聚合，供同一轮全文修订使用 |
| `revision_summary.md` | 本次修订的 complete / partial / failed 和处置说明；缺失须按实际步骤判断 |
| `review/manuscript_quality.{mode}.round{N}.yaml` | 既有改文前后观察与保护结果；reader 模式另绑定实际使用的读者报告 |
| `audit/release_eligibility.yaml` | admission 与 terminal，由现有脚本维护，交付者消费 |

表中除 `story.md` 外均相对 `pipeline/`。schema、轮次及命令由 [Phase 7 入口](../SKILL.md) 和相应脚本维护；审美取舍保留作者裁决。
