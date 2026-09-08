# 从已有知识库取材

按作品、版本与当前问题查询 MUSE-canon-distill 已有资产。通过宿主支持的已安装 skill 入口调用，指定本次创作 的输出位置；内部物理路径由该包解析。

| 入口 | 当前用途 |
|---|---|
| `design-doc-reference` | Phase 0–5 的构想、世界、人物与结构；传实际 `phase_id / narrative_problem` 和已有 signals，genre 可缺 |
| `scene-reference` | 场面机制、语言、上下场与具体原文；按来源传 `novel / stage_play / screenplay` 等实际 source_medium |

固定来源时传明作品与版本，返回的其他作品只补已授权的空缺。人物问题先查询已有 Phase 2 分析与角色资料，按缺口回读原文；不启动建库或角色 rebuild。

抽取时区分原文事实、分析解释与创作启发。世界事实可进入 `world_rules`，可核对的连续性条件进入 `constraints`；控制思想或类型解释保留为带来源的分析，不提升为新作硬约束。人物、声音与节奏按本次需要写入相应候选字段。原句或连续段落进入 `reuse_candidates`，保留来源位置。

记录实际返回的作品、场景或文档定位；存在稳定 `kb_id` 时一并保留。目标资产缺失或入口不可用时，可按 [web 路径](web-path.md) 补查同一来源；无法核实必需的指定版本时返回缺口。已有证据继续使用，缺失的可选字段省略。
