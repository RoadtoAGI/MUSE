# 剧本场次契约

`pipeline/screenplay/sequence_list.yaml` 的 `sequences` 列表决定呈现与拼接顺序。每项对应一个独立场次文件；场次长度与拆分取决于时空、行动及表演组织。

```yaml
sequences:
  - seq_id: SEQ01
    location: 候船室
    time: 末班船离港前
    characters_in_scene: [林, 周]
    dramatic_purpose: |
      周已决定离开，林仍相信关系能维持。通知停航后，两人必须面对
      今夜共同滞留的处境；离开的决定尚未撤回。通知怎样进入场面由写作决定。
    inspiration_refs: []
```

| 字段 | 契约 |
|---|---|
| `seq_id` | run 内唯一的文件键，仅用字母、数字、连字符、下划线；编号不承担排序 |
| `location / time` | 非空文字，说明场内时空；抽象空间、记忆或并置时间照实写。影视场头按媒介使用 INT./EXT.，舞台等无需套用 |
| `characters_in_scene` | Phase 2 角色名列表；无人出场的环境、声音或转场段可为空 |
| `dramatic_purpose` | 本场的处境、冲突或表达作用，以及后续真正依赖的结果；与上游关系和知识条件衔接，保留写作选择空间 |
| `act / scene` | 目标剧本实际分幕分场时填写，整数或非空标签；独幕、连续或实验结构可省略 |
| `arc_position` | 需要说明结构位置时用非空文字描述，允许省略 |
| `inspiration_refs` | 可选 INS-* 字符串列表，仅引用 ledger 中 accepted / bound 的采用项 |

Phase 4 的 Arc 与序列提供故事组织；展开为场次时保留必要因果、人物轨迹及表达意图。幕号按实际演出或剧本组织决定。必要的观察范围、隐藏信息或接续条件直接写进本场 `dramatic_purpose`，详尽人物依据仍从上游读取。

写完后执行入口中的 `validate_screenplay_phase5.py`。它检查类型、文件键、必需内容与 ledger 外键；创作依赖、媒介适配和目的是否成立由设计检查判断。
