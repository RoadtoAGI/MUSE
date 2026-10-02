---
name: phase6-scene-development
description: 原创完整链的正文与场景审修编排，由 story-writing 推进到场景展开时调用；协调角色视图、按需排练、writer 和修订，单段润色由 prose-craft 或 dialogue-craft 承接。
---

# Phase 6: 场景展开

本阶段把 Phase 5 场景设计与人物上下文交给 writer，完成正文、审阅和必要修订。主控按本技能执行主干（恢复、逐场派发、审阅路由、索引交接）；PATCH 应用、ROLLBACK 重写、post-revision 复审、可选机器合同 lane 与 scene-reference 选择的命令手册在[执行协议](references/execution-protocol.md)，进入相应分支时读取。正文由 writer 产出，场景 patch 由 reviser 执行，机器合同交 distribution-reviser。

## 执行总览

```text
核对当前设计与既有场景
  -> 按 Phase 5 呈现顺序完成尚缺正文
       -> role-brief-deriver -> 逐角色 role views
       -> 当前有效参考 / 条件 character-actor
       -> writer -> draft_tail
  -> 全场正文就绪（evaluation/smoke 到此直接 -> 索引 -> Phase 7）
       -> L1 lint（定位线索）-> A + 条件 B/C -> scene-review
       |-- PASS -> 本场完成
       |-- PATCH -> reviser -> post-revision
       |-- ROLLBACK -> fresh writer -> post-rewrite
       `-- REWRITE -> 原设计 owner -> 更新受影响下游
  -> 作者要求 strict 时：机器合同 lane -> distribution-reviser -> 复检
  -> 当前正文语义与保护闭合 -> 索引 -> Phase 7（AIGC 机器合同由 wholetext 承担）
