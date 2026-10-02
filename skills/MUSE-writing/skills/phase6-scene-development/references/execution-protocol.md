# Phase 6 Execution Protocol

本文件是 Phase 6 的分支与命令手册：PATCH 应用、ROLLBACK 重写、post-revision 复审、可选机器合同 lane、scene-reference 选择与密度诊断。主干（恢复、逐场派发、审阅路由、索引交接）由 [phase6-scene-development](../SKILL.md) 维护，进入相应分支时读取本文件对应节。命令中的 `WORK_DIR` 是本次作品目录，`MUSE_WRITING_ROOT` 是本包实际安装根。

## PATCH 应用

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

## ROLLBACK 重写

按 SKILL“逐场创作”更新受影响的 scene card/role views，明确本轮 actor/ref 授权，向 fresh writer 交当前裁决目标与已接受的事实、关系和 literal 保护。旧稿不作为重写范文；必须保持的内容仍须进入当前输入。重写成功后刷新当前 lint 和尾摘，并准备既有保护批次：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/protected_integrity.py" prepare-post-rewrite \
  --work-dir "$WORK_DIR" --scene-id S01
```

随后派 `post-rewrite` 模式 scene-reviewer，沿 `scene_{id}.post_revision.yaml` 输出。失败保持当前问题未关闭，不转机器改写掩盖。

## Post-revision review

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

## 机器合同 lane（非默认）

默认不执行。只有作者明确要求 strict AIGC 治理，或 Phase 7 两轮 de-AI 后仍要求逐场机器修订时启用；启用后对可继续场景按下列顺序运行，并在 admission 中要求其状态闭合。仍有必需输入错误、设计回退或未完成语义修订的场景暂停本 lane。

```bash
python3 "$MUSE_WRITING_ROOT/scripts/ai_filler_lint.py" \
  --work-dir "$WORK_DIR" --scene-id S01 --output-suffix pre_dist
python3 "$MUSE_WRITING_ROOT/scripts/machine_directive.py" \
  --work-dir "$WORK_DIR" --scene-id S01 --refresh \
  --lint-artifact pipeline/review/lint/S01.ai_filler.pre_dist.yaml
```

只有当前 directive 中的 pending 合同项进入 distribution-reviser；普通观察、已闭合项和未授权旧文件不产生施工。指令须 `dispatch_ready: true`，保留既有保护、issue 身份、objection 兼容及 pre_dist 快照。每次派发明确 work_dir、scene_id、directive 与 attempt；读取对应 `distribution_summary.md` 状态。普通自动修订累计最多两轮，恢复沿用已执行轮次。每轮改文后运行 `ai_filler_lint`（`distN`）、`machine_directive --refresh` 与 `distribution_gate.py --attempt N --max-attempts 2`：gate exit 0 关闭机器合同，exit 1 保留实际剩余问题并按预算处理，exit 2 处理输入/执行错误。脚本 PASS 只覆盖合同、应用及保护检查；分布修改后的实际段落进入同一现有 post-review。

## scene-reference 选择、生成与派发

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
