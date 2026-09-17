---
name: distribution-revision
description: 按主控本次机器指令修订原创场景的分布性表达问题，保留事实、人物声音与保护语义；用于实际有待处理条目的修订。
---

# 分布性修订

读取当前 `pipeline/scenes/scene_{scene_id}.md` 与 `pipeline/review/{scene_id}.machine_directive.yaml`。dispatch_ready 必须为 true；否则返回 directive_not_ready，由主控刷新。无 pending entries 时写 complete 的空施工 summary。

有待修订条目时，先取得本包 prose-craft 主文件，按实际问题补读相关参考；改动对白内容、话轮或声音时取得 dialogue-craft。已有有效上下文可复用，宿主文件加载可用。按需补读 scene_card、人物依据与已采用来源。当前命中提供位置和模式线索，先判断其语义作用；必要用法和作者明确的表达条件保留，冲突交主控处理。

只处理 remaining_hit_ids 指定项，exempted_hit_ids 保持原样；字段缺省时按当前 entry 范围解释。可以合并、删减、补明或重排相关句群，范围由真实损害决定。不得增加情节事实、改人物动机/必要结果，或将不同声音统一成模板。同义替换若仍有原问题不算修复。

protected_regions 的 preserve 语义继续成立；可调整措辞但需逐区记录。protected_integrity 中 active relation span 为冻结内容，重叠时返回未应用原因，本 lane 不重判关系。正文、已获准事实与当前保护约束发生矛盾时回对应负责人。

交接前沿 prose-craft 的“可读性与承接”判据，对照改动前后连读相关句段；压缩后缺少的回指、因果、比较项或话轮归属应在当前范围内补回，超出授权范围则交主控调整。

就地修改正文并写 `pipeline/scene_{scene_id}/distribution_summary.md`：顶部 `**status**: complete|partial|failed`，每个 pending entry 记录处理或未处理原因，每个保护区写 `- 保护区 {patch_id}：未动` 或 `措辞调整但语义保持（原因）`。complete 表示全部施工，partial 表示部分施工，failed 表示无法施工；有效性由主控 re-lint 与既有复审判断。

机器指令、patch 指令和审阅报告保持只读。主控负责快照、保护核对与轮次，字符保留率等观察不能单独判定内容错误。回复完成状态及 summary 路径。
