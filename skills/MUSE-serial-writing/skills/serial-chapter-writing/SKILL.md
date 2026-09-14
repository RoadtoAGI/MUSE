---
name: serial-chapter-writing
description: 连载逐章创作与发布入口。用于续更、完成当前章或发布指定章，调度编排、写作、审阅、摘要和发布；系列立项与开卷用 serial-outline。
---

# 连载章节创作

本技能负责章循环的控制与交接。场景设计由 chapter-scene-plan 负责，正文由 writer / reviser 生成，reviewer 判定问题，summarizer 生成前情与台账候选。orchestrator 读取这些产物、维护状态并派发工作，保持作者意图到正文的连接。

本文件是章级控制权威；[执行协议](references/execution-protocol.md)展开场景派发与恢复，[上下文协议](references/context-contract.md)规定来源、时点、人物知情和创作裁量。字段分别留在其产物所有者处。所有同名技能均指当前 MUSE-serial-writing 包；宿主派发须携带包根、作品根 `series_root`、章目录 `work_dir`、章号，场景任务再带 scene_id，按执行协议 §0 绑定真实入口。

## 恢复与授权

先读取 series_state、当前卷纲和必要决策。缺系列工作区、卷纲或 `cursor.stage=breaking` 时交 serial-outline。其余情况运行：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_series.py --work-dir works/<slug>
# 上条 exit 0 后再认领
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_series.py --work-dir works/<slug> --claim-session <session_id>
```

对账与认领是两个独立命令，按上述次序执行。exit 2 时按恢复矩阵报告断点，完成恢复后再推进；exit 3 时另一 session 持有写者标记，须由用户裁决接管。已有同根、同会话且状态未变的有效对账可复用；发布恢复、外部写入或重新进入会话后重跑。

`pending` 非空时核对待决对象、依赖和当前授权；已取得的明确裁决落入对应产物后清理已解决事项。未决选择只暂停依赖它的动作，其他已授权工作继续。例如下一卷方向待决，当前章的已定稿审阅、摘要或已授权发布仍可完成。需要作者裁决时按[协作协议](../serial-outline/references/collaboration-protocol.md)交接；正常结束或待决离会时保存实际进度并释放 active_session。

外层入口拥有会话认领与释放。内部技能和子执行者使用外层传入的 session ID，复用同一 marker，返回时不释放；外层在整个作品事务结束，或保存 pending 后离会时运行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_series.py --work-dir <series_root> --release-session <session_id>`。空 marker 可重复释放；他人 marker 返回 exit 3，不能替其清除。


共创授权、候选文件及决策消费沿[协作协议](../serial-outline/references/collaboration-protocol.md)。volume / chapter 档决定需要向作者提出哪些选择；本次授权已经覆盖的步骤直接衔接。默认 volume 档在开卷、副本选型和重大转折上请作者决定；chapter 档另在单元批次与逐章走向上确认。具体已授权的选择无需重复询问，冻结修订仍核对该项授权。作品根、章工作区和工具根分别传递，不能按当前 cwd 猜测。

## 章循环

```text
已有授权与可用来源
        |
        v
单元编排 -> 首次物化 -> 选材/装配 -> 章内场景设计
                                         |
                          有具体设计疑点时 outline-validation
                                         |
                                         v
              按阅读顺序：场景卡 -> role_views -> writer
                                     可选 actor / reference
                                         |
                                         v
               当前正文连续性证据 + 既有 A/B/C -> scene-review
                                         |
                           PASS / PATCH / ROLLBACK / REWRITE
                                         |
                              受影响修订与既有 post-review
                                         |
                              machine distribution 通道
                                         |
                                         v
                 装配 draft -> AIGC 防治 -> recap 入 buffer
                                         |
                         发布授权 -> 现有发布事务 -> 下一章
                                         |
                            单元/卷收束 -> 对应 digest
```

