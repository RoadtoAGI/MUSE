# A 组审查：微观语言 + 反 AI 化 + reframing 独白判读

> 本子文件承载 A 组审查中"句级 / 段级语言细节"的诊断规则：反 AI 化失守检查、微观语言错配（含 hot zone 判读、reader-visible damage 原则、修订方向）、以及 改变前文理解的独白判读。主表逐项检查见 [`A_aesthetic.md`](A_aesthetic.md)。口癖的四个机制与共同改法见 [`prose-craft/references/ai-cliche-patterns.md`](../../prose-craft/references/ai-cliche-patterns.md)。

## §1bis 反 AI 化失守检查（承载与视角语义模式）

下列两项是口癖模式库“说破”（`spelled_out`）在特定位置的表现，A 组逐场景扫描：

| 检测项 | 触发场景 | 报告落点（`dimension: ai_pattern` + subkind） |
|---|---|---|
| 叙述者过度自省 | 第一人称叙述场景，叙述者在道德灰区，替读者宣布自己认识到了什么 | `subkind: narrator_self_corrects` |
| carrier 后重复命名情绪 | 命名只复述已成立的认识，不改变人物的自知或关系 | `subkind: emotion_naming_under_face_loss` |

每条 finding 需要 `evidence_quote` 原句和一句机制级失败原因；表面词或题材类型不单独构成立案。修订方向按口癖的改法：先删，删后缺了人物此刻必要的认识再压进相邻句。

## §7 微观语言错配

扫描单句级"看似有文气但不成立"的问题。命中时 `dimension: micro_language`，并填 `subkind`：

| subkind | 判据 | 例 |
|---|---|---|
| `false_literary_diction` | 修饰语与被修饰动作不搭，句子只剩假文气 | "人群退得极轻" |
| `sensory_mismatch` | 感官通道错接，触/听/视觉强度混用且无转换 | "那一退极轻，却刺眼" |
| `abstract_judgment_without_action` | 抽象判断缺少理解依据，或复述已成立的意义；内心与叙述认识可独立成立 | "他显得复杂而沉重" |
| `stock_speech_tag` | 用库存语气标签（"淡淡道 / 声音不高 / 低声道 / 平静道 / 沉声道 / 悠悠道"等）替代角色实际语气、动作压力或对白本身——删后说话人仍能辨认、读者不少事实时报告 | "他淡淡道：「刀断了，人还在。」" / "杨过声音不高，「这条路给他退……」" |
| `weak_character_expression` | 人物声音 / 神情 / 动作 / 心理描写附近用弱否定、虚词、副词或状态标签替代具体动作、压力或对白效果——删后读者不少事实时报告。景物或物件作主语（"册页翻动的声音""门没开"）、否定用来纠正事实或反驳对方（"公审是今夜，不是明晨"）的句子不在此列 | "声音仍平" / "表情没有变化" / "脚步不慢" / "她只是看着" / "不是问句" |

这两项（`stock_speech_tag`、`weak_character_expression`）是口癖模式库“填充”的具体形态。每条 finding 必须给 `evidence_quote` 原句和一句失败原因，方便 scene-reviewer 直接转 patch。

**`stock_speech_tag` 与 dialogue_lint S3 信号联动**：dialogue_lint S3 已加 `STOCK_SPEECH_TAG` 正则信号（同名 enum，confidence=medium），A 组消费 lint hits 时按上表判据核对；说话人要靠这个标签才能辨认时不在此列。

**`weak_character_expression` 与 dialogue_lint S3 信号联动**：dialogue_lint S3 的 `weak_character_expression_candidate` 是 observe 候选，按上表判据核对。candidate 分两档：

- **confidence=medium**——有锚点（声音/神情/动作/心中等身体部位或感官名词），如"声音仍平 / 表情没有变化 / 脚步不慢 / 心中仍想"
- **confidence=low**——仅代词锚点（"他/她 + 弱副词 + 弱动词"），宽召回兜底

每条 candidate 还附 `near_dialogue: bool`——命中行 ± 2 行内是否有对白引号。

**Hot zone 加权（near_dialogue=true）**：人物对白前后 1-2 行是 weak_character_expression 高发区——典型场景：

- 对白前后引导句："她声音平" / "他低声道" / "声音短硬"
- 同一人物连续两句对白之间的垫句："她没有动" / "神色不变" / "只是看着"
- 对白后补态度："不是问句" / "语气淡淡" / "话里没有怒气"

常见失效是状态标签反复提供同一含义，掩盖实际话轮或关系变化。

### 判读流程

这里的判读只用于 dialogue_lint 的 observe 候选与 A 组自己读出的句子。`ai_filler` 报告里 `per_sentence: true` 的逐句命中（如 `echo_negation`）直接记 finding，不走本流程；observe 的 `body_closeup_filler`、`silence_pause_cliche` 命中同样按下面的问题判。

判定时问：**删去这句，读者少了什么事实？** 少了具体的事——人物没喝那杯茶、转身走了、说话人换了——就不是填充；只少一种口气、气氛或节奏，就报。例："接过茶，却没饮，望着远去的背影"里“却没饮”交出了人物没喝这件事，不报；"她说完，屋里没人接话，灯芯爆了一下"里“灯芯爆了一下”删去后问答照样承接，报。

**报**：

- **库存语气标签**：相关词面代替应有的语气差异，删后说话人仍能辨认；后续是否接动作不决定是否报
- **抽象状态替代具体反应**："声音仍平 / 表情没有变化 / 不是问句 / 没有起伏"
- **同义堆叠**：几处成分交代同一状态；“很轻／几乎听不见／像是在自语”分别交代了音量、听者能否听见和交流对象时，各自是事实，按语境判断

删去后句意残缺的（如删掉唯一的说话人归属），压进相邻句，不留原句。

### 修订方向（写进 finding 的 `suggestion`）

建议说明问题句是哪一种机制、删后要保住哪件事实。修订按口癖的改法：先删；缺了归属或衔接再压进相邻句；不把状态标签换成一个动作或另一个标签，那是同一功能换了说法；中性说话标记“说、问”照用。复读新旧上下文，确认原问题消失、理解完整；同义替换和计数下降各自不足以证明完成。

## §reframing 独白判读

独白可以通过新事实、立场或经验改变读者对前文的理解。按受审正文独立判断：它增加了什么，如何影响人物、关系或事件的意义；设计只辅助解释意图。长篇幅、低动作密度、结尾接对白或继续叙事，都不能单独推出注水。

例如，同一段撤退往事从“懦弱”改读为“保护同伴”，关键在于新增事实改变了对选择的理解；若只是换词重复已经确立的评价，就是说破。迁移的是信息与解释的变化，不要求复制往事独白或特定收尾。

独白交出了新事实或改变了理解，照写。只换词重复已成立的意思时，finding 引用原文、说明重复了哪一处，写 `dimension: ai_pattern, subkind: monologue_padding`，修订按口癖的改法删或压。A 不读取 reader 报告；修订者按本次合并反馈核实处置。
