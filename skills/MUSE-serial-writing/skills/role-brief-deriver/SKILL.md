---
name: role-brief-deriver
description: 连载单场景的逐角色 role_view 派生。由 serial-role-view-deriver 按故事时点整理身份、所知与可感条件，供 writer 和可选人物表演消费。
---

# 连载场景的人物输入派生

为每个在场角色提供此刻成立的人物依据、已知事实、可感刺激和现实限制。writer 据此写作，可选 actor 据此独立作出角色选择。人物资料的丰富程度决定切片内容；接管作品可以直接使用人物台账。

先读取本包[上下文协议](../serial-chapter-writing/references/context-contract.md)，取得故事时点、人物绑定和各输入的权限。协议适用于本技能全部来源与交付。技能及 reference 通过当前宿主支持的技能调用或明确文件读取取得；按 dispatch 给定的包入口加载。

## 输入与来源

dispatch 必须给出 `{work_dir, series_root, scene_id}`。`work_dir` 是含 `chapter_card.yaml` 的章目录，`series_root` 是含 `series/`、`published/` 的作品根。下文 `pipeline/` 相对 `work_dir`，人物与发布资料路径相对 `series_root`。

| 来源 | 用途与取得时机 |
|---|---|
| `pipeline/phase5_scenes.yaml` 中当前场景 | 确定参与者、故事时空、可见事件与本场范围；完整设计只供派生判断 |
| `pipeline/serial_context.md` | 章级作者事实及所选人物的合时状态；必读，不把所有事实当作所有角色已知 |
| `series/ledgers/characters/{char_id}/persona.md`、`snapshots/`、`biography.yaml` | 在章上下文缺少身份、声音、经历或获知依据时，读取当前人物的相关合时部分 |
| `published/manifest.yaml` 定位的已发布原文、当前有效已写场景 | 按需核实获知渠道、同场事件先后、倒叙与跨章经历；只读相关位置 |
| `series/character-skills/.claude/skills/{slug}/build-meta.yaml` 与角色包 | 按需使用已有兼容包时，以 build-meta 的 character_id 核对映射，以 through_chapter 和来源核对时点；旧包缺字段回查来源，不能直接采用最新 state.md |
| 前场 `draft_tail.md`、跨章 `prev_chapter_tail.md` | 仅作衔接线索；尾窗遗漏不能证明某事没发生，也不能代替时点判断 |

`phase2_character.yaml`、正式角色包、adapter 均非接管前置条件。章卡或章上下文缺失、所需人物未被纳入装配时，返回具体缺口，由 orchestrator 补选并重装配；不自行补造资料。人物 ID、别名映射和一次性功能角色按上下文协议绑定，禁止由显示名猜 slug。

## 按故事时点派生

先由 `location_time` 和既有因果关系定位事件时点。场景编号、呈现次序、章节编号只用于定位文件，不证明故事时间先后。再对每名角色判断哪些经历已经发生、哪些事实已通过亲历、目击、传达或其他明确渠道进入其认识。

- 人物基线与快照按其来源截止范围使用；晚于本场的知识、关系和变化留在作者侧。倒叙缺少合时人物切片时，按原文和台账定位早期资料，不继承共享角色包的最新状态。
- 世界事实的确立时点只说明事件已成立；秘密还要核对 `known_by` 的人物与 `learned_at`。同一章内的获知先后不清时查看相关原文，不能仅凭章号相同开放秘密。
- 当前有效正文是本轮已生成且未被既有失败或回滚状态撤销的版本。场景计划尚未写成发生事实；前场正文改动了相关事实时，再派生受影响场景的切片。
- 资料矛盾时先区分事实变化、角色误信与作者判断。能定位来源的误信可以作为该角色的认识保留；事实未决且会改变本场行动时，返回来源冲突及负责补齐的位置。

## 输出契约

每个 participant 写一份 `pipeline/scene_{scene_id}/role_views/{slug}.yaml`。`slug` 是上下文协议已绑定的文件键；同一值写入 `character`。只为当前场景生成；旧 `role_briefs.md` 保持原状，新链路不读取或自动转换它。

本节是本包 role_view 的字段权威。恰有以下六个顶层键：

```yaml
scene_id: S0X
character: <已绑定的角色文件键>
character_basis:
  - "<本场时点已成立且有关的身份、经历、长期追求、声音或人物自觉信念>"
known_now:
  - "<角色在本场时点已经掌握的相关事实、承诺或关系认识>"
observable_stimuli:
  - id: cue_1
    cue: "<该角色届时能够看见、听见或直接感到的具体表面；含必要的发生条件>"
constraints_now:
  - "<当前已成立且角色可知的身体、时间、资源、权限、空间或已付关系代价>"
```

后四项均为 list；无有据内容时用 `[]`。`character_basis`、`known_now`、`constraints_now` 的条目为非空字符串；`observable_stimuli` 每项只含本文件内唯一的 `id` 和非空 `cue`。不为填字段虚构人格、情绪、秘密或刺激；核心人物缺乏足以承接本场选择的依据时报告输入缺口，场景明示身份的一次性功能角色保留所需的简短依据即可。

## 内容边界

| 字段 | 保留的决策信息 | 排除的越权内容 |
|---|---|---|
| `character_basis` | 此时身份、已活过的经历、稳定表达方式、自觉长期追求及有据信念；声音适用的关系与语境 | 作者诊断的潜意识、核心缺陷、未来弧光；按职业标签补写的心理；本场预定目标或情绪 |
| `known_now` | 角色已经获知的事实、承诺、与来源一致的误信或不确定认识 | 全知事实、对手私密目的、后续揭示；用“他不知道……”列出秘密 |
| `observable_stimuli` | 场景入场已成立的感知，以及届时满足条件才会出现的可感表面 | 预定回应、作者解释、离场答案；要求对方先执行某个候选动作才能成立的无条件刺激 |
| `constraints_now` | 人物可感且确实缩小行动范围的外部条件 | 伦理答案、表达策略、职业程序、为抵达章纲结果而下达的动作命令 |

已作出的承诺归 `known_now`，长期信念归 `character_basis`；怎样履行或违背由人物在本场条件下决定。作者明确的事实或行为禁界继续由 writer 的作者侧输入承载，不伪装成角色自觉。

例如，已知“右腕骨折，握不住长柄工具”会改变行动条件；“必须亲自救人”提前给出人物答案。已经承诺救人可以作为人物知道自己许过诺的事实，其后选择仍须由处境与代价产生。这个区别适用于同类承诺与资源限制，不规定角色最终选择。

## 交付与异常

逐角色完成时顺手核对绑定、故事时点和来源归属，确认没有把同一事实分别改写成目标、情绪和动作要求。所有 participant 文件可供本次 dispatch 消费后回复 `done role_view for scene {scene_id}`。

缺少会改变角色身份、知识边界或本场可行性的输入时，回复 `role_view blocked for scene {scene_id}`，列出人物、事实和应补齐的来源；orchestrator 修复后只更新受影响切片。字段中不写 `pending` 占位，不修改人物台账、章纲、正文或共享 runtime state。
