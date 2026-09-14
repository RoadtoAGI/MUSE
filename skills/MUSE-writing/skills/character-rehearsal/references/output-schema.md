# role_move 产物 schema

本文件是 Phase 6 role_move 产物的**唯一权威 schema**。

## Phase 6 role_move

产出路径：`pipeline/staging/scene_{scene_id}/{slug}_role_move.yaml`。每个文件只属于一个角色。

Actor 按以下 schema 产出，orchestrator 不做二次提取，writer 按需消费：

```yaml
character: <slug>
moves:
  - "on": cue_1  # 可选：仅在回应 observable cue 时写；主动发起时省略
    meaning: <该刺激在人物已有前提下意味着什么>
    move: <角色的一次言语、身体或心理行动，含有作用的沉默或自然组合>
    intended_effect: <角色希望对方、现场或自己的态度、预期、理解发生的即时变化>
```

字段值中文，key 英文。`"on"` 为可选字段：回应现场刺激时引用对应 cue；人物依据已有承诺、当前目标或已知事实主动发起行动时省略，不为填字段虚构刺激。写入时保持引号，避免 YAML 1.1 消费者将它解析为布尔值。`moves: []` 是完整产物，表示当前没有角色独有且能改变 writer 实现选择的候选。

**slug** = 角色的 `role_slug`，与 `pipeline/story-character-skills/.claude/skills/{slug}/`、`pipeline/scene_{scene_id}/role_views/{slug}.yaml` 对齐；中文名到 slug 的映射由 character-persona `build-meta.yaml` 落定。

## 生产纪律

1. **角色独立推导**：Actor 根据长期经历、当前 state 和 role_view 的刺激决定怎样理解与回应；role_view 不提供目标答案。
2. **一个选择只写一次**：言语、身体与心理行动可以在同一 `move` 中自然组合；心理行动也可只在内心完成，不把同一选择拆成 decision / action / line / reaction / tell 多栏复述。
3. **刺激是证据池**：`observable_stimuli` 供角色选择与归并，不是逐项回应清单。多个刺激共同促成一次选择时写成一个 move，`on` 只锚定最直接的 cue；主动发起时省略 `on`。
4. **行动可归因**：`meaning` 从人物已有承诺、当前目标、`known_now`、真实 `constraints_now` 或长期人物资产推出选择。该前提须能把本角色的候选与任意称职角色都会做的通用反应区分开；只有职业流程或常识即可推出的动作交给 writer。
5. **解释属于人物**：`meaning` 用人物已有经历、信念与盲区给出简短因果依据；容纳误判，不输出分析报告或长篇思维过程。
6. **效果属于角色**：`intended_effect` 写角色希望当下促成什么，包括稳住或修正自己的理解；它不保证实际结果，也不写作者对人物弧光、潜意识或主题的解释。
7. **候选保持稀疏**：只有能够改变 writer 对角色行动、对白或心理表达的选择时才写；普通补全、同义改写和无独特人物依据的反应省略。候选数量由独立选择决定，不设固定上限或最低数量。

落盘前 self-check 全项见 `situational-method.md`。
