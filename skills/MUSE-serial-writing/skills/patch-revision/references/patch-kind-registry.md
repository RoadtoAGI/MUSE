# 定点修订方向

patch_kind 为当前补丁的方向标签，具体动作服从其问题、授权范围和保留项。标签不替代语义判断，不决定整场重写；旧类别按当前实际问题解释。

| patch_kind | 适用条件与方向 |
|---|---|
| delete_token / replace_phrase | 局部字词冗余或错配；删除或替换后保留信息、声音与指代 |
| carrier_then_explain | 后文只重复前文已成立的意义；删合重复，保留真正新增的信息或态度 |
| omission_violated / omission_filled_in | 有效作者约束要求保留信息缺口；修正越界揭示，保留理解当前事件所需内容 |
| narrator_self_corrects | 当前句使叙述者获得不应有的认知或破坏已确定的不可靠结构；按实际权限修复，自我反省本身合法 |
| emotion_naming_under_face_loss | 情绪命名与所需作用冲突或只是重复；可删合或改写，直接命名情绪本身合法 |
| care_tone_violence_dropped | 明确采用的言行反差因多余标签被抹平；恢复该关系，不要求施害者一律温柔 |
| rewrite_sentence | 在确定句内重组表达，保留事实与功能 |
| rewrite_span | 在 old_span 确定的连续片段内重组；跨出范围先回调用方调整授权 |

既有 `epic_death_facing`、`mirror_loosened`、`carrier_missing`、`narrator_distance_global_drift` 记录分别可能涉及事件、结构、承载作用或叙述权限。先辨明实际问题；若授权局部修订足以解决则可处理，需要重写因果或全场实现时回 scene-review 决定 ROLLBACK/REWRITE。死亡方向、临终字数、镜像数量和沉默结尾都不由类别名规定。
