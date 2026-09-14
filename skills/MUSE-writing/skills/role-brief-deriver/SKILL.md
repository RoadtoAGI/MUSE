---
name: role-brief-deriver
description: 为原创完整链的当前场景派生逐角色认知切片，供 actor 和 writer 使用；由同名 agent 加载，只过滤人物已知事实、可感刺激与实际限制。
---

# role-brief-deriver：Phase 6 runtime role_view 派生

## 执行总览

```text
scene_id
  -> required input gate
       |-- scene card / role package / build-meta 缺失 -> 失败退出
       `-- 完整
            -> 读取可选 state 与前场景 tail；缺失时按合同回退
            -> 遍历 participants
                 -> 从人物已知信息与本场可见表面派生 role_view
                 -> 写 role_views/{slug}.yaml
            -> 返回成功供 actor / writer 消费
```

派生只收敛既有设计与 runtime 状态，不新增场景走向或正文。

## 核心原则

> role_view 是 Phase 6 为单个角色编译的场景认知切片。它只交付角色此刻可用的事实、可见刺激与可感限制，让 actor 在角色自身经历和状态上独立完成判断。

**范围边界**：
- **只做派生**，不产正文 / 叙事 / 对白
- **只做认知过滤**，不替角色规定目标、情绪、误读、行动、台词或场景答案
- **当前输入的一场景派生一次**，由 orchestrator 通过当前运行时 subagent dispatch 启动；不通过脚本 / CLI wrapper 启动（详见 [Phase 6 执行协议](../phase6-scene-development/references/execution-protocol.md)）

## 输入契约

每次调用明确 `work_dir`、本包位置、单个 `scene_id` 与呈现前场 `previous_scene_id`。下列路径相对该作品的 `pipeline/`。

| 文件 | 必需 | 路径（相对 `pipeline/`） | 缺失时的处理 |
|---|---|---|---|
| Phase 5 scene_card | 必需 | `phase5_scenes.yaml`（定位 `sequence_expansions[].scenes[]` 中 scene_id 匹配项） | 失败退出 |
| 角色 runtime package | 必需 | `story-character-skills/.claude/skills/{slug}/SKILL.md`（角色长期人设 / 声音权威源） | 失败退出 |
| 角色 build-meta | 必需 | `story-character-skills/.claude/skills/{slug}/build-meta.yaml`（读取 `character_display_name`，用于 participant 与 slug 对齐） | 失败退出 |
| 角色 runtime state | 可选 fallback | `story-character-skills/.claude/skills/{slug}/state.md` | 缺失时只使用角色 package 中已经成立的信息 |
| 前场景 draft 尾段 | 可选 fallback | `scene_{previous_scene_id}/draft_tail.md` | 仅提供局部衔接；缺失不补造事实 |
| 相关当前有效正文 | 按需 | `scenes/scene_{id}.md`，由 Phase 5 时空与因果关系定位 | state / tail 不足以解释本场知识或约束时读取相关部分；未写的计划不作为已发生事实 |

## 输出契约

### 输出路径硬约定

- **逐角色文件**：`pipeline/scene_{scene_id}/role_views/{slug}.yaml`
- 每个 `participant` 恰有一份同 slug 文件；不生成包含其他角色信息的合集版

### 输出 schema

每角色 YAML：

```yaml
scene_id: S0X
character: <slug>
known_now:
  - "<角色入场时确实掌握、且与本场有关的事实>"
observable_stimuli:
  - id: cue_1
    cue: "<角色在本场届时能够亲眼看见、听见或直接感到的具体刺激>"
constraints_now:
  - "<人物意志之外、当前实际缩小可行动范围的身体、时间、资源、权限、空间或已付关系代价>"
