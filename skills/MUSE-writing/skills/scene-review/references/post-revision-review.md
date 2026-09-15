# 修订与重写后的复审

post-revision / post-rewrite 使用当前正文、本次修订前证据、summary、当前有效 findings 与机器状态。先核实输入对应本轮，再复读受影响内容及相关衔接；原问题是否解决、是否出现迁移以及必要关系是否保持，在这次阅读中共同判断。对照修订前后，具体核对回指、主宾语、比较项、解释顺序、段际衔接和人物声音；必要复现或连接词减少后若需读者自行补关系，视为本轮引入的问题并恢复或重组。原稿已有的问题按原稿证据归因。

## 结果字段

现有消费者保留以下结构。targeted_span、scene_residual、pattern_migration 表达复审结果的不同方面，不要求独立扫描三遍。确已检查的方面才写 evaluated=true；gate_pass 表示该方面没有仍须处理的已确认问题。family 集合、命中数和形态迁移只记录观察，不单独决定语义失败。

```yaml
review_round: post_revision_round1
verdict: PASS | PATCH | ROLLBACK | REWRITE

ai_pattern_gate:
  machine_gate: pass | fail
  reviewer_gate: pass | fail | override
  override:
    applied: false
    override_reason: null

targeted_span_gate:
  evaluated: true
  gate_pass: true
  per_patch:
    - patch_id: patch_01
      patch_kind: rewrite_sentence | rewrite_span | delete_token | replace_phrase
      local_lint_v1_family_set: []
      local_lint_v2_family_set: []
      same_family_remaining: false
      new_family_introduced: false
      semantic_function_preserved: true
      contract_conflict_observed: false

scene_residual_gate:
  evaluated: true
  gate_pass: true
  unresolved_high_spans: 0
  unresolved_medium_spans: 0
  unresolved_low_spans: 0
  needs_patch_hits: 0

pattern_migration_gate:
  evaluated: true
  gate_pass: true
  old_family_set: []
  new_family_set: []
  old_subtype_set: []
  new_subtype_set: []
  cross_cluster_migration: false
  same_cluster_migration: false

protected_integrity_gate:
  evaluated: true
  gate_pass: true
  literal_gate: pass                 # 脚本结果；token 缺失时为 fail
  relation_review_required: true     # 当前 pending application batch 含 relation scope 时固定为 true
  relation_verifications:
    - patch_id: patch_02
      relation_id: R-S01-01
      preserved: true
      after_quote: "修订后承载同一关系且在当前正文唯一的原句"
      reason: "说明主体、极性、模态、因果、时序或比较基线如何保持"
      current_span: {start: 128, end: 151}  # 当前正文零基、左闭右开字符区间
      scene_sha: "<当前 scene 正文 sha256>"
```

## 判定与交接

- targeted_span：当前文字是否解决本次原问题、保留必要语义；相同 family 仍出现可以是合法用法，新 family 也可提供准确表达。
- scene_residual：检查本轮尚未闭合的问题与改动牵动的上下文；无需重新激活旧报告。unresolved_* 和 needs_patch_hits 统计实际待处理问题，不按原始 lint 条数填写。
- pattern_migration：原来的重复、虚假纠偏或人物失真是否换了说法继续存在；词表只指示候选。superficial_patch_failed 须说明旧问题如何延续，按实际范围选择再次 PATCH、writer 重写或返回设计，不自动升级 patch_kind。
- protected_integrity：沿现有 literal / relation 合同检查，输入、身份或内容保护失败继续阻断。此项不被风格解释豁免。

ai_pattern_gate.machine_gate 反映当前已执行的硬合同及应用状态，reviewer_gate 表达语义结果。当前普通词形与密度提供复读线索，语义未解决或内容保护失效继续阻断；统计增减不制造新的机器失败。旧报告中统计误判需要兼容 override 时，写实际原文和作用依据，不能用 override 遮蔽保护或合同冲突。

无待处理语义问题且当前硬合同闭合时 PASS；局部可修为 PATCH；整体实现失效为 ROLLBACK；输入设计有误为 REWRITE。达到调用方既有修订上限后报告具体未决项，不扩大轮数。当前模式 verdict_path 与回复一致，初审文件保留。

## protected relation 核验与 active anchor

- 当前 scene 的不可变声明快照是核验身份源；完整 verification history 必须覆盖全部声明身份。本轮 reviewer 的核验集合由**当前 pending application batch 的 relation scopes**确定，只包含本轮 applied patch 实际触及的 relation。该集合必须精确相等；缺记录、额外记录、重复记录均 fail-closed。
- 当前 pending application batch 含 relation scope 时，`relation_review_required=true`，本轮 reviewer 核对该集合。历史 relation 未被本轮 patch 触及时沿用既有 active anchor；当前 batch 无 relation scope 时写空 `relation_verifications`，保护由脚本核验，已确认语义问题仍在本次复审中判断。
- `post-rewrite`（ROLLBACK）dispatch 前，orchestrator 先运行 `protected_integrity.py prepare-post-rewrite`；该纯脚本将全部 active relation 投影为 synthetic current application batch。reviewer 继续只读 current scopes，逐项复认全场重写后的关系身份；此步骤只准备证据集合，不增加 reviewer dispatch 或修订回合。
- 每条核验记录必填 `patch_id / relation_id / preserved / after_quote / reason / current_span / scene_sha`。`after_quote` 必须在 `scene_sha` 对应的当前正文唯一命中，`current_span` 必须精确覆盖该 quote。
- `preserved=true` 的记录追加到 `pipeline/scene_{scene_id}/protected_integrity.yaml`，其 `after_quote + current_span` 接任该复合身份的 active anchor。下一轮合法改写以新 anchor 核对。
- `preserved=false`、quote 缺失或非唯一、span/hash 不匹配均令 gate fail。partial 修订中，applied patch 追加当前记录并切换 anchor；not_applied patch 沿用旧 active anchor，且本轮不得为它新增核验记录。
- literal 核验由脚本读取同一快照执行；任一 `protected_tokens` 未在声明 scope 内找到 `raw` 或显式 `accepted_forms`，`literal_gate=fail`。