```

恢复沿既有有效正文、裁决、应用记录和轮次继续，不默认重写。必需人物输入冲突时暂停依赖它的正文；可选参考或 role move 缺失可继续。脚本应用或计量成功不代替当前正文的语义审阅；`run_intent` 的审阅深度由 [story-writing](../story-writing/SKILL.md) 定义，本阶段按执行协议落实。

## 输入与权责

| 输入 | 当前消费者与作用 |
|---|---|
| `phase5_scenes.yaml` 的本场 `sequence_expansions[].scenes[]` | 主控与 deriver 读完整设计；`extract_scene_card.py` 为 writer 生成 `scene_card.md`，保留事实、因果、目标效果及候选材料，隔离设计字段与内部关联键 |
| `phase2_character.yaml` | 作者侧人物设计，供构建与审阅；actor-facing package 由 character-persona 编译 |
| `story-character-skills/.claude/skills/{slug}/SKILL.md` | 人物已有经历、追求、判断习惯、声音与边界；每名 participant 按 build-meta 对齐 slug |
| 同目录 `state.md` | 已记录时点的主观状态，可选资料；本场知识按 role view 核对，不能假定它已自动跨场更新 |
| `scene_{scene_id}/role_views/{slug}.yaml` | 每名 participant 的当前可知事实、可见刺激与真实限制；只支配对应人物，不能相互补全秘密 |
| Phase 0 / 1 / 3 的相关字段 | 用户要求、参考与风格、世界机制和适用条件、故事组织力；具体读取清单由 writer 技能维护 |
| `scene_{previous_scene_id}/draft_tail.md` | 呈现前场的文字衔接；previous_scene_id 由 Phase 5 顺序给出，首场为“无” |
| 相关当前有效正文 | deriver 在知识/约束缺口处按故事时点与获知渠道补读；呈现次序不代表事件先后 |
| 本轮 reference 与 role moves | 仅消费当前派发明示授权的路径和 slug；目录中旧文件不自动生效 |

## 工作目录与恢复

命令中的 `WORK_DIR` 是本次作品目录，`MUSE_WRITING_ROOT` 是本包实际安装根；执行前按当前宿主解析。

每次派发明确 `work_dir`、本包实际位置、`scene_id` 与本轮模式。场景顺序来自 Phase 5 `sequence_expansions[].scenes[]`；`previous_scene_id` 取其呈现前项，不按 ID 减一。静态输入清单由各 agent/skill 维护；动态来源选择、前场 ID、role move 授权及必要保护条件直接随派发传入。宿主未预载所需 agent 时，主控先读取本包 `agents/{agent-name}.md`，将职责正文交给子执行者，或要求其先读取该绝对路径；子执行者随后加载文件指定的技能。仅有 agent 名称不表示职责已进入上下文。

`run_intent` 决定本阶段的审阅深度：`release` 执行下文全部；`evaluation / smoke` 只完成“逐场创作”与“索引与交接”，“全场审阅与四档路由”、patch 链与机器合同 lane 不执行（admission 按 intent 免除，终态不可发布），L1 lint 仍可运行作诊断记录，全文阶段由 Phase 7 的 wholetext、reader 与 B 对账承担。

子执行者默认继承本次主会话所选模型。注册 agent 与文件加载后派发通用子执行者采用同一政策；文件里的 `model: inherit` 由实际调用方落实。只有本次作者明确指定某项任务使用其他模型时才传覆盖值，沿既有派发说明保留该任务的选择。宿主强制配置使继承不可用时，报告实际限制及受影响任务，不把文件默认值当成实际运行模型。

进入时核对现有正文、裁决、pending directive、应用 summary 与 post-review：

- 当前设计下的有效正文继续复用，从未完成的审阅或修订环节恢复。文件存在只证明落盘；中断稿、已判失效稿与待重写稿不能冒充完成稿。
- 首次生成仅处理尚无有效正文的场景；已有正文只在当前 ROLLBACK 或作者明确授权重写时交 fresh writer 覆盖。恢复不重置既有 applied、protected 或合同轮次。
- 已有 review 仅在输入、正文和来源选择仍适用时复用。待应用 patch 先核对当前锚点及 application_id，按下方“全场审阅与四档路由”继续；不另设紧急修订流程。
- 必需人物输入失败时暂停依赖该输入的场景与后续场景，不让后场把未成立的计划当已发生事实。无此依赖的工作可以继续；在现有完成状态中保留具体缺口。
- `state.md` 是已有状态资料，可能只覆盖故事入口。按故事时点、获知渠道及相关当前有效正文补足 role view；未来场景的知识不能倒灌，actor/writer 不写 state。

## 逐场创作

首次进入本批场景写作前，按 Phase 5 的 `sequence_expansions[].scenes[].participants` 核对本次人物与 Phase 2 设计、build-report 和 build-meta 的 name→slug 映射。已有核验结果只在参与者、人物设计及资产均未变时复用。角色缺设计或映射有歧义时，先回 Phase 2 人物负责人确认来源与身份；已有设计但未建、缺失或失效的角色包，由其调用 character-persona 构建或重建，再执行 `verify_phase2_assets.py <work_dir>`。该脚本核验角色资产；参与者是否齐备由本交接核对。修好来源和资产后更新受影响输入，才派生相应场景的 role_view；不让 deriver 或 writer 临时编造人物包，也不因跳过可选 actor 而跳过人物依据。

### 派生 role views 与场景卡

将工作目录、当前及前场 ID 交 `role-brief-deriver`。它从 Phase 5、人物 package、可选 state 和相关正文派生逐角色认知切片。participant 的中文名通过 `build-meta.yaml` 对齐 slug；不能把人物名直接当文件名。当前必需文件缺失、映射不唯一或认知事实冲突时返回输入负责人；不重复派发直到碰巧成功。

确认每名 participant 的 `pipeline/scene_{scene_id}/role_views/{slug}.yaml` 齐备且适用于当前时点，再生成 writer 投影：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/extract_scene_card.py" \
  --work-dir "$WORK_DIR" --scene-id S01
```

恢复时只重建受已变输入影响的视图。主控不补写角色答案或正文。

### 人物路由与可选 actor

role-brief-deriver 为每名 participant 派生 `role_views/{slug}.yaml`。消化场景、人物资产、state 与 views 后，仍有须由该人物独有前提完成、且会改变关键判断、行动、对白或关系结果的解释/选择空位，才独立派发 character-actor。常见情形是人物信念或盲区影响选择、信息不对称改变关系、canon 推理方式承重、多方利益需要各自判断。