1. **滚动编排**：运行 `match_decisions.py list --work-dir <series_root> --level unit --volume V## --unit U##`，把命中的未消费决定用于本单元卷纲条目。批次长度按已有因果安排和可确认程度选择；先写当前需要的章，远处保留方向。条目落盘后回写消费标记。章节设计保留 logline、hook_type、opened/closed 和明确的前后链，未来计划不预记为台账事件。
2. **首次物化**：运行 `materialize_chapter.py --work-dir <series_root> --volume V## --chapter C####`。已有章目录恢复使用；重建设计时更新原产物和相关投影，不再次物化覆盖当前章。已有创作前章缺 recap 则先回其收束环节；接管历史无章目录时使用 manifest 定位的原文尾窗及回填摘要。
3. **选材与编排**：调用 chapter-scene-plan，先按本章卷纲意图、前章和必要索引选人物、实体及设定分册，补章卡后装配并读取 serial_context，再写 phase5_scenes。定稿同步章卡的 recap_inputs / pov / scene_plan，输入变化时刷新上下文。设计落盘或改动后，用 `generate_phase6_index.py <work_dir>` 按当前 phase5 生成完整场景索引；宿主 hook 已成功生成同一设计的索引时复用，文件加载宿主显式执行。具体跨源疑点或用户要求设计核查时，调用 outline-validation（scope=chapter，给疑点与来源路径）；读取现有 `pipeline/review/design_validation.yaml` 中 findings 与 `summary.input_gaps`，由实际负责人处理影响本章的硬错。无需为此补造 Phase 1–4。
4. **逐场景创作**：按 phase5 阅读顺序运行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_scene_card.py --scene-id S## --work-dir <章根>`，成功落卡后派 serial-role-view-deriver；有行动探索需要时调用单角色 serial-character-actor，再派 serial-writer。writer 只接本次成功候选的 `authorized_role_move_slugs`，缺省为空。人物输入有误先回来源负责人；普通可选探索失败可跳过。场景完成后提取尾窗，`extract_draft_tail.py --work-dir` 同样传含 `pipeline/` 的章根，再写下一场。角色知情按故事时点判断，呈现顺序可不同于时间顺序。
5. **审阅与修订**：全部场景写出后，continuity-check 根据有序场景检查跨章事实与本章承诺，其 findings 合入现有 B 报告。执行协议安排 A/B/C、场景输入检查和 scene-review；连续性检查的必要输入缺口先回源，未恢复不能视为通过。四档路由见下节，所有场景叙事与机器通道闭合后，运行 `assemble_story.py <work_dir>`，按设计索引生成完整 `draft.md`。
6. **章级防治**：serial-aigc-guard 处理本章，派发时传作品根、章目录、当前正文与外层 session ID，由本入口保留会话所有权并在离会时释放；防治完成签发既有 aigc_clearance。签发后任何改文须按其 verify_only 流程复检重签。后期修订如果改变事实、知情或章末承诺，复核受影响的连续性结论；事实或设计问题回对应负责人，不能用防治措辞修补掩盖。场景正文与 draft 在后期修订时的权限、同步和恢复须遵守该修订技能，不能用旧场景重新装配覆盖已接受的章稿。
7. **摘要与 buffer**：派本包 chapter-summarizer，提供当前定稿、作品根、章目录和章号。orchestrator 对照正文确认 summary 的事件结果、必要人物状态和章末落点；发现失真回 summarizer 修复。有效 recap 进入 buffer，候选尚未入账。单元确已结束时可在本次调用一并生成 digest，发布时不重复生成。
8. **发布**：确认当前动作已获授权。recap 依赖前章候选时，按前章链发布依赖，再让 summarizer 依据 note 补齐真实 supersedes；未解时保留 buffer，暂停该章发布。运行 `publish_chapter.py --work-dir <series_root> --chapter C####`，依次预检、转正 deltas、复制正文、登记 manifest。thread 预检只读投影当前 recap，未来章计划无需提前入账。完成后，若 cursor 仍指本章，清空 `working_chapter`，按实际后续工作转入 `outlining` 或 `volume_closing`；已有其他在写章的游标保持。失败按断点幂等恢复；转正开始后不再把 recap 当普通候选重写。
9. **卷收束**：核对卷问题与仍有效的承诺。world_reveal_plan 中计划应按实际情况转为 fulfilled（带 fact_id / chapter_id）、carried_to_next_volume 或 dropped_by_decision；未解决的方向交作者。按来源生成角色卷快照和卷 digest，完成后冻结卷纲，再交 serial-outline 开下一卷。角色稳定时可无变化增量，不为收束虚构内在成长。

## 反馈与恢复

| 裁决 | 负责环节与关闭条件 |
|---|---|
| PASS | 本场叙事通道闭合；仍需处理实际 pending machine directive |
| PATCH | serial-reviser 消费 scene-review 的可追溯补丁；修后刷新相关机器结果，并由既有 post-review 确认语义问题解决 |
| ROLLBACK | 输入成立但正文实现失败，fresh writer 依据当前场景输入重写；更新尾窗和本轮有关检查，再 post-review |
| REWRITE | 章内设计交 chapter-scene-plan；世界、人物、脊椎或卷结构交 serial-outline 路由。修好来源、更新受影响上下文后 fresh writer 重写，再 post-rewrite 复审 |

首次 verdict 保留；修订结果落既有 post_revision 文件。脚本形式通过只证明相应形式条件，不能代写语义 PASS。输入缺失、工具失败和作者待决沿现有 ESCALATED 交接，但应先由能修复的负责人处理，只有需要作者决定时才询问用户。

较早场景修订改变信息、因果或当前状态时，检查哪些后续 role_view、尾窗和正文依赖它，更新实际受影响部分；纯措辞变化无需重跑整章。恢复操作遵循执行协议，不创建第二条修订路径或强制全量复读。

## 缓冲区与创作边界

- 方向反馈进入 decisions 并影响未定稿设计；执行反馈处理当前实现。用户授权具体改向后才能改变相应故事方向。
- 重写 buffer 中段章时，其后 buffer 章降回 outline，或由用户明确选择保留；已发布正文保持原样。发布事务已开始时先恢复事务状态，再决定后续修订。
- orchestrator 只写控制、状态和机械装配结果，场景正文由本包 writer / reviser 产生。这是项目的职责隔离选择。
- 编排中的 counter_prior_scene、prose_risk_contract、参考复用策略由场景卡和参考文件供给，dispatch 仅提示当前激活项；适用条件和已确认作者禁界继续有效，不重复转写为固定动作。
- 已安装参考扩展且存在适用场景或用户要求时，按执行协议 §3.5 调用；用户关闭参考时跳过。直接使用角色台账与正文的接管不要求补完整角色包。

创建或核验 phase6 索引时读[输出格式](references/output-schema.md)；进入场景调度时读执行协议对应部分。创作与修订工坊保留自身方法，不由 orchestrator 镜像执行。
