# Phase 6 Execution Protocol

进入 Phase 6 时读取。主控负责恢复、上下文选择、派发和既有验证；writer 产正文，reviser 处理场景 patch，distribution-reviser 处理当前机器合同。下文使用现有 agent、文件和脚本；宿主没有 Skill 工具时，从本包实际安装位置读取相应技能。

## 执行关系

```text
核对当前设计与既有场景状态
  -> 按 Phase 5 呈现顺序处理尚未完成的正文
       -> role views -> 本轮参考 / 可选 actor -> writer -> draft_tail
  -> 全场当前正文就绪
       -> L1 lint -> 本轮 A + 条件 B/C -> 全局问题与逐场裁决
            |-- PASS -> 语义通道完成
            |-- PATCH -> reviser -> 既有 post-revision
            |-- ROLLBACK -> writer 重写 -> 既有 post-revision
            `-- REWRITE -> 原设计 owner -> 受影响下游
       -> 当前机器合同 pending -> distribution-reviser -> 复检
  -> 当前正文的语义审阅、保护与机器状态均闭合
       -> 更新索引 -> verify_review_complete.py -> Phase 7
```

## 0. 工作目录与恢复

命令中的 `WORK_DIR` 是本次作品目录，`MUSE_WRITING_ROOT` 是本包实际安装根；执行前按当前宿主解析。

每次派发明确 `work_dir`、本包实际位置、`scene_id` 与本轮模式。场景顺序来自 Phase 5 `sequence_expansions[].scenes[]`；`previous_scene_id` 取其呈现前项，不按 ID 减一。静态输入清单由各 agent/skill 维护；动态来源选择、前场 ID、role move 授权及必要保护条件直接随派发传入。宿主未预载所需 agent 时，主控先读取本包 `agents/{agent-name}.md`，将职责正文交给子执行者，或要求其先读取该绝对路径；子执行者随后加载文件指定的技能。仅有 agent 名称不表示职责已进入上下文。

进入时核对现有正文、裁决、pending directive、应用 summary 与 post-review：

- 当前设计下的有效正文继续复用，从未完成的审阅或修订环节恢复。文件存在只证明落盘；中断稿、已判失效稿与待重写稿不能冒充完成稿。
- 首次生成仅处理尚无有效正文的场景；已有正文只在当前 ROLLBACK 或作者明确授权重写时交 fresh writer 覆盖。恢复不重置既有 applied、protected 或合同轮次。
- 已有 review 仅在输入、正文和来源选择仍适用时复用。待应用 patch 先核对当前锚点及 application_id，按 §1.5 的同一路由继续；不另设紧急修订流程。
- 必需人物输入失败时暂停依赖该输入的场景与后续场景，不让后场把未成立的计划当已发生事实。无此依赖的工作可以继续；在现有完成状态中保留具体缺口。
- `state.md` 是已有状态资料，可能只覆盖故事入口。按故事时点、获知渠道及相关当前有效正文补足 role view；未来场景的知识不能倒灌，actor/writer 不写 state。

## 1. 逐场创作

### 1.1 派生 role views

将工作目录、当前及前场 ID 交 `role-brief-deriver`。它从 Phase 5、人物 package、可选 state 和相关正文派生逐角色认知切片。participant 的中文名通过 `build-meta.yaml` 对齐 slug；不能把人物名直接当文件名。当前必需文件缺失、映射不唯一或认知事实冲突时返回输入负责人；不重复派发直到碰巧成功。

确认每名 participant 的 `pipeline/scene_{scene_id}/role_views/{slug}.yaml` 齐备且适用于当前时点，再生成 writer 投影：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/extract_scene_card.py" \
  --work-dir "$WORK_DIR" --scene-id S01
```

恢复时只重建受已变输入影响的视图。主控不补写角色答案或正文。

### 1.2 人物素材与来源

普通场景直接交 writer。消化 scene card、人物资产、state 和 role views 后，仍存在须由该人物独有前提完成、且会改变关键判断、行动、对白或关系结果的解释/选择空位时，才对相关角色调用 isolated `character-actor`。canon 身份、对白存在、人数或场景标签本身不能触发。

对命中的 `{scene_id, role_slug}`，可先通过扩展包 `dialogue-reference` 获取本人参考，再把本轮有效路径或“无”交 actor。只有本次完成且对应当前 role view 的 role move 获授权；空 moves、未命中参考或普通执行失败可直接继续。actor 报告必需输入问题时先修输入。

writer 派发明确“本轮可读 role move 角色：[...]”；空列表不读 staging 中任何旧文件。参考选择见 §3.5。