角色数量、对白存在、key_scene 标签和 canon 身份只帮助定位问题。场景已给出功能角色的程序与结果时，writer 可直接完成。命中的 actor 可按需取得本人 dialogue-reference，返回可选 role move；不要求补齐或逐项采用。actor 报告必需输入问题时先回输入负责人，普通执行失败或空 moves 不阻断 writer。

writer 派发明确“本轮可读 role move 角色：[...]”；空列表不读 staging 中任何旧文件。参考选择见[执行协议](references/execution-protocol.md)的 scene-reference 节。

### 当前参考与实现空间

扩展包可用且当前场景有参考缺口或用户指定来源时，按[执行协议](references/execution-protocol.md)的 scene-reference 节获取或确认 scene-reference。派发明确有效路径、原有用途与领域、最终 `reuse_tier` 和适用的 `worldview_reuse`；采用语义由[参考采用契约](../writer/references/reference-adoption.md)维护。世界事实的确定度与人物获知范围分别保持；动作、感知、对白与叙述均可承载材料。

`counter_prior_scene.used=true` 时传实际设计的处境、日常行为与适用限制，不追加默认的象征/心理描写禁令。参考、角色候选和场景材料的具体实现由 writer 按故事不变量与来源合同取舍。

节拍帮助理解压力中的动作/反应及其变化；观察、信息显形、独白与母题段落按实际作用组织。写作前由 writer 加载 [prose-craft](../prose-craft/SKILL.md)，含对白时加载 [dialogue-craft](../dialogue-craft/SKILL.md)。

### writer 派发

派发包含：工作目录、本包位置、scene_id、前场 ID、本轮有效 reference 路径或“无”、获准 role move slugs；ROLLBACK 另给当前裁决目标和必须保持的已接受事实/保护关系。调用 `writer` 的职责与输入清单，输出唯一正文 `pipeline/scenes/scene_{scene_id}.md`。

`counter_prior_scene.used=true` 时传已有 `kind / mundane_action / emotional_context / forbidden_moves`，让 writer 理解所选日常行为的作用。只传设计中实际存在且适用的限制，不自动追加“不得象征化”或“不得心理解释”。候选实现仍按 writer 的权责层级取舍。

本轮 ref 的采用范围、最终 `reuse_tier`、已有 `reuse_mode / intended_domains` 与适用的 `worldview_reuse` 随派发明确，执行[参考采用契约](../writer/references/reference-adoption.md)。只给 scene_id 无法表达这些本轮选择；静态目录中同名文件也不取得输入权。

writer 成功并确认正文完整后提取尾摘，供下一场衔接：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/extract_draft_tail.py" \
  --work-dir "$WORK_DIR" --scene-id S01
```

有必要输入冲突或未完成正文时保持当前有效版本并报告缺口，不能以“已写文件”判定成功。

## 全场审阅与四档路由

全部所需场景的当前正文就绪后（`release`），沿既有 L1 → L2 → L3 执行。复用仍适用的成功结果；正文或输入变动后刷新受影响项。

### L1：定位线索

对当前场景运行 `ai_filler_lint.py` 与 `dialogue_lint.py`；两脚本接收 `--work-dir`、`--scene-id`，可传 Phase 0 的实际 genre。沿当前 policy 使用默认诊断条件，不由类型另造阈值。保留初稿报告，修后使用既有 suffix。`lexical_stats.py` 只在审阅者需要副词密度、TTR 或感官平衡统计时运行。lint 产物是 A 组与 scene-reviewer 的定位线索；普通词形与密度由语义审阅按实际作用判断，命中数不构成修改义务。缺输入、脚本失败、当前报告无法对应正文时不能沿旧结果继续。

机器合同 lane（`machine_directive.py` 与分布修订）默认不在逐场路径中，AIGC 机器合同由 Phase 7 `wholetext_gate.py` 对全文判断；作者明确要求 strict 时按执行协议“机器合同 lane”启用。

### L2：本轮来源与全局问题

A 默认运行；多线连续性、复杂人物关系等具体风险选 B，世界规则、时间线或设计对照风险选 C。用户明确 strict 时三组齐备。各组派发明确 work_dir、包位置与 `group=A/B/C`。本轮未选 B/C，即使目录有旧报告也不消费。

将本轮选择同时交全局聚合与 scene-reviewer：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/aggregate_global_findings.py" \
  --work-dir "$WORK_DIR" --source A
# 若本轮选择 B/C，分别追加 --source B / --source C。
```

