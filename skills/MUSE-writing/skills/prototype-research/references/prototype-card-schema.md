# 原型候选卡与采用映射

每个原型写一张 `pipeline/references/prototypes/{slug}/prototype_card.yaml`。以下内容按实际证据选填；身份与来源必备。

```yaml
prototype_id: PROT-ferry
prototype_type: user-provided
source_label: 用户提供的渡口设定
retrieval_path: direct
retrieved_at: "2026-09-07T12:00:00Z"
world_rules:
  - content: 末班船遇大雾停航，旅客必须在岛上过夜
    source_anchor: "SRC-001 第 2 段"
constraints:
  - content: 停航是天气条件，船主无权临时破例
    source_anchor: "SRC-001 第 3 段"
reuse_candidates:
  - kind: setting
    content: 雾中停航的渡口
    source_anchor: "SRC-001 第 2–3 段"
    provenance: user-provided
sources:
  - id: SRC-001
    locator: "用户资料 ferry-notes.md 第 2–3 段"
```

`prototype_id` 在 run 内唯一。`prototype_type` 使用 novel / film / drama / opera / real-person / real-location / historical-event / myth / user-provided；`retrieval_path` 记录主要取材路径 canon / web / direct，补充来源在对应项保留真实 provenance。`source_label` 标明作品、人物或事件及必要版本；`sources` 必须能回到实际资料。

有证据时可填 `style_signature`（声音、节奏）、`key_traits`、`world_rules`、`constraints` 和 `reuse_candidates`。候选内容附 `source_anchor`，连接本卡 SRC-* 与具体位置；既有字符串字段可在同字段说明来源。事实条件、分析解释及适配建议保留各自效力。`kb_id` 仅在 canon 入口实际返回稳定标识时填写。

`reuse_candidates.kind` 可为 person / setting / plot / proper_noun / wording / sentence / passage，内容包括原词、原句或连续段落及标志性表达。旧卡的 `allowed_quotes` 作为逐字候选兼容读取，新卡将这些内容统一放入 `reuse_candidates`；同一材料只保存一次。

## 采用映射

采用者按实际用途选择内容，再写入已有设计字段或 ledger。普通背景事实可直接进入世界和人物设计；需要跨阶段跟踪的机制或复用项写 INS-*。

| 本卡内容 | ledger 中的落点 |
|---|---|
| `prototype_id / source_label` | `source.prototype_id / source.work` |
| 实际采用项的来源 | `source.kind` 按采用证据填写 canon / web / direct；补充来源的 provenance 随内容保留 |
| 实际采用来源的定位与稳定标识 | `source.locators[]`，对应 canon 证据有实际 kb_id 时加 `source.kb_id` |
| 已采用的关系、声音、世界条件或表达机制 | `abstraction` 说明机制与成立条件；`fit_signal` 说明本作适用原因；`project_encoding` 保留本作对象、时点、必要结果与可改范围 |
| 实际采用的 `reuse_candidates[]` 或旧 `allowed_quotes[]` | 合并去重到 `reuse_candidates[]`，保留内容、source_anchor 与 provenance |

例如停航资料用于人物被迫共处时，编码需要保留天气原因、船主无权例外与双方关系；只写“安排滞留动作”会丢掉阻力来源。若作品采用的只是渡口空间，则无需同时采用停航机制。

`source.verified_by` 写 `prototype-research`。canon 缺少稳定卡 ID 时以作品、PROT-* 与实际原文定位追溯；web / direct 不制造 kb_id。采用阶段补齐 `type`、状态和相应设计绑定；只有分阶段揭示的机制需要 `disclosure_ladder`。writer 从绑定的 INS-* 取得实际内容，候选路径本身不代替上下文。
