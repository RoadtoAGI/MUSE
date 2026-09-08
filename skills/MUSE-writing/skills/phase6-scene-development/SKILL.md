---
name: phase6-scene-development
description: MUSE Phase 6 — 场景展开。pipeline 中唯一产出正文的阶段：orchestrator 逐场景派生 per-role role_view，普通场景直接调度 writer；承重人物语义命中时先隔离调度 character-actor 产可选 role_move。由 orchestrator 推进到 Phase 6 时按宿主能力加载。属 pipeline 内部阶段件，不直接承接用户自然语言入口；单场景散文改写或对白修订由 prose-craft / dialogue-craft 承接。
---

# Phase 6: 场景展开

本阶段把 Phase 5 场景设计与人物上下文交给 writer，完成正文、审阅和必要修订。主控读取 [执行协议](references/execution-protocol.md)，负责恢复、上下文选择、派发与验证；正文由 writer 产出，场景 patch 由 reviser 执行，机器合同交 distribution-reviser。

## 执行总览

```text
核对当前设计与既有场景
  -> 按 Phase 5 呈现顺序完成尚缺正文
       -> role-brief-deriver -> 逐角色 role views
       -> 当前有效参考 / 条件 character-actor
       -> writer -> draft_tail
  -> 全场正文就绪 -> L1 lint -> A + 条件 B/C -> scene-review
       |-- PASS -> 继续核对机器合同
       |-- PATCH -> reviser -> post-revision
       |-- ROLLBACK -> fresh writer -> post-rewrite
       `-- REWRITE -> 原设计 owner -> 更新受影响下游
  -> 当前机器合同有 pending -> distribution-reviser -> 复检
  -> 当前正文语义、保护与机器状态闭合 -> 索引 -> Phase 7
```

恢复沿既有有效正文、裁决、应用记录和轮次继续，不默认重写。必需人物输入冲突时暂停依赖它的正文；可选参考或 role move 缺失可继续。脚本应用或计量成功不代替当前正文的语义审阅。

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

## 人物路由

role-brief-deriver 为每名 participant 派生 `role_views/{slug}.yaml`。消化场景、人物资产、state 与 views 后，仍有须由该人物独有前提完成、且会改变关键行动、对白或关系结果的解释/选择空位，才独立派发 character-actor。常见情形是人物信念或盲区影响选择、信息不对称改变关系、canon 推理方式承重、多方利益需要各自判断。

角色数量、对白存在、key_scene 标签和 canon 身份只帮助定位问题。场景已给出功能角色的程序与结果时，writer 可直接完成。命中的 actor 可按需取得本人 dialogue-reference，返回可选 role move；不要求补齐或逐项采用。actor 报告必需输入问题时先回输入负责人，普通执行失败或空 moves 不阻断 writer。

## 当前参考与实现空间

扩展包可用且当前场景有参考缺口或用户指定来源时，按执行协议 §3.5 获取或确认 scene-reference。派发明确有效路径、`reuse_tier` 和存在时的 `worldview_reuse`：full 学习并实际复用贴切原句与段落，material 使用适用的来源事实/专名/术语，style 学习文风。世界事实的确定度与人物获知范围分别保持；动作、感知、对白与叙述均可承载材料。

`counter_prior_scene.used=true` 时传实际设计的处境、日常行为与适用限制，不追加默认的象征/心理描写禁令。参考、角色候选和场景材料的具体实现由 writer 按故事不变量与来源合同取舍。

节拍帮助理解压力中的动作/反应及其变化；观察、信息显形、独白与母题段落按实际作用组织。写作前由 writer 加载 [prose-craft](../prose-craft/SKILL.md)，含对白时加载 [dialogue-craft](../dialogue-craft/SKILL.md)。

## 输出

- `pipeline/scenes/scene_{id}.md`：每场唯一正文，纯 Markdown，无设计标签或执行批注。
- `pipeline/scene_{scene_id}/role_views/{slug}.yaml`：逐角色当前认知切片；可选 role move 位于 `pipeline/staging/scene_{scene_id}/{slug}_role_move.yaml`。
- `pipeline/scene_{scene_id}/draft_tail.md`：从当前正文提取的尾摘。
- `pipeline/phase6_development.yaml`：场景索引，正文完成或修改后由 `generate_phase6_index.py` 更新路径、顺序与字数；[输出结构](references/output-schema.md)列明字段用途。

现有审阅、patch、保护与机器状态路径由执行协议维护。只读 state 与相关正文足以支撑当前输入，不为缺少状态事务另建阻断或交付物。
