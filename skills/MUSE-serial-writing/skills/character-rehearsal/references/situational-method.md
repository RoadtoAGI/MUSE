# 连载角色行动候选

## 取得本人输入

orchestrator 向本包 `serial-character-actor` 提供 `{work_dir, scene_id, role_slug}`，明确 `mode: role_move`。actor 读取 `pipeline/scene_{scene_id}/role_views/{role_slug}.yaml`；路径相对章 `work_dir`，其中 `character` 必须与 dispatch 的绑定一致。

view 已包含本人合时的人物依据与本场信息。actor 不读取完整 scene_card、serial_context、其他人物 view、共享人物包、state、作者设计、其他场景正文或聚合角色材料。view 缺失、身份错配或明显自相矛盾时，回复具体输入问题，由 orchestrator 交还派生器；不扩大读取来猜测完整剧情。

## 人物如何形成选择

先以 `character_basis` 中此时的经历、追求、信念、声音和盲区理解自己，再用 `known_now` 与现场可感信息理解局面。人物可以误判，其误判应有本人所见、所信的依据。作者侧诊断、未来终点和对手内心不会自动成为人物的认识。

`observable_stimuli` 是可选择的现场证据；数个 cue 可能共同促成一个选择。带条件的 cue 只有在条件发生后才可触发候选，不能提前把它当作已发生事实。人物也可基于已有追求、承诺或认识主动行动，不必等每个 cue 都获得回应。

每个保留的候选应体现人物已有前提如何改变其对现场的解释与行动：人物想让场内的人或局面发生什么，愿为此付什么代价，对方能听懂哪些信息。这些判断用于形成候选，完整推演过程不落盘；`meaning` 仅保留让 writer 理解此选择的简短人物依据。

- 对白以场内接收者为对象，能够实施试探、说服、威胁、隐瞒、坦白、安抚、拒答或退出。自言自语服务人物自己的整理、质问或说服。
- 动作、对白、沉默和身体反应可以共同完成一次选择，合在一个 move；不拆成多项同义解释。
- 有表达代价、隐瞒或盲区时，让言行之间留出可推断间距；明确的请求、报告和坦白可以直说。不会因出现“我害怕”“我爱你”等词句就强制改写或重跑。
- 比较换成另一名处境相同的称职角色是否仍会给出相同的程序性回应。若人物经历、关系或信念没有改变选择，通常由 writer 直接完成，无需占用候选。

例如，两人都看见门锁损坏。普通的“换锁”建议可由 writer 补全；曾被同伴关在门外的人要求保留从里面徒手打开的办法，其经历改变了他关注的风险，才形成有用的人物候选。该机制适用于经历改变解释或代价权衡的情境，不规定角色必须回忆创伤或反对安全措施。

## 形成与交付

按[输出 schema](output-schema.md)写 `pipeline/staging/scene_{scene_id}/{role_slug}_role_move.yaml`。写入前核对本人绑定、cue 引用和知识来源，删去逐 cue 复述、同义候选及对作者预定结果的解释。没有有用候选时写 `moves: []`，不强加表演。

`move` 是人物可能实施的候选，writer 保留取舍权；`intended_effect` 只写人物所期待的即时效果，不保证世界或其他人物会配合。遇到可定位的问题只修受影响候选，不为语气、字数或固定栏目进行整组重试。

完成回复 `done role_move for scene {scene_id} character {role_slug}`。输入不足时回复 `role_move unavailable for scene {scene_id} character {role_slug}` 并给出原因；orchestrator 可在 view 可用时直接让 writer 写作，涉及 view 本身错误则先修该输入。原始问答和推演过程不单独存档。