```

三个语义字段必须存在且为 list；没有可归因内容时显式写 `[]`。不写注释、`pending` 或用作者猜测填空。

### 按故事时点选取来源

当前有效正文指本轮已落入 `pipeline/scenes/scene_{id}.md` 的当前版本；按既有失败 / 回滚状态排除失效版本，不等待后续统一 scene-review，也不另加接受标记。先由本场 `location_time` 及既有因果关系确定故事时点。scene_id 与呈现次序不证明事件先后；倒叙场景不能继承已写未来场景中的知识。state.md 是已有状态资料，不保证已包含跨场变化；draft_tail 只承载相邻正文片段。相关事实有缺口时，按人物亲历、转述或其他已成立的获知渠道回读相关当前有效正文，避免统一全文回读。来源仍不足时省略该项，不把后续设计补成已知。

### 认知切片纪律

- `known_now` 只收录角色 package、当前 state 或已经发生正文能够支持的事实、承诺与关系认知。`phase2_character.yaml` 不进入本 agent 输入；作者侧的“不自觉欲望”“核心缺陷”、`end_state` 和人物轨迹机制留在设计链。
- `observable_stimuli` 每项只含本文件内唯一的 `id` 与刺激的可感表面 `cue`。对手私密目的、作者对事件的解释、离场结果、reader task、omission、irreversible action 与预定解法不进入 role_view。
- `constraints_now` 只写人物意志之外、角色能够感觉或已经知道、并且此刻实际缩小可行动范围的条件：伤势、剩余时间、资源缺口、门禁权限、空间封锁、已经付出的关系代价等。
- 信念、伦理判断、表达策略、职业程序和设计期待分别留在人物资产、`known_now` 或 actor 的当场判断中，不编成限制。已经作出的承诺可以作为 `known_now` 事实；是否履行、怎样履行由角色本人决定。
- 判别例：`右腕骨折，无法举枪`、`警报三分钟后封门`、`只有对手持有通行证`会改变可选行动；`必须保护孩子`、`应当如实报告`、`按原文回答`提前规定了人物答案，不进入 `constraints_now`。
- 使用白名单语义：未写入 role_view 的场景事实不向 actor 开放。不要用“角色不知道……”列出秘密；列出秘密本身会泄漏信息。
- 事实切片保持具体。职业、性格和主题标签不能替代人物已经经历过什么、眼前实际发生什么。

## 执行步骤

1. 读 `pipeline/phase5_scenes.yaml`，定位 `sequence_expansions[].scenes[]` 中 `scene_id == {当前 scene_id}` 的 scene_card，提取 `participants` 与本场事实；完整设计只供本 agent 判断哪些表面届时对当前角色可见，不原样下发
2. 对每个 participant，遍历角色 `build-meta.yaml` 的 `character_slug / character_display_name` 完成 slug 对齐；映射不存在或不唯一时失败退出，不猜 slug
3. 对每个已对齐的 participant slug：
   - 读 `pipeline/story-character-skills/.claude/skills/{slug}/build-meta.yaml`，确认 `character_display_name`
   - 读 `pipeline/story-character-skills/.claude/skills/{slug}/SKILL.md`（run 级角色资产文件，非 skill 入口加载）
   - 试读 `pipeline/story-character-skills/.claude/skills/{slug}/state.md`（缺则只用角色 package 中已经成立的内容）
   - 试读 `pipeline/scene_{前一场景 id}/draft_tail.md`；核对其故事时点。state / tail 存在相关知识或约束缺口时，沿现有时空与因果线索读取 `pipeline/scenes/scene_{id}.md` 中相关当前有效正文，只采用本角色在本场时点前已获知的事实
   - 从上述来源筛出 `known_now`
   - 从 scene_card 筛出该角色届时可感的 `observable_stimuli`；只保留动作、话语、声音、物件或环境变化的表面，并为每项分配本文件内唯一的 `cue_*` id
   - 从来源筛出角色可感、且实际缩小本场行动集合的 `constraints_now`；删除伦理答案、表达策略与程序指令
   - 写 `pipeline/scene_{scene_id}/role_views/{slug}.yaml`
4. 确认 participants 对应的逐角色文件全部写毕；不生成 aggregate role brief

## 完成信号

全部文件写毕后回复：

```
done role_view for scene {scene_id}
```

## 不做清单

- 不产正文 / 叙事 / 对白
- 不替角色决定本场目标、论证过程、行动或表达
- 不把 scene_card 的离场结果、读者任务、作者省略与对手私密目的下发给 actor
- 不调其他 skill（不借 character-persona 等）
- 不改写 Phase 2 / Phase 5 文件
- 不创建 `scene_{scene_id}/` 以外的目录

## 不读

- `pipeline/phase2_character.yaml`（作者侧人物诊断、弧光与终点；本 agent 只消费编译后的 actor-facing package）
- `pipeline/characters/{中文角色名}.md`（adapter，build-time 校验视图；slug→display_name 反查走 `build-meta.yaml.character_display_name`）
