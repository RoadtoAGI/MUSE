# 对白事件 schema

本文件是作品内 `dialogue/events/scene_{scene_id}.yaml` 的字段权威。

```yaml
schema_version: dialogue-scene-events/v1
work_id: novel:作品目录名
scene_id: S01
scene_file: scenes/scene_01.md
events:
  - event_id: novel:作品目录名:S01:e01
    event_type: interaction       # interaction | group_exchange | monologue | soliloquy
    context:
      relationship: peer
      power: symmetric
      intimacy: familiar
      face_condition: private
      pressure: concealment
      shared_context: 双方已经知道且无需复述的事实
      immediate_stakes: 本轮要改变的现场结果
    participants:
      - character_id: novel:作品目录名:role-a
        display_name: 角色甲
        position: initiator
        knowledge_boundary: 只写场景可证实的知识边界
      - character_id: novel:作品目录名:role-b
        display_name: 角色乙
        position: respondent
    turns:
      - turn_id: t01
        speaker_id: novel:作品目录名:role-a
        speaker_label: 角色甲
        addressee_ids: [novel:作品目录名:role-b]
        response_to: null
        source_locator: scenes/scene_01.md:L8-L9
        text: 原文中的实际台词
        speech_action: probe
        cooperation: indirect
        oral_forms: [omission]
        capacity: strained
    outcome:
      control_shift: initiator_keeps_control
      relationship_cost: low
      visible_result: 原文可观察到的本轮结果
    transferable_mechanism: 用一句话说明可迁移的交互机制，不总结主题
    annotation:
      extractor: dialogue-kb-distill
      confidence: 0.9
      review_status: source_checked
      source_file: scenes/scene_01.md
      source_sha256: 完整文件的 sha256
```

## 字段约束

- `work_id`：`novel:{目录名}` 或 `drama:{目录名}`；
- `event_id`：作品内唯一，推荐 `{work_id}:{scene_id}:eNN`；
- `character_id`：作品内稳定 ID。匿名说话者使用 `guard-02`、`crowd-voice-01` 一类稳定 slug；
- `source_locator`：相对作品目录，格式 `path:Lstart-Lend`；
- `text`：与 locator 窗口中的原文一致，保留解释本轮回应所需的原文；原文仍是最终权威；
- `response_to`：只指向本事件中更早的 turn；
- `addressee_ids`：已知接收者引用本事件 participants；未明确接收者时可为空，不猜测归属；
- `context`：使用可扩展词表。现有词表不能准确表达时写 `other`，并增加同级 `*_note`；
- `annotation.review_status`：`candidate | source_checked | reviewed | disputed`。

## 运行时准入

默认检索 `interaction` 和 `group_exchange`，并使用 `source_checked`、`reviewed` 事件。调用方明确需要独白时再纳入 `monologue` 或 `soliloquy`。`candidate` 留在知识库等待复核，不作为高权重 few-shot。
