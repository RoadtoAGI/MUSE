# Phase 4 输出 Schema

交付物文件：`pipeline/phase4_structure.yaml`

```yaml
arc_expansions:
  - arc_id: ARC-1
    sequences:
      - seq_id: ARC1-SEQ1
        name: "序列名称"
        core_conflict: "组织本序列的追求与阻力、待解信息关系或母题联系"
        escalation_direction: "局面、解释或母题意义从何处发展到何处"
        sequence_climax: "序列高潮（哪个事件是顶点）"
        closed: "本段形成的阶段成果、认识、关系状态或已解问题"
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
| `arc_expansions[].sequences[].core_conflict` | 是 | Phase 5（围绕本序列的冲突或组织关系安排场景，语义见下方判据） |
| `arc_expansions[].sequences[].sequence_climax` | 是 | Phase 5（标识序列高潮场景，触发 beat_direction 标注） |
| `arc_expansions[].sequences[].closed/opened` | 是 | Phase 5（验证序列间衔接） |
| `causal_chain` | 是 | Phase 5（验证场景间因果）、Phase 7（因果链修订） |
| `narrative_threads[].line_id/description/sequence_refs` | 否 | Phase 5（真实多线时定位当前序列相关线）；单线故事或下游无需区分时省略 |

## 序列节拍判据

`core_conflict` 保留现有字段名：欲望组织时写追求与有效阻力，信息组织时写证据与待解问题的关系，母题组织时写将要展开、变形或对位的联系。按实际作用结合使用，无人物对抗时不补造对抗。

`sequence_climax` 需要改变后续行动、解释、母题意义或选择空间。`escalation_direction` 描述困境性质、代价、不可逆性、信息状态或选择空间怎样变化；外部声量可以下降。

`closed` 记录本段已经形成的阶段成果、认识、关系状态或已解问题；`opened` 说明这些结果使什么后续行动、追问或理解成为可能。阶段成果可以来自合作、学习与条件积累，完成标准也可随人物认识而深化。终局序列按 Phase 3 `story_climax_design.resolution` 收束，无需制造额外 handoff。

`narrative_threads` 只提供下游定位。跨线影响写入相关序列的转折与 `causal_chain`，不增加第二套交叉表。`LINE-*` 与伏笔台账的 `thread_id` 分属不同命名空间。