选中报告缺失、非法或执行不完整时补齐该输入；不回退旧聚合。`global_findings.yaml` 中阻断当前设计/正文的真实问题回实际负责人，标明受影响场景。全局问题不被逐场 PASS 消除，也不需要另造场景 patch 来替代全局决定。

### L3：裁决与恢复

每场派 scene-reviewer；它自行读取当前正文、scene card、本轮来源与现有 lint，缺失、损坏或版本失效时在 `pipeline/review/scene_{id}.yaml` 写 `verdict: ESCALATED`、`review_incomplete: true` 与 `missing_inputs`。主控补齐输入后重派，不以旧降级报告代替裁决；需要排查输入时可运行 `verify_scene_review_inputs.py --scene-id S01 --pipeline-root "$WORK_DIR"`。

派发包含本轮选中的 A/B/C 来源、当前正文/lint 与模式。现有有效裁决直接续办；已失效裁决只在主控明确本次重审与替换权限后重写，不能因旧文件存在永久卡在 `already_reviewed`。

| 裁决 | 当前负责人和动作 |
|---|---|
| PASS | 本场语义审阅完成；启用机器 lane 时另核对其状态 |
| PATCH | 按[执行协议](references/execution-protocol.md)“PATCH 应用”执行 pending patch，并进入现有 post-revision |
| ROLLBACK | 当前设计有效，正文需重写；按执行协议“ROLLBACK 重写”更新受影响上下文，派 fresh writer，进入 post-rewrite |
| REWRITE | 回 finding 指向的 Phase 2–5 设计 owner，更新直接受影响下游后恢复 |

裁决依据实际损害与修复范围。诊断名称、词面命中或次数不自动升档。

## 索引与交接

所有正文采用 `pipeline/scenes/scene_{id}.md` 单路径；尾摘由当前正文提取。Phase 5 写入 hook 可生成索引骨架，正文完成或修改后按需刷新：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/generate_phase6_index.py" "$WORK_DIR"
python3 "$MUSE_WRITING_ROOT/scripts/verify_review_complete.py" "$WORK_DIR"
```

索引的正文路径、呈现顺序与字数对应实际文件。`release` 进入 Phase 7 要求所需场景与当前语义结果完整、全局阻断问题已处理、保护验证有效；启用机器 lane 的场景另要求其状态闭合，未启用的场景由 Phase 7 wholetext 承担。`evaluation / smoke` 由 admission 按 intent 免除场景级作者侧检查，受保护施工批次不免除。未知、pending、escalated 或输入不完整均不能借格式通过放行。

### 宿主执行

hook 注册见本包 `hooks/hooks.json`，现只保留写前保护与预检、YAML 契约、设计 token 泄漏、reviser 派发前校验、assemble 前准入、Phase 5 写后校验与短篇契约；L1 lint、索引生成与派发日志不再由 hook 代跑，按本协议在相应步骤显式执行。宿主未触发 hook 时，在相同操作点手动执行已有脚本；已成功的同版本检查直接复用。Phase 5 写后使用 `validate_phase5_r10.py <phase5_path> --scan-scene-tasks --scan-inspiration-refs` 与索引生成器，整合前使用上述 admission verifier。

## 输出

- `pipeline/scenes/scene_{id}.md`：每场唯一正文，纯 Markdown，无设计标签或执行批注。
- `pipeline/scene_{scene_id}/role_views/{slug}.yaml`：逐角色当前认知切片；可选 role move 位于 `pipeline/staging/scene_{scene_id}/{slug}_role_move.yaml`。
- `pipeline/scene_{scene_id}/draft_tail.md`：从当前正文提取的尾摘。
- `pipeline/phase6_development.yaml`：场景索引，正文完成或修改后由 `generate_phase6_index.py` 更新路径、顺序与字数；[输出结构](references/output-schema.md)列明字段用途。

PATCH 应用、ROLLBACK 重写、复审与可选机器 lane 的命令由执行协议维护。只读 state 与相关正文足以支撑当前输入，不为缺少状态事务另建阻断或交付物。