### 1.3 writer 派发

派发包含：工作目录、本包位置、scene_id、前场 ID、本轮有效 reference 路径或“无”、获准 role move slugs；ROLLBACK 另给当前裁决目标和必须保持的已接受事实/保护关系。调用 `writer` 的职责与输入清单，输出唯一正文 `pipeline/scenes/scene_{scene_id}.md`。

`counter_prior_scene.used=true` 时传已有 `kind / mundane_action / emotional_context / forbidden_moves`，让 writer 理解所选日常行为的作用。只传设计中实际存在且适用的限制，不自动追加“不得象征化”或“不得心理解释”。候选实现仍按 writer 的权责层级取舍。

本轮 ref 的采用范围、最终 `reuse_tier`、已有 `reuse_mode / intended_domains` 与适用的 `worldview_reuse` 随派发明确，执行[参考采用契约](../../writer/references/reference-adoption.md)。只给 scene_id 无法表达这些本轮选择；静态目录中同名文件也不取得输入权。

writer 成功并确认正文完整后提取尾摘，供下一场衔接：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/extract_draft_tail.py" \
  --work-dir "$WORK_DIR" --scene-id S01
```

有必要输入冲突或未完成正文时保持当前有效版本并报告缺口，不能以“已写文件”判定成功。

## 1.5. 全场审阅与四档路由

全部所需场景的当前正文就绪后，沿既有 L1 → L2 → L3 执行。复用仍适用的成功结果；正文或输入变动后刷新受影响项。

### L1：定位与合同

对当前场景运行 `ai_filler_lint.py`、`lexical_stats.py`、`dialogue_lint.py`；各脚本接收 `--work-dir`、`--scene-id`，可传 Phase 0 的实际 genre。沿当前 policy 使用默认诊断条件，不由类型另造阈值。保留初稿报告，修后使用既有 suffix。

lint 成功后调用 `machine_directive.py --work-dir "$WORK_DIR" --scene-id S01`。普通 observe 命中交语义审阅判断；明确密度合同按现行 policy 计量。缺输入、脚本失败、当前报告无法对应正文时不能沿旧结果继续。

### L2：本轮来源与全局问题

A 默认运行；多线连续性、复杂人物关系等具体风险选 B，世界规则、时间线或设计对照风险选 C。用户明确 strict 时三组齐备。各组派发明确 work_dir、包位置与 `group=A/B/C`。本轮未选 B/C，即使目录有旧报告也不消费。

将本轮选择同时交全局聚合与 scene-reviewer：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/aggregate_global_findings.py" \
  --work-dir "$WORK_DIR" --source A
# 若本轮选择 B/C，分别追加 --source B / --source C。
```

选中报告缺失、非法或执行不完整时补齐该输入；不回退旧聚合。`global_findings.yaml` 中阻断当前设计/正文的真实问题回实际负责人，标明受影响场景。全局问题不被逐场 PASS 消除，也不需要另造场景 patch 来替代全局决定。

### L3：输入、裁决与恢复

每场派发前执行：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/verify_scene_review_inputs.py" \
  --scene-id S01 --pipeline-root "$WORK_DIR"
```

exit 1 表示必需输入缺失；沿现有 `pipeline/review/scene_{id}.yaml` 记录 `verdict: ESCALATED`、`review_incomplete: true`、`missing_inputs` 与 `written_by: orchestrator_input_gate`，不派 reviewer。其他执行错误同样保持未完成。补齐输入后，将本 gate 的旧降级报告移至既有 `scene_{id}.input_gate.yaml`，再派 scene-reviewer。

派发包含本轮选中的 A/B/C 来源、当前正文/lint 与模式。现有有效裁决直接续办；已失效裁决只在主控明确本次重审与替换权限后重写，不能因旧文件存在永久卡在 `already_reviewed`。

| 裁决 | 当前负责人和动作 |
|---|---|
| PASS | 本场语义审阅完成；继续核对当前机器合同 |
| PATCH | 按下节执行 pending patch，并进入现有 post-revision |
| ROLLBACK | 当前设计有效，正文需重写；更新受影响上下文，派 fresh writer，进入 post-rewrite |
| REWRITE | 回 finding 指向的 Phase 2–5 设计 owner，更新直接受影响下游后恢复 |

裁决依据实际损害与修复范围。诊断名称、词面命中或次数不自动升档。

### PATCH 应用

reviser 派发前验证指令结构、保护声明及锚点：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/verify_rewrite_patch_schema.py" "$WORK_DIR" --scene-id S01
python3 "$MUSE_WRITING_ROOT/scripts/verify_patch_directive_traceability.py" \
  --scene-id S01 --pipeline-root "$WORK_DIR" --source-filter scene_review
```

