# 审稿报告格式

## 报告结构

审稿报告按维度组织，只列出发现的问题（无问题的维度直接省略）。

```yaml
review_findings:
  - dimension: factual_detail   # 16 个可选值见下方维度分组
    subkind: null                # micro_language 必填；其他维度用 null
    scene_id: S03               # 全文级或 pipeline 级问题用 null
    location: '"pale yellow climber roses" — S03 第 12 段'
    evidence_quote: '"pale yellow climber roses"'
    contradiction_pair: '"the Constance Spry is a soft pink" — S04 第 3 段'
    source: story               # story | pipeline
    issue: 颜色描述矛盾——S03 说黄色，S04 说粉色
    suggestion: 统一为其中一种颜色

summary:
  total_issues: 3
  by_dimension:
    factual_detail: 2
    timeline_plot: 1
```

### A 组全稿语义报告附加字段

`scope=manuscript` 复用 `review_findings[] + summary`，并在顶层增加以下字段：

```yaml
review_scope: manuscript
review_round: 1                    # 只允许 1 或 2
input_snapshot: pipeline/review/snapshots/story.semantic.round1.md
semantic_review: clear             # clear | findings
coverage:
  planning_trace_leakage: clear    # clear | findings
review_findings: []
summary:
  total_issues: 0
  by_dimension: {}
```

`semantic_review: clear` 要求 `review_findings: []` 且 `coverage.planning_trace_leakage: clear`；`semantic_review: findings` 要求至少一条 actionable finding。全稿 finding 通常写 `scene_id: null`；需要给出一个主定位场景时可以写该场景 ID，聚合器仍按全稿 finding 消费。manuscript scope 的问题均落在冻结成品，`source` 必须写 `story`；Phase 2/5 的来源证据放 `contradiction_pair` 或 issue。终态脚本比较 `input_snapshot` 内容与当前 `story.md`；内容不一致时报告自动失效。`revision_summary.md` 的 complete 状态不能代替本报告。

### INS-* carrier 闭环 finding 样例（dimension=pipeline_crosscheck）

```yaml
review_findings:
  - dimension: pipeline_crosscheck
    subkind: inspiration_bound_but_no_visible_carrier
    scene_id: S03
    location: '"儿童夜灯" 未在 S03 正文出现'
    evidence_quote: '(S03 全文无 carrier 同义物)'
    contradiction_pair: 'inspiration_ledger.yaml INS-001 disclosure_ladder[early_signal].carrier="儿童夜灯"'
    source: pipeline
    issue: ledger 锁定的 early_signal carrier 在指定 scene 内未出现
    suggestion: 在 S03 安排 carrier 出现一次（不解释含义）
```

## 字段说明

| 字段 | 必需 | 用途 |
|------|------|------|
| `dimension` | 是 | 审查维度标识（16 个可选值，见下方维度分组——**本表是 dimension/subkind 的唯一枚举权威**，审查指南内的检测项名一律作 subkind，不新开 dimension） |
| `subkind` | 条件必需 | A 组 manuscript scope 报规划痕迹外泄时必填 `planning_trace_leakage`，并配 `dimension=ai_pattern`；其他 `dimension=ai_pattern` finding 可选填 `carrier_missing` / `carrier_then_explain` / `omission_violated`（承载完整性，见 A_aesthetic-carrier.md §11）、`narrator_self_corrects` / `emotion_naming_under_face_loss`（反 AI 化失守，见 A_aesthetic-micro_language.md §1bis）、`monologue_padding`（注水独白）、`subtext_translated_by_narrator`（旁白翻译潜台词，见 prose-craft ai-cliche-patterns D 类）。`dimension=micro_language` 时必填：`false_literary_diction` / `sensory_mismatch` / `abstract_judgment_without_action` / `stock_speech_tag` / `weak_character_expression`。`dimension=pipeline_crosscheck` 且涉及 INS-* 检测时必填对应 carrier subkind；其他维度用 `null` |
| `severity` | 否 | 严重度 `CRITICAL` / `IMPORTANT` / `INFO`（可选字段；INS-* 检测按 story-review SKILL.md 的默认严重度表填；缺省时下游按 `IMPORTANT` 处理） |
| `scene_id` | 是 | 问题所在场景；全文级或 pipeline 级问题通常用 `null`，A manuscript scope 可按上文写一个主定位场景 ID |
| `location` | 是 | 引用原文片段，让 orchestrator 无需回查即可理解问题 |
| `evidence_quote` | 是 | 可直接定位并进入 patch_directive 的原句或短段；不得只写概括 |
| `contradiction_pair` | 否 | 矛盾对照引用——当问题是两处描述互相矛盾时，此字段引用另一处 |
| `source` | 是 | 问题来源：`story`（正文）或 `pipeline`（设计文档） |
| `issue` | 是 | 具体问题描述 |
| `suggestion` | 是 | 修订方向（不写具体改法，留给 orchestrator 决策） |
| `summary` | 是 | 按维度统计发现数量 |

## 维度分组

本轮选中的 A/B/C 组分别执行，各自负责相应维度：

| 组别 | 维度 | 审查粒度 |
|------|------|----------|
| **A 审美组** | ai_pattern, voice_consistency, value_change, on_the_nose, credibility, action_log, **micro_language**, **sensory_balance**, **pov_boundary**, **scene_ending** | 场景级 |
| **B 叙事一致性** | characterization, factual_detail, narrative_style | 全文级 |
| **C 结构一致性** | timeline_plot, world_building, pipeline_crosscheck | 全文级 + 设计文档级 |

**A 组维度说明**（对应 [`A_aesthetic.md`](A_aesthetic.md) §8-10）：
- `sensory_balance` — 感官平衡（视听触嗅味分布；读 S2 `density.sensory_balance.imbalanced`）
- `pov_boundary` — 单场景内焦点角色感知越界（与 B §3.A 跨场景视角分工）
- `scene_ending` — 场景收尾中的意义复述、信息保留破坏或形式机械重复；依据实际作用判断
- `micro_language` — 微观语言错配；用 `subkind` 区分假文气、感官错配、抽象判断替代动作、库存语气标签（stock_speech_tag）、人物描写弱表述（weak_character_expression）

## 持久化

每个 subagent 完成审查后，将报告以 YAML 格式写入 `pipeline/review/` 目录：

| Subagent | 输出文件 |
|----------|----------|
| A 审美组 | `pipeline/review/A_aesthetic.yaml` |
| A 审美组（全稿初审） | `pipeline/review/A_aesthetic.manuscript.yaml` |
| A 审美组（修订后复审） | `pipeline/review/A_aesthetic.manuscript.post_revision.yaml` |
| B 叙事一致性 | `pipeline/review/B_narrative_consistency.yaml` |
| C 结构一致性 | `pipeline/review/C_structural_consistency.yaml` |

这是 Pass 1 的交付物。subagent 写入文件后只需返回完成信号（如「审查完成，报告已写入 pipeline/review/A_aesthetic.yaml」），**不返回报告内容**。orchestrator 从文件读取报告来执行修复。

## 原则

- **只报告问题，不报告通过项**——审稿的价值在定位问题，不在确认良好
- **引用必须具体**——包含完整句子或段落，不要只引用几个词
- **建议是方向，不是改法**——具体怎么改由 orchestrator 在修复阶段决定
- **一致性维度尽量配对引用**——当两处描述矛盾时，`location` 和 `contradiction_pair` 分别引用两端，标明各自位置
- **pipeline 问题标注两端**——`pipeline_crosscheck` 标明正文位置与实际被违反的设计字段；设计内部冲突交 design-validation
