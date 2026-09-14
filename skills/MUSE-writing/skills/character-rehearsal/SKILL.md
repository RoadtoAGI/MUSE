---
name: character-rehearsal
description: 为原创场景中尚未确定的角色判断生成可选 role_move，由场景编排按需派发；每次依据一个角色的认知切片排练。
---

# 角色排练

麦基《故事》第五章以压力下的选择解释人物性格。排练让人物的经历、欲望、关系与盲区参与具体选择；产物是 writer 可选用、改写或舍弃的候选。

调用方已确认需要排练后，使用 `character-actor` 或宿主可用的独立执行者，明确本包技能、work_dir、scene_id、role_slug 和本次有效对白参考路径或“无”。每次仅处理一个角色。加载[生产方法](references/situational-method.md)和[输出契约](references/output-schema.md)。

必需输入是本人 `pipeline/scene_{scene_id}/role_views/{role_slug}.yaml`；本人 package/state 补充长期依据，按当前故事时点解释。对白参考仅在本次明确选中且 MATCH 时使用。缺 role_view 或存在无法解释的事实冲突时返回具体输入问题，由派生者补正；没有有用候选时正常写 `moves: []`。

输出 `pipeline/staging/scene_{scene_id}/{role_slug}_role_move.yaml`，返回路径与完成状态。writer 只采用本次授权的 moves；独立选择已有充分依据时可直接写作。