任一步失败返回指令生产者，不用模糊定位继续。派发 reviser，携带 work_dir、scene_id、当前 directive 和 application_id。读取 `revision_summary.md` 顶部的权威 status：

- `complete`：全部应用后执行 `mark_patch_applied.py --work-dir "$WORK_DIR" --scene-id S01`，转 `.applied.yaml`，刷新正文尾摘并复审。
- `partial`：reviser 将 pending 指令裁剪为未应用项，并为下一轮换未用过的 application_id；summary 保留本轮完整应用记录。主控不 mark applied，先处理具体未完成原因。
- `failed`：零应用，保留当前有效正文与 pending；定位失败交指令生产者，输入或设计错误交其 owner。普通重试沿用同一 application_id。

complete 只证明应用动作完成；主控不依据 family 数量、literal-only 保护或 summary 自写语义 PASS。

### ROLLBACK 重写

按 §1 更新受影响的 scene card/role views，明确本轮 actor/ref 授权，向 fresh writer 交当前裁决目标与已接受的事实、关系和 literal 保护。旧稿不作为重写范文；必须保持的内容仍须进入当前输入。重写成功后刷新当前 lint 和尾摘，并准备既有保护批次：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/protected_integrity.py" prepare-post-rewrite \
  --work-dir "$WORK_DIR" --scene-id S01
```

随后派 `post-rewrite` 模式 scene-reviewer，沿 `scene_{id}.post_revision.yaml` 输出。失败保持当前问题未关闭，不转机器改写掩盖。

## Step 6: Post-revision review

任何正文修订的完成判定均对应当前正文。PATCH 后刷新全场 AI lint：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/ai_filler_lint.py" \
  --scene-id S01 --work-dir "$WORK_DIR" --output-suffix v2
```

存在 applied patch 时，对对应项沿既有 `run_local_lint.py` 生成 old/new 局部对照：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/run_local_lint.py" \
  --scene-id S01 --work-dir "$WORK_DIR" --patch-id patch_01 \
  --output "$WORK_DIR/pipeline/review/lint/S01.patch_01.local.v1.yaml" \
  --output-v2 "$WORK_DIR/pipeline/review/lint/S01.patch_01.local.v2.yaml"
```

派发 scene-reviewer，模式明确 `post-revision` 或 `post-rewrite`。它读取当前正文、scene card、本次初审问题与选中来源、当前 lint、实际应用 summary/局部对照及保护批次，核对原问题是否消失、必要功能是否保留、是否引入新损害。不存在的 patch/summary 不为填齐输入而伪造；ROLLBACK 使用其重写裁决与准备好的保护批次。

报告写 `pipeline/review/scene_{id}.post_revision.yaml`；同一路径已有修前结果时，派发明确刷新当前轮。然后执行：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/protected_integrity.py" verify-post-revision \
  --work-dir "$WORK_DIR" --scene-id S01 \
  --review "$WORK_DIR/pipeline/review/scene_S01.post_revision.yaml"
```

语义 PASS 与保护验证同时成立才闭合。`requires-review` 只说明是否存在需核对的 relation scope；literal-only/空保护集仍由现有 reviewer 判断已确认语义问题，不提供主控签发 PASS 的捷径。

## 2. 当前机器合同

先处理场景语义问题，再处理会改变锚点的分布修订。仍有必需输入错误、设计回退或未完成语义修订的场景暂停本 lane。现有 `reviewer_gate` 与正文证据已确认语义修复完成、仅剩机器合同待处理时可以进入；总 verdict 不必提前 PASS，最终放行才要求双通道闭合。

对可继续场景刷新当前正文 lint，并显式指定当前输入：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/ai_filler_lint.py" \
  --work-dir "$WORK_DIR" --scene-id S01 --output-suffix pre_dist
python3 "$MUSE_WRITING_ROOT/scripts/machine_directive.py" \
  --work-dir "$WORK_DIR" --scene-id S01 --refresh \
  --lint-artifact pipeline/review/lint/S01.ai_filler.pre_dist.yaml
