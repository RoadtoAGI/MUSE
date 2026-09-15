# Phase 6 Execution Protocol

本文档承载 Phase 6 场景 dispatcher 的操作细节。`SKILL.md` 是章级宏观控制、gate 与交接的权威；本文件只展开 scene-level 精确顺序、dispatch prompt、role_view 派生与可选人物行动、writer 接线与低频恢复。具体写作细节由 writer 加载 `prose-craft` + `dialogue-craft` skill 获得。

**何时读此文档**：`serial-chapter-writing` 已加载并进入章循环、需要执行场景级 dispatch 时。用户直接提出的单场景散文改写、对白修订分别由 `prose-craft`、`dialogue-craft` 承接，不进入本协议。

## 目录

- [§0 本文件范围](#0-本文件范围)
- [§1 Dispatcher 伪代码](#1-dispatcher-伪代码)
- [§1.5 Step 5 scene-review 审阅阶段](#15-step-5-scene-review-审阅阶段per-scene-loop-结束后)
- [Step 6 Post-revision review](#step-6-post-revision-review)
- [§2 role_view 派生协议](#2-role_view-派生协议)
- [§3 direct-writer 链路](#3-direct-writer-链路)
- [§3.5 scene-reference 调度与消费语义（扩展包行为）](#35-scene-reference-调度与消费语义仅在装有-muse-canon-distill-扩展包时生效)

---

## 0. 本文件范围

本文件定义章内场景调度；章级控制与交接以 `SKILL.md` 为准。开始调度时读取本包 [上下文协议](context-contract.md)，取得大纲、人物与正文的资料权限、时点及反馈责任。

### 明确包身份与任务工作区

父执行者从当前入口解析包根、作品根及章根。每个新子任务携带 `serial_package_root`、`series_root`、`work_dir`、`chapter_id`，场景任务再带 `scene_id`，单角色任务带 `role_slug`；将本次正文、关键输入和输出目标展开为绝对路径。`series_root` 含 `series/` 与 `published/`，`work_dir` 含本章 `pipeline/`。文件加载派发将 `work_dir="<章绝对路径>"` 独立放一行，供现有 hook 定位。执行者按指定根读写；指定输入缺失时返回缺口，不能以 cwd、同名目录或历史样本推定替代工作区。

脚本示例中的 `${CLAUDE_PLUGIN_ROOT}` 表示本包根；文件加载宿主使用已解析的 `serial_package_root` 绝对路径，不假定该环境变量存在。包内职责规定允许读取的输入、写入的产物和委派边界；宿主负责把这些能力映射到正式文件、补丁或命令工具。Claude 元数据中的工具名只在该宿主解释，文件加载宿主不因此丧失等价读写能力。

| 场景职责 | 本包元配置 | 本包职责 skill |
|---|---|---|
| 人物视图派生 | `agents/serial-role-view-deriver.md` | `skills/role-brief-deriver/SKILL.md` |
| 可选人物行动 | `agents/serial-character-actor.md` | `skills/character-rehearsal/SKILL.md` |
| 场景正文 | `agents/serial-writer.md` | `skills/writer/SKILL.md` |
| 场景审阅 | `agents/serial-scene-reviewer.md` | `skills/scene-review/SKILL.md` |
| 定点修订 | `agents/serial-reviser.md` | `skills/patch-revision/SKILL.md` |
| 分布修订 | `agents/serial-distribution-reviser.md` | `skills/aigc-distribution-revision/SKILL.md` |
| 章收束 | `agents/chapter-summarizer.md` | `skills/chapter-summarizer/SKILL.md` |

使用宿主已注册且明确绑定本包的 agent 与包限定 skill 入口。宿主支持文件加载、但未注册这些 agent 时，派 fresh 通用子执行者，提供上述元配置的绝对路径，并要求先加载该文件及它指向的本包职责 skill；相对链接按所在文件解析。`consistency-review` A/B/C 与 `continuity-check` 沿用已有技能调用，分别直接绑定本包 `skills/consistency-review/SKILL.md` 和 `skills/continuity-check/SKILL.md`；文件加载宿主给出职责文件绝对路径，无需新增 agent 元配置。其他同名包的裸名 agent、现有 workspace wrapper 或 sibling skill 不自动继承为本包入口。缺少子执行能力或必要文件时，报告具体缺项。

下文 `dispatch_serial(role=..., prompt=...)` 是本文件的调度伪代码：每次执行都按上表解析本包元配置，或使用上述直接技能路径，并向 prompt 加入包根、章工作区与标识。它沿用宿主已有 dispatch 工具，不对应新增脚本、registry 或阶段。仅在子执行者确已取得本包元配置和职责层时，后续任务消息才只补动态变量。父执行者不假定宿主会继承自己的 cwd、已读文件或 skill 内容。`reports_input_issue`、`current_role_views_complete` 等同样表示执行者对本次回执与交付物的判断。`current_reference_scope` 解释现有作者决定，`recover_with_scene_owner` 和 `report_remaining_dependency` 表示原责任路径的恢复与交接；它们不要求新增脚本、状态或过程产物。工具调用返回成功与职责交付完成分别判断。

派发失败时先确认指定位置的产物是否已完整：完整且有效则继续尾窗/审阅；未完整则按错误回原执行者修复输入、路径或写入。相同条件下不盲目重复派发。缺权限或作者选择时才进入相应待决，其他必要依赖仍缺则保留当前断点、说明负责环节，并继续无关的已授权工作。

---

## 1. Dispatcher 伪代码

```python
def phase6_dispatcher(chapter_id, scenes_in_order):
    # WORKDIR 是本次章工作区的绝对路径；SERIAL_PACKAGE_ROOT 从当前入口解析。
    # 章卡已选定本章人物，serial_context 已按章卡装配。
    # 已接受的章稿进入防治/摘要/发布恢复时，沿章级断点继续，不重新执行场景装配。
    for scene in scenes_in_order:
        if current_scene_completed(scene):
            # 调用方核对当前正文、已有回执和依赖是否仍有效；文件存在本身不证明完成。
            # 已写且有效的场景直接续用，缺尾窗时从当前正文提取。
            ensure_current_tail(scene)
            continue
        if scene_text_exists(scene) and not rewrite_authorized(scene):
            # 已有正文但完成状态含混时，由调用方核对落盘状态与待办，再决定续用或重写。
            return_to_scene_owner(scene)
            return
        # 只有缺正文的首写，或已经决定重写的场景，才进入下方 fresh writer。
        # 场景卡先落盘，deriver 才有本场事实与时点可读。
        run_script("extract_scene_card.py", scene_id=scene.id, work_dir=WORKDIR)
        result = dispatch_serial(
            role="serial-role-view-deriver",
            prompt=f"chapter_id={chapter_id} scene_id={scene.id} 派生逐角色 role_views。",
        )
        if not result.success or not current_role_views_complete(scene):
            # 检查本次派生回执及本场 participants 对应文件；旧文件存在不代表本次成功。
            # 缺输入回装配/编排，字段或过滤错误回 deriver；事实裁决按 context-contract。
            return_to_input_owner(scene, result)
            return  # 当前场景尚未完成，后继场景不使用缺失的正文尾窗继续。

        # 可选 reference 依 §3.5 选取；人物行动仅在角色选择确能改变本场时调用。
        # 不默认逐角色排练；普通移动、既定程序和纯过渡由 writer 实现。
        reference_scope = current_reference_scope(scene, chapter_id)  # §3.5 的 reuse_mode / intended_domains
        current_ref_path = select_current_scene_reference(scene, chapter_id, WORKDIR, **reference_scope)
        authorized_role_move_slugs = []
        for role_slug in select_roles_needing_action_exploration(scene):
            # 角色交流确需来源案例时查询；缺扩展或无匹配为“无”，不重用旧参考。
            dialogue_ref = select_current_dialogue_reference(scene.id, role_slug, WORKDIR)
            actor_result = dispatch_serial(
                role="serial-character-actor",
                prompt=f"chapter_id={chapter_id} scene_id={scene.id} role_slug={role_slug} "
                       f"dialogue_ref={dialogue_ref or '无'}；据本人 role_view 及本次有效参考生成可选 role_move；moves 为空合法。",
            )
            if reports_input_issue(actor_result):
                return_to_input_owner(scene, actor_result)
                return  # 人物输入有错时，writer 同样不能依赖该 view。
            if actor_result.success and current_role_move_completed(scene.id, role_slug):
                authorized_role_move_slugs.append(role_slug)
            # 空 moves 或普通 actor 执行失败不阻断 writer；未完成时不授权旧文件。

        # 任务只补本场激活项。完整写作与复用规则从本包 writer/craft 加载。
        active_guidance = [key for key in ("counter_prior_scene", "prose_risk_contract")
                           if (getattr(scene.card, key, None) or {}).get("used") is True]

        result = dispatch_serial(
            role="serial-writer",
            prompt=f"为章场景 chapter_id={chapter_id} scene_id={scene.id} 按本次明确的首写或重写任务生成正文。按 SKILL.md 读输入、"
                   f"只写 {WORKDIR}/pipeline/scenes/scene_{scene.id}.md；已有正文的保留或重写已由调用方确认。"
                   f"authorized_role_move_slugs={authorized_role_move_slugs}；current_ref_path={current_ref_path or '无'}。"
                   f"完成回复 'done draft for scene {scene.id}'。"
                   f"active_guidance={active_guidance}；reference_scope={reference_scope}。",
        )
        if reports_input_issue(result):
            return_to_input_owner(scene, result)
            return
        if not result.success:
            # 先核指定路径的实际正文与回执，避免失败通知触发重复写入。
            if not current_scene_completed(scene):
                result = recover_with_scene_owner(scene, result)
                # 恢复使用已有任务、输入与产物；未完成时保持断点，后继不消费缺失尾窗。
                if not current_scene_completed(scene):
                    report_remaining_dependency(scene, result)
                    return

        # scene_card 合规校验（显式调用，无自动兜底；WARN 型不阻断，同主干语义）
        run_script("muse_hook_check.py", extra=[
            "scene-card-compliance",
            "--scene-card", f"pipeline/scene_{scene.id}/scene_card.md",
            "--scene-text", f"pipeline/scenes/scene_{scene.id}.md"])

        # 首次生成阶段不读取既存 patch_directive，也不在正式审阅前派 reviser。
        # PATCH 的唯一生产者是下方 Step 5 scene-reviewer，唯一消费点是其 verdict 路由。
        # tail 在 writer 落下的唯一权威 scene_{id}.md 上执行；PATCH / ROLLBACK
        # 后由对应 Step 5 分支再次提取，确保下游取得当前版本。
        run_script("extract_draft_tail.py", scene_id=scene.id, work_dir=WORKDIR)

        # ============ Step 2.3: scene-review 四档分流（每场景入口占位）============
        # Phase 6 per-scene loop 内**不跑** scene-review——scene-review 设计为 Phase 6
        # **全场景 draft 完成后**的独立审阅阶段（见本文件 §1.5）。

```

**关键约束**：
- 新场景、新人物隔离任务及独立审阅使用 fresh session，按 §0 提供本包元配置与章工作区。针对同一对象的缺件修复可在原执行者继续；输入权限改变时重新隔离。职责层维护静态输入清单，dispatch 补齐当前场景、模式、有效来源与 role_move 授权。
- orchestrator **全程不产 prose**——不改写 / 整合 / 兼职修订

---

## 1.5. Step 5 scene-review 审阅阶段（per-scene loop 结束后）

全部场景写出后、装配 draft 前，按 phase5 阅读顺序执行本段。先取得当前正文的诊断，再派 scene-review 裁决；局部修订、正文重写和设计修复沿现有四档路由。输入缺失或脚本失败先回对应负责人，不以旧文件的存在补足本次失败。

| 责任 | 当前输入与产物 |
|---|---|
| L1 定位 | 本场 ai_filler、lexical_stats、dialogue lint；频数是观察信号 |
| L2 语义诊断 | A 默认执行；B/C 按人物、事实、世界或时间风险调用。当前 continuity-check findings 合入 B |
| L3 裁决 | scene-review 按当前正文、scene_card 和本轮选中报告输出四档 verdict；PATCH 另产 directive |

### 当前输入与调用

1. 对本轮新增或改动场景运行三份 lint，未变化且已确认对应当前正文的结果可复用。脚本失败时记录具体缺项，恢复前不派该场 reviewer；不能让旧报告掩盖失败。
2. 运行现有 `machine_directive.py` 保持诊断接口。新统计只产 observed ledger，directive 可为空；已有 refreshed/pending 文件按恢复状态继续使用，不覆盖。该接口不把高频、cluster 或 family 名称转为必须改文的要求。
3. 调用本包 consistency-review A；B/C 按实际风险选取。每个执行者取得当前章范围和所派组指南，返回必要输入缺口。continuity-check 使用本章有序正文及合时来源，结果合入 B，更新实际受影响条目。
4. 明确本次可用的 A/B/C 报告及场景范围。未触发组的旧条目只在其输入仍有效时复用；失效条目从本次消费集合排除。`aggregate_global_findings.py` 使用固定 B/C 路径，因此运行前应使这些文件只包含当前有效结论，保留有效的 continuity 条目。
5. 对 `scene_id: null` 的全局 finding，由调用方按来源回相应设计或正文负责人。已确认的 CRITICAL 问题阻断章交付，但其他场景仍可完成有独立价值的取证。

派发 scene-review 前运行：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_scene_review_inputs.py \
  --scene-id S01 --pipeline-root "$WORK_DIR"
```

exit 0 允许继续；exit 1 表示缺输入；其他非零表示工具/运行错误。调用方在本次目标路径写 `scene_id / verdict: ESCALATED / review_incomplete: true / missing_inputs / written_by: orchestrator_input_gate`，保留具体问题。初审目标为 `scene_{id}.yaml`，复审目标为 `.post_revision.yaml`；不把复审失败写到首次 verdict 上。补齐后移走该降级文件，再派当前任务。只有需要作者选择的冲突才交用户。

### 四档路由与恢复

scene-review 派发带本轮报告范围，以及 `<work_dir>/pipeline/scenes/scene_<id>.md`、审阅输出 `<work_dir>/pipeline/review/scene_<id>.yaml` 和 PATCH 输出 `<work_dir>/pipeline/scene_<id>/patch_directive.yaml` 的绝对路径。文件 verdict 为权威；回执与指定位置的交付不符时回执行者补正。已有有效结果可恢复使用；需要新复审时先处理失效目标，`already_reviewed` 本身不证明完成。

| verdict | 调用方动作 |
|---|---|
| PASS | 本场叙事通过；检查是否仍有真实待处理的既有 machine directive |
| PATCH | 校验当前补丁后派 serial-reviser；complete 后 mark_patch_applied，partial 保留未应用条目；改动后按 Step 6 复审 |
| ROLLBACK | 正确输入下重新生成本场，更新尾窗及受影响依赖，再按 Step 6 复审 |
| REWRITE | 修复实际上游来源和投影，fresh writer 重写本场，再按 Step 6 复审 |

PATCH 派发前沿现有 hook 校验；宿主未执行 hook 时显式运行相同脚本：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_patch_directive_traceability.py \
  --scene-id S01 --pipeline-root "$WORK_DIR"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_rewrite_patch_schema.py "$WORK_DIR" --scene-id S01
```

校验失败回 patch 生产者；anchor 或 old_span 必须命中当前正文，不重复执行作者已接受/延期的 finding。派 serial-reviser 时明确唯一正文、已校验 directive 和 `revision_summary.md` 的绝对路径；新修订任务不能仅沿用另一子任务的目录简称。完成后读取指定位置 summary 的 status 并核对回执：

- complete：调用 `mark_patch_applied.py --scene-id <id> --work-dir <章目录>`。
- partial：未应用项仍在 pending directive，保留已完成改动，回导致剩余问题的负责人；不能按 complete 清空它们。
- failed 或缺/坏 summary：记录具体输入或执行失败，不能宣称正文未变；先核实实际落盘状态再恢复。

ROLLBACK 使用 §1 的同一 writer 派发契约：重新确认 `current_ref_path`，未选中为“无”；`authorized_role_move_slugs=[]`，除非本次重新成功取得并明确选用。按阅读顺序确定上一场尾窗，保留本场 role_views 与作者侧上下文，不把旧候选当作当前输入。角色交流需参考时沿 §1 的 `dialogue_ref` 选择；不强制重新排练。

REWRITE 跨回合恢复保留首次 verdict：场景卡/编排交 chapter-scene-plan；系列世界、人物、主线或卷纲交 serial-outline 路由。修好来源后更新相关 context、scene_card、role_views 和实际依赖，复用已有章目录，不再次物化覆盖现场。然后 fresh writer 重写，刷新检查并以 post-rewrite 产生当前 `.post_revision.yaml`。旧 post-review PASS 不能证明此次修复已完成。

### Step 5.6 既有机器修订的接续

本段只处理工作区实际存在的待修 directive。新统计的空 directive 直接跳过；不因 raw cluster、高频或新 family 重造修订任务。已存在的 pending 不能静默删除，先结合当前正文确定问题及授权范围。

仍有具体问题时，先完成前述定点修订与其复审，再执行分布修订，避免场景改写使原补丁失去锚点。复用本次有效 directive，经 `machine_directive.py --refresh` 装配当前保护区与 dispatch_ready 后派 serial-distribution-reviser。refresh 前排除不属于本次处置的旧 objection；有记录需保留时沿既有工作区历史保存，不让旧申请自动作用于新正文。

既有 pending 经当前语义判断为合法表达时，可使用现有 machine_objection 兼容结构记录本次证据：target_entry_id、family、精确 evidence_quote、具体 function_claim。由原脚本核对定位并记录处置；没有数量、等级或装置预算要求。它服务实际存量事项，新运行无需制造该文件。

分布修订读取同一当前场景与保护内容，写现有 distribution_summary。完成一次实际修订后，运行 ai_filler 的本次 `dist<attempt>` 输出，再调 `distribution_gate.py --attempt <attempt> --max-attempts <本次执行预算>`。attempt/预算属于现有恢复接口；依据实际未完成问题决定是否继续，不能按统计残余固定循环。

- gate exit 2：输入或工具错误，回负责人。
- gate exit 1：施工状态或保护条件未完成，保留 directive/summary，检查原因后决定继续或回交；不能扩大修改追求频数清零。
- gate exit 0：机器接口完成，仍按 Step 6 对照修前后检查原问题、阅读连续性、人物声音与事实约束。脚本将 entries 记 resolved 不替代这项判断。

分布修订改变正文后更新尾窗，复用已有 post-review 路径核对受影响内容。任何 escalated 条目表示待决，不能当作完成放行。进入章装配前，调用 `verify_review_complete.py <章目录>`，确认语义与实际待修项均闭合；随后由 assemble_story 按现有有序索引装配，不按文件名猜顺序。

## Step 6: Post-revision review

PATCH 已实际改动、ROLLBACK/REWRITE 或分布修订产生新正文后，更新受影响的 lint：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ai_filler_lint.py \
  --scene-id S01 --work-dir "$WORK_DIR" --output-suffix v2
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lexical_stats.py --scene-id S01 --work-dir "$WORK_DIR"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dialogue_lint.py --scene-id S01 --work-dir "$WORK_DIR"
```

PATCH 只有需要判断具体片段变化且本次实际应用记录可定位时，使用已有 `run_local_lint.py`；其结果只作片段线索，不成为每个补丁的额外手续。partial 时不能把尚未应用的条目当成已修。ROLLBACK/REWRITE 和整场分布修订直接使用当前场景检查。

按已有 A/B/C 与 continuity-check 职责刷新实际受影响证据；先前场景改动导致后续知情、状态或因果变化时，更新对应 role_view、尾窗与依赖正文。纯措辞变化无需重做全章。

清理本次失效的 post_revision 目标，保留首次 verdict；派 scene-reviewer 的 post-revision/post-rewrite 形态，明确当前报告范围、原问题与实际修改记录。复审方法和字段由 [复审协议](../../scene-review/references/post-revision-review.md)负责。输入缺失由本段 input gate 交接；当前语义 PASS 和相关机器完成分别判断，格式成功不能替代问题解决。

`patch_directive.yaml` 仍由 scene-review 的 PATCH 档产生并消费。用户直接要求的文字改写沿对应写作/修订工坊及作者授权，不伪造审阅产物建立第二条章 dispatcher。

---

## 2. role_view 派生协议

**触发与输入**：每场景在 `scene_card.md` 提取后、writer 启动前派生。章卡的人物选择与 `serial_context.md` 应在章内编排前已具备；场景设计变更后按实际影响更新章卡、重装配、重新提取，再派生受影响角色的视图。

按 §0 派 `serial-role-view-deriver`。输出为 `pipeline/scene_{scene_id}/role_views/{slug}.yaml`，逐角色表达合时身份、已知信息、可观察刺激和当前限制。完整字段与缺失语义归本包 [role-brief-deriver](../../role-brief-deriver/SKILL.md)；来源权限与作者/角色分工归 [上下文协议](context-contract.md)。本协议不镜像 schema，也不把人物欲望或动作改写成执行命令。

**完成与失败**：根据本次派生回复与本场 participants 核对所需 role_views。缺文件、缺必要输入、时点矛盾或字段不符时，先交造成问题的装配、编排或派生环节；需要作者事实裁决时才交用户。输入恢复后重做受影响派生，再继续 writer。未解决时停止本章正文顺序推进，并沿现有 ESCALATED 记录交接。旧 `role_briefs.md` / `*_rehearsal.md` 保留在原工作区，新链路不读取它们，也不进行未经语义重建的字段改名转换。

## 3. direct-writer 链路

- 按 §0 派 `serial-writer`，输入包括 `scene_card.md`、本场全部 role_views、作者侧 `serial_context.md`、上一场 `draft_tail.md`（章首用 `prev_chapter_tail.md`）和其他 writer skill 规定的条件材料。
- 传 `authorized_role_move_slugs`，默认为空。仅本次成功且与当前 role_view 相容的可选行动进入授权列表；文件存在、旧回执或上一轮授权均不构成本次授权。writer 保有场景实现裁量，actor 候选不会升级为必须逐项落地的动作。
- writer 只产 `pipeline/scenes/scene_{scene_id}.md`；dispatcher 随后提取 `draft_tail.md`，再启动下一场。缺必需输入或输入冲突时，按上下文协议回交来源环节，修复前不靠 writer 猜补。
- 本包 writer skill 拥有输入消费、散文/对白 skill 加载与回执要求。审阅和修订沿用下文现有机制；改变上游输入后只重建受影响视图与正文。

---

## 3.5. scene-reference 调度与消费语义（仅在装有 MUSE-canon-distill 扩展包时生效）

> 本节定义 orchestrator 侧的**调度时点 + 判据** 与 writer 侧的**消费契约**。`scene-reference` skill 由 `MUSE-canon-distill` 扩展包提供，主干 plugin 单独运行时本节默认 graceful skip。扩展包内部检索策略、query 构造、脚本入口、KB 内容描述均归扩展包自身职责，本文件不复述（细节由扩展包 `scene-reference` SKILL.md 自身承载，按 D7 闭包纪律不构造 link）。

### 3.5.1 调度与本次有效输入

role_view 派生完成后、writer 开始前，按当前缺口或作者指定用途选择参考。复杂场面可提示检查是否需要取材，题材标签、角色数量或单个 lint 命中不强制查询。已有适用来源直接复用；作者关闭参考时返回“无”。

通过宿主可用的包限定 `scene-reference` 入口，传 work_dir、scene_id、当前叙事问题、已知人物/视角/信息条件及实际来源范围，同时继承本次已确定的 `reuse_mode` 和 `intended_domains`。类型参数使用来源包认可的 genre；具体表达问题放 narrative_problem，无法匹配类型时可省略。查询不要求固定句数。`select_current_scene_reference` 在伪代码中表示此选择：只有本次成功取得，或经确认仍适用于当前任务的来源，才返回其 Path；其余返回 None。

`current_reference_scope` 从当前任务、已确认设计和实际采用决定中取用既有字段：reuse_mode 为 maximize_apt_reuse / style_only，intended_domains 使用 world_rule / reveal_structure / protagonist_archetype / scene_carrier / prose_style_imitation 的实际子集。调用方已明确用途时交给 scene-reference 传递到 `kb_query.py --reuse-mode ... --intended-domains ...`。已有本次适用的 Phase 0 canon_reference_profile 时，传其实际文件路径给 `--canon-reference-profile`，让来源包逐来源保留不同用途；不为连载补造 Phase 0。缺字段按来源包既有兼容方式处理，不为调用补造作者决定。纯文风用途会收窄为 style，世界规则用途最多 material；题材、相关性分数或手选本身不扩大作者采用范围。

actor 确需对白案例时，可在同一选材环节通过 canon `dialogue-reference` 传 work_dir、scene_id、role_slug；只给本人 view 可知信息。`select_current_dialogue_reference` 返回本次有效路径或“无”，无匹配照常依据人物材料完成。检索方不取得对手秘密，actor 不接收全场 ref。

扩展未装、查询失败或 NO_MATCH 时不把旧同名文件当成功。必要的用户指定来源缺失则回调用方，普通可选参考不阻断创作。首稿与 ROLLBACK 派发均明确 current_ref_path 与 dialogue_ref 的实际范围。

### 3.5.2 消费与回执

writer 在生成前取得当前有效 ref，按本包 [writer 的复用契约](../../writer/SKILL.md#参考与复用)解释已确定用途、条目范围及 reuse_tier/reuse_mandate，完成实际采用回执。正文方法与完整复用规则由 writer/craft 持有；派发只补当前路径、采用字段和激活项。

只有确认子执行者已取得本包职责和必要参考，才省去静态规则重述。上下文丢失、来源变化或可定位的执行遗漏发生时，补回对应指导；不按模型名复制整套派发策略。旧同名文件不自动生效，必需的指定来源缺失回其负责人。

### 3.5.3 ref 对齐校验（orchestrator 侧，writer 落盘后）

本次已选参考，且有具体密度疑点需要比较时，可在正文落盘后运行来源包实际提供的对比工具：

```bash
python3 <MUSE-canon-distill>/knowledge-base/scripts/paragraph_density.py \
  --compare pipeline/scenes/scene_{sid}.md <ref_source_file> \
  --format yaml > pipeline/review/lint/{sid}.density_vs_ref.yaml
```

`<ref_source_file>` 从本次所选参考条目的 `ref_source_file:` 取得；多条来源按实际采用对象选择。脚本不可用或来源无该字段时跳过，不把别的片段补作对照。产物只给 scene-reviewer 定位差异，不独立要求改文或按数值收敛。
