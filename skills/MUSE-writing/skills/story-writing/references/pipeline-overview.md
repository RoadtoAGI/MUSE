# 阶段依赖与上下文交接

本文件规定八阶段之间传什么、由谁使用。阶段内部执行归各技能；角色与正文输入的局部协议归 Phase 6。

## 阶段依赖

恢复或自定义调用链可以跳过已有有效产物的阶段；当前阶段所依赖的决定仍须可用。

| 消费者 | 输入与用途 | 输出 |
|---|---|---|
| Phase 0 构想 | 用户目标、已有材料、实际信息缺口；确定前提、价值问题、类型与表达意图 | `phase0_conception.yaml` |
| Phase 1 世界 | Phase 0 的前提、类型、来源约定；建立人物能够行动的物质、制度与社会条件 | `phase1_world.yaml`；实际调研时附 `world_research.md` |
| Phase 2 人物 | Phase 0 的创作意图与 Phase 1 的生活条件；设计欲望、关系、经历、声音和人物轨迹 | `phase2_character.yaml`、角色 SKILL/state/build-meta 与构建清单 |
| Phase 3 脊椎 | Phase 0 的组织意图、Phase 2 的人物系统与入场状态、相关世界限制；确定组织力、激励事件、阻力、读者信息边界和结局 | `phase3_spine.yaml` |
| Phase 4 结构 | Phase 3 的 Arc 与目标结果、人物轨迹和相关世界限制；展开序列、压力递进及真实因果依赖 | `phase4_structure.yaml` |
| Phase 5 场景 | Phase 4 的序列、Phase 3 的组织力与读者信息、Phase 2 的人物关系、当前世界条件；确定场景职责、状态变化和交接 | `phase5_scenes.yaml` |
| 设计校验与大纲审查 | Phase 0–5 的具体断言和引用；修复确定矛盾，取得作者对大纲的裁决 | `review/design_validation.yaml`、`run_state.yaml` 中的 `outline_gate` |
| Phase 6 正文 | 场景卡、逐角色认知切片、角色资产、当前有效参考与前场尾摘；实现情境、人物选择和表达效果 | `scenes/scene_{id}.md`、`phase6_development.yaml` 及既有审阅产物 |
| Phase 7 整合 | Phase 6 索引、通过场景审阅的正文、原始创作意图；整合全文并作全文修订 | 工作目录根部 `story.md` |

表内阶段文件均在 `pipeline/` 下。Phase 6 索引按 Phase 5 的呈现顺序列出场景；事件发生次序、场景 ID 与文件名排序各有用途，不能替代呈现顺序。未完成正文的场景保留索引位置，整合阶段须取得全部正文。

## 传递有用的语义

每次派发明确当前任务、技能入口、工作目录、有效输入和输出位置。宿主未预载所需 agent 时，从本包实际 `agents/` 取得职责正文交给子执行者，或要求其先读取明确的绝对路径；只给 agent 名称不足以完成加载。按当前决策选择上下文，保留以下区别：

- **作者决定与客观限制**：用户要求、已批准的创作意图、世界硬规则、人物已知事实、场景必要结果与信息释放边界具有相应约束力。摘要时连同适用条件传递。
- **解释与候选**：理论说明、取材所得机制、局部动作、物件、对白和修辞候选帮助执行者选择。保留它们服务的情境与目的；具体措辞仅在作者指定或来源复用约定要求时锁定。
- **来源与推断**：来源事实、角色相信的事、模型提出的联系分别标明。世界事实已确定而 POV 尚未知时，约束角色获得信息的方式，保留事实本身。

直接读结构化原文、摘取关联字段或使用现有投影脚本，取决于消费者。无需固定 XML 包装或强制转写全部 YAML。裁剪前确认没有拆散“人物为何在意—当前压力—选择余地—必要后果”；其余来源保持可回读。参考数量、字段数量和摘要长度按实际信息量决定。

### 人物与正文

Phase 2 YAML 承载作者侧人物轨迹、关系与背景；`story-character-skills/.claude/skills/{slug}/SKILL.md` 承载长期人格与声音，`state.md` 承载已记录的入场状态，`build-meta.yaml` 保存身份映射及构建来源。Phase 3 经 `build-report.md` 的 name→slug 映射读取主角状态；Phase 4/5 从 YAML 读取作者侧轨迹。

Phase 6 每场由 `role-brief-deriver` 生成独立 `role_views/{slug}.yaml`；普通场景直接交 writer，人物独有前提确实影响关键实现时，才派发相关 character-actor。writer 只读本次派发明确列出的可选 role move 和参考文件。详见 [Phase 6 协议](../../phase6-scene-development/references/execution-protocol.md)。

`state.md` 可能仅覆盖故事入口。派发结合场景时点与前文选择有效事实；初始状态、未来轨迹和其他角色的秘密不能自动成为本场人物知识。尾摘负责文字衔接，角色可知范围由 role view 给出。

### 来源复用

阶段 owner 按实际缺口加载已安装的 `design-doc-reference`；已有适用材料先复用。扩展不可用时继续处理可由现有输入支持的设计，明确受影响的缺口。

用户选择的来源、复用方式与适用领域随相关决定传递。`stance: prefer`、`reuse_mode: maximize_apt_reuse` 且领域包含 `world_rule` 时，Phase 1 采用该来源的实际运行机制，按本作情境适配；后续按已确定规则创作。把它换成传闻、象征或另一套原因会改变已选机制，应回到该决定处理。

参考生产者输出候选；阶段 owner 采纳后，将其加入 `inspiration_ledger.yaml` 并在实际使用的字段挂 INS-*。具体结构和生命周期见 [ledger schema](../../design-validation/references/output-schema.md#inspiration_ledgeryaml-schema)。普通来源材料无需为入上下文再造卡片；ledger 用于已建立的显式机制或原型绑定。

## 执行与反馈

角色资产构建归 Phase 2。已成功验证且输入未变的资产沿用结果；缺失、变更或无验证结果时执行本包 `scripts/verify_phase2_assets.py <work_dir>`。

Phase 5→6 的设计校验与作者大纲审查由 [story-writing](../SKILL.md) 调度。Phase 6 拥有已有的 lint、story-review、scene-review 及修订路由；Phase 7 拥有全文整合和发布条件。格式检查识别字段与接口问题；设计校验指出可定位的语义矛盾；审美取舍交作者。

反馈回到首次产生问题的位置：输入不足补输入，来源或投影失真修生产者，规则不清修规则，执行偏离再修正文。修订只复查受影响关系。

插件 hook 注册以 `hooks/hooks.json` 为准，宿主是否触发需由实际运行确认。未自动执行时由所属阶段补运行必要脚本，已有成功结果无需重复。`run_state.yaml` 更新采用读改写，保留 `run_intent` 等其他状态。