```

只有当前 directive 中的 pending 合同项进入 distribution-reviser；普通观察、已闭合项和未授权旧文件不产生施工。指令须 `dispatch_ready: true`，保留既有保护、issue 身份、objection 兼容及 pre_dist 快照。

每次派发明确 work_dir、scene_id、directive 与 attempt；读取对应 `distribution_summary.md` 状态。普通自动修订累计最多两轮，恢复沿用已执行轮次，不重置预算。failed/执行错误返回具体负责人；partial 仅对脚本重建的剩余项继续。

每轮改文后运行：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/ai_filler_lint.py" \
  --work-dir "$WORK_DIR" --scene-id S01 --output-suffix dist1
python3 "$MUSE_WRITING_ROOT/scripts/machine_directive.py" \
  --work-dir "$WORK_DIR" --scene-id S01 --refresh \
  --lint-artifact pipeline/review/lint/S01.ai_filler.dist1.yaml
python3 "$MUSE_WRITING_ROOT/scripts/distribution_gate.py" \
  --work-dir "$WORK_DIR" --scene-id S01 --attempt 1 --max-attempts 2
```

第二轮对应 `dist2` 与 `--attempt 2`。gate exit 0 关闭机器合同，exit 1 保留实际剩余问题并按预算处理，exit 2 处理输入/执行错误。脚本 PASS 只覆盖合同、应用及保护检查；分布修改后的实际段落与连接进入同一现有 post-review，复用无变化部分的结论，不拿改前语义 PASS 代表改后全文。

## 3. 索引与交接

所有正文采用 `pipeline/scenes/scene_{id}.md` 单路径；尾摘由当前正文提取。Phase 5 写入 hook 可生成索引骨架，正文完成或修改后按需刷新：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/generate_phase6_index.py" "$WORK_DIR"
python3 "$MUSE_WRITING_ROOT/scripts/verify_review_complete.py" "$WORK_DIR"
```

索引的正文路径、呈现顺序与字数对应实际文件。进入 Phase 7 要求所需场景与当前语义结果完整、全局阻断问题已处理、保护验证有效、机器状态闭合。未知、pending、escalated 或输入不完整均不能借格式通过放行。

### 宿主执行

hook 注册见本包 `hooks/hooks.json`。宿主未触发 hook 时，在相同操作点手动执行已有脚本；已成功的同版本检查直接复用。Phase 5 写后使用 `validate_phase5_r10.py <phase5_path> --scan-scene-tasks --scan-inspiration-refs` 与索引生成器，整合前使用上述 admission verifier。

## 3.5. scene-reference 选择、生成与派发

扩展包 MUSE-canon-distill 可用时，由 `scene-reference` 负责检索和写 ref。当前冲突、复杂对白、表达难点或手选来源的实际适用领域存在材料缺口时，在 role views 成功后、writer 前调用；已有适用材料足够时直接复用。用户要求每场检索时按要求执行；明确关闭参考时整段跳过。

派发传工作目录、scene_id、当前人物处境、要解决的叙事问题与来源范围。存在 `canon_reference_profile` 时，将当前 `phase0_conception.yaml` 的绝对路径交 scene-reference，生成 ref 时使用 `kb_query.py --canon-reference-profile <当前Phase0路径>`，逐作品保留 `reuse_mode / intended_domains`。本次所有来源共有的限制才使用 `--reuse-mode / --intended-domains`；某一作品的用途不得作为整个结果集的共同授权。手选作品的 `stance: prefer` 与本次领域相交时，保留该作品的实际采用范围。未明确用途时沿现有选材约定；不从相关分数推断作者新增授权。`world_rule` 需求另装相应 lore。无同书候选时保留已采用世界规则、跳过范文，不另选作品替代。扩展不可用、无匹配或执行失败时以“无”继续；作者指定的必要事实缺口仍回来源负责人。

新生成或经确认来源范围和用途仍适用的 ref 才是当前输入。writer 派发明示有效路径或“无”；目录中有旧文件不等于本轮采用。主控读取实际元数据区到正文边界，传递用途与采用范围，避免截断契约。

writer 与后续修订者按[参考采用契约](../../writer/references/reference-adoption.md)消费本次有效参考；该文件维护完整链与短篇共用的用途、档位、回执和读取规则。

### 场景参考密度诊断

既有密度对比仅在需要判断具体文风偏差、且 ref 有 `ref_source_file` 和可用脚本时运行：

```bash
python3 <MUSE-canon-distill>/knowledge-base/scripts/paragraph_density.py \
  --compare pipeline/scenes/scene_S01.md <ref_source_file> \
  --format yaml > pipeline/review/lint/S01.density_vs_ref.yaml
```

沿用现有诊断路径交 scene-reviewer；数值偏离不产生自动 finding。
