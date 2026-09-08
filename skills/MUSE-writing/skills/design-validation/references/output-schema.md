# 设计校验与来源引用格式

## design_validation.yaml

写入 `pipeline/review/design_validation.yaml`。延用三类问题与既有字段：

```yaml
review_findings:
  - dimension: temporal_math
    scene_id: null
    location: 'phase2_character.yaml: protagonist.birth_year = 2100'
    contradiction_pair: 'phase2_character.yaml: protagonist.backstory 明确亲历 2090 年事件'
    source: pipeline
    issue: 实际出生前十年亲历事件；本作采用普通寿命且无跨时机制
    suggestion: 回到人物经历，确认事件年份、参与者身份或已有机制
summary:
  total_issues: 1
  by_dimension:
    temporal_math: 1
  input_gaps: []
```

`dimension` 为 `temporal_math`、`world_rule_violation` 或 `reference_integrity`。每项须有问题位置、冲突另一端、具体判断和修复方向；设计层 `scene_id` 可为 null。`source` 固定为 `pipeline`。

无问题时 `review_findings: []`、`total_issues: 0`、`by_dimension: {}`。`input_gaps` 只记录缺少必要依据而未完成的判断，例如 `{path: phase2_character.yaml, missing: 明确的角色别称映射, affects: S07 参与者身份}`；没有缺口可省略或为空。确定问题和待补输入分开消费。

## inspiration_ledger.yaml schema

文件为 mapping，正式条目放在 `inspirations` 列表；读取旧产物兼容 `inspiration_ledger` 列表键。

参考生产者将候选留在 `pipeline/references/phase{N}_design_ref.md`。阶段 owner 采纳后分配本 run 唯一 INS-* ID，以 `accepted` 加入 ledger；被 phase YAML 显式引用后改为 `bound`。重新设计后弃用的条目设为 `retired`，同时清理当前有效设计的引用。`candidate` 仅用于候选区，不作为当前设计的绑定来源。

```yaml
inspirations:
  - id: INS-001
    type: pattern
    status: bound
    source:
      kind: canon
      work: 来源作品名
      kb_id: 来源的稳定 ID
      pattern_name: 所采用的机制
      learned_mechanism: 来源中该机制如何发生作用
      verified_by: design-doc-reference
    abstraction:
      what_to_learn: 可迁移机制及适用条件
    fit_signal:
      - 当前情境为何适合这个机制
    project_encoding:
      - phase: 5
        field_path: sequence_expansions[seq_id=Q1].scenes[scene_id=S02].inspiration_refs
        scene_id: S02
        adoption_kind: scene_carrier
        design_value: 该机制在当前场景改变什么
```

示例中的情节与字段值是占位说明。`field_path` 须定位到本作实际采用位置。`type` 为 `pattern` 或 `archetype`，当前被引用的条目状态为 `accepted` 或 `bound`。

### 来源与逐项复用

`source.kind` 为 `canon`、`web` 或 `direct`；旧条目缺 kind 且含 kb_id 时按 canon 读取。canon 用 `work`、实际返回的 `kb_id` 与原文定位；经原型调研取得且没有稳定卡 ID 的 canon，以及 web/direct，使用 `work`、`prototype_id`、`locators[]` 追溯本 run 的 `pipeline/references/prototypes/*/prototype_card.yaml` 及其 sources。`verified_by` 记录生成方。

候选被采纳时将 `reuse_candidates[]` 与旧 `allowed_quotes[]` 中实际使用的内容合并去重，保留来源信息，每项含 `content`、`source_anchor`、`provenance`，锚点回到所选来源。来源核对由其生产者提供证据，消费插件无需复制一套知识库。

### 条件性披露

`disclosure_ladder` 仅用于本作已在 Phase 3 建立、且由该机制承载的同一事实、因果或身份的分阶段显形。条目按实际安排填写 `layer`、`scene_id`、`carrier`、`reader_inference`；确有延后揭示要求时加 `do_not_explain[]`。每层改变人物行动、读者归因、关系判断或价值评价。层数与标签按本作安排，引用真实场景。

普通手艺、母题、象征和单次场景载体通过 `project_encoding` 与 Phase 5 场景字段落地。

### 人物原型

`type: archetype` 另有 `archetype_role`、`archetype_target_slug` 和 `weight`。当前 Phase 2 绑定节点为 `protagonist`、`deuteragonist`、`antagonist`，`archetype_target_slug` 虽名为 slug，实际填对应角色槽位。来源中补 `character` 与可用的原文定位。

`weight: dominant | secondary` 表示实际作用；多来源按各自作用划定边界，`secondary` 须有 `merge_boundary`。数量与主次组合没有配额。Phase 2 同一角色的 `canon_archetype[]` 用 `id`、`weight`、条件性的 `merge_boundary` 引用，边界须与 ledger 一致。

校验唯一 ID、有效状态、类型、真实对象、来源可达性与实际落点。缺少被采用来源的必要信息记为输入缺口；引用不存在或已弃用的条目、指向错误对象记为 `reference_integrity`。
