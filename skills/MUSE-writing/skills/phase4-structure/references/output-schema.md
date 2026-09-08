# Phase 4 输出 Schema

交付物文件：`pipeline/phase4_structure.yaml`

```yaml
arc_expansions:
  - arc_id: ARC-1
    sequences:
      - seq_id: ARC1-SEQ1
        name: "序列名称"
        core_conflict: "这个序列的核心冲突（**也是序列尺度的读者追问**——读者跟住这个冲突读完整段）"
        escalation_direction: "冲突从哪递进到哪（**= 读者在本序列被带向什么方向**）"
        sequence_climax: "序列高潮（哪个事件是顶点）"
        closed: "这个序列闭合了什么（**= 读者本段获得什么答案**）"
        opened: "本段留下的后续条件、问题或收束结果；终局可为空字符串"
    arc_progression_note: "此 Arc 内序列之间的递进逻辑（可选）"

causal_chain: "事件之间的实际因果依赖；可与序列呈现顺序不同"

narrative_threads:                     # optional；两条以上持续叙事线且 Phase 5 需要区分时填写
  - line_id: LINE-01
    description: "这条线由谁或什么问题推动"
    sequence_refs: [ARC1-SEQ1, ARC2-SEQ2]
```

## 字段说明

| 字段 | 必需 | 下游使用 |
|------|------|---------|
| `arc_expansions[].arc_id` | 是 | Phase 5（按 Arc 组织场景） |
| `arc_expansions[].sequences[].seq_id` | 是 | Phase 5（按序列展开场景） |
| `arc_expansions[].sequences[].core_conflict` | 是 | Phase 5（序列内场景的冲突围绕此展开） |
| `arc_expansions[].sequences[].sequence_climax` | 是 | Phase 5（标识序列高潮场景，触发 beat_direction 标注） |
| `arc_expansions[].sequences[].closed/opened` | 是 | Phase 5（验证序列间衔接） |
| `causal_chain` | 是 | Phase 5（验证场景间因果）、Phase 7（因果链修订） |
| `narrative_threads[].line_id/description/sequence_refs` | 否 | Phase 5（真实多线时定位当前序列相关线）；单线故事或下游无需区分时省略 |

## 序列节拍判据

`sequence_climax` 需要改变后续行动、解释、母题意义或选择空间。`escalation_direction` 描述困境性质、代价、不可逆性、信息状态或选择空间怎样变化；外部声量可以下降。

`closed/opened` 记录局部答案和它产生的新条件。终局序列按 Phase 3 `story_climax_design.resolution` 收束，无需制造额外 handoff。

`narrative_threads` 只提供下游定位。跨线影响写入相关序列的转折与 `causal_chain`，不增加第二套交叉表。`LINE-*` 与伏笔台账的 `thread_id` 分属不同命名空间。
