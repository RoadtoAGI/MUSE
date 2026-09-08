---
name: macduff
description: 麦克达夫（Macduff） — 知识库参考角色，仅供加载，不扮演
version: 1
allowed-tools: Read
---

# 麦克达夫（Macduff）

## 身份与处境

11 世纪苏格兰菲夫领主、邓肯王的近臣。在剧中他从未追求王位，他被卷入的方式完全是被动的——A2S3 他奉命叫醒邓肯，因此成为首位发现弑君的人；A2S4 他拒绝赴 Scone 参加 Macbeth 的加冕；A4S2 他离开妻儿赴英求援，导致全家被屠杀；A5S7 他亲手为家人复仇，斩下 Macbeth 之首。他不是一个想成为英雄的人，他只是在每个关键节点都做了那个不肯说谎的选择——而这些选择的代价由他和他的家人共同承担。

来源：phase2_roles.yaml → roles.macduff.dramatic_role / status_arc
佐证：
- scenes/scene_A2S3.md:L161-L182（首位发现弑君："O, horror, horror, horror! / Tongue nor heart cannot conceive nor name thee!"）
- scenes/scene_A2S4.md:L57-L67（公开拒绝赴 Scone：No, cousin, I'll to Fife）
- scenes/scene_A5S7.md:L99-L113（终战亲手追击 Macbeth：Tyrant, show thy face）

## 核心欲望

- **自觉欲望**：让苏格兰从篡位者手中解放出来（A4S3 多次称 Macbeth 为 tyrant）；A4S2 之后增加了亲手为家人复仇的私人欲望
- **不自觉欲望**：在不撒谎的前提下继续作为一个人活着——他能不能在政治、家庭、复仇三个领域同时不背叛自己的本性
- **核心缺陷**：他对"自己的诚实"过于信赖，以致在 A4S2 抛下妻儿赴英时没有充分估算这是把家人变成谋杀目标的等价行为——Lady Macduff "he wants the natural touch" 是剧中对他最狠的判语，且这判语来自他妻子的口

来源：phase2_roles.yaml → roles.macduff.desire / obstacle
佐证：
- scenes/scene_A4S3.md:L519-L533（"All my pretty ones? ... I must also feel it as a man" — 私人复仇欲望首次完整出场）
- scenes/scene_A4S2.md:L23-L40（Lady Macduff："Wisdom? To leave his wife, to leave his babes" + "he wants the natural touch"）
- scenes/scene_A4S3.md:L249-L260（Macduff 听到"Fit to govern? No, not to live" — 用绝对句承担政治诚实的代价）

## 性格真相

- **外在塑造**：忠诚、寡言、不擅政治表演的硬派 thane；在朝廷中以缺席为表达
- **压力下的真实反应**：A2S3 发现弑君时他的反应是高声召唤所有人 + 拒绝详细描述（"Do not bid me speak: / See, and then speak yourselves"），他不试图主导现场；A4S3 被 Malcolm 用自我诋毁测试时，他先承担听者的痛苦，然后用最简洁的句子作判断（"Fit to govern? No, not to live"）；A4S3 听到家人被杀的消息时他不立刻接受 Malcolm 的"convert to anger"建议，而是坚持先以"a man"的身份悲恸（"I must also feel it as a man"）——他对自己情感的诚实优先于政治效率
- **裂隙**：他坚持"不撒谎"的代价由他的妻儿承担。这个裂隙剧本没有让他自己说出来，但他的"He has no children"（一句指 Malcolm）暗示他意识到了，但他没有展开

来源：phase2_roles.yaml → roles.macduff.status_arc / voice_function
佐证：
- scenes/scene_A2S3.md:L161-L190（"O horror" + "Do not bid me speak"）
- scenes/scene_A4S3.md:L237-L249（"Fit to govern? No, not to live"）
- scenes/scene_A4S3.md:L513-L533（"He has no children" + "But I must also feel it as a man"）

## 声音框架

朴素的五步抑扬格，少抽象名词、少假设从句、少比喻 - 倾向直陈句和重复（"All my pretty ones? / Did you say all?"——重复不是修辞，是承受信息的速度）。他几乎从不长篇独白——他的声音在与他人对话时最清楚，在他独自占场时反而最沉默。当他必须做判断时他用最短的判决式句子（"Fit to govern? No, not to live"；"Despair thy charm"；"Turn, hell-hound, turn"），把整段思考压缩到一个动词或者一个否决。他的语言永远低于他承受的情感量级——这与 Macbeth 永远高于他承受的语言量级形成完整对比。

来源：phase2_roles.yaml → roles.macduff.voice_signature
佐证：
- scenes/scene_A4S3.md:L237-L249（"Fit to govern? No, not to live" — 判决式短句）
- scenes/scene_A4S3.md:L513-L533（"All my pretty ones? Did you say all?" — 重复承载信息）
- scenes/scene_A5S7.md:L99-L113（"Turn, hell-hound, turn" + "I have no words: / My voice is in my sword" — 把判决压缩到动词或动作）

## 边界（Layer 0 硬规则）

- 不会赴 Macbeth 加冕的 Scone——A2S4 他在 Ross 面前直接拒绝；A3S6 由 Lennox 之外的 Lord 证实他已离开苏格兰；他用缺席表达政治立场，不靠口头宣告 ← 佐证：scenes/scene_A2S4.md:L57-L73 + scenes/scene_A3S6.md:L57-L80
- 不会为了政治效率压抑哀悼——A4S3 Malcolm 对他说"Dispute it like a man"时他拒绝立刻把悲痛兑换为愤怒，他坚持先"feel it as a man"再"do so" ← 佐证：scenes/scene_A4S3.md:L525-L533
- 不会向篡位者下跪 / 谈判——A5S7 见到 Macbeth 后他直接说"I have no words: / My voice is in my sword"；终战 Macbeth 主动表示"my soul is too much charged / With blood of thine already"求他退让，他拒绝 ← 佐证：scenes/scene_A5S7.md:L107-L113
- 不会让自己被任何超自然 / 命运式语言说服——A5S7 Macbeth 自称 charmèd life 时他立刻反击"Despair thy charm"，用一个具体的、可解读的事实（自己是剖腹产）瓦解 Macbeth 的形而上自我保护 ← 佐证：scenes/scene_A5S7.md:L121-L135
- 不会主动承认自己抛弃家人的代价——A4S3 听到家人被杀的消息他说"Sinful Macduff, / They were all struck for thee!"——他承认是自己的过错（"for mine"），但接下来立刻把这种承认转化为复仇动力，不展开为"我是不是不该走"。剧本不让他真正消化 Lady Macduff 在 A4S2 对他的判语 ← 佐证：scenes/scene_A4S3.md:L527-L535（"Naught that I am ... Fell slaughter on their souls"）

来源：phase2_roles.yaml → roles.macduff.dramatic_role / status_arc

## 弧光（已完成）

- **起点**：忠诚但寡言的领主，以缺席表达不满，相信只要自己不参与篡位政权就能保持"诚实"——一种相对廉价的政治姿态
- **终点**：在亲手为家人复仇并献上 Macbeth 首级后获得"the time is free"的政治宣告权，但同时也承受了用妻儿性命换来的复仇——他从一个相信"不参与即清白"的人，变成一个知道"诚实的代价由他人共付"的人
- **核心转变**：从一个被动的"不站队者"变成一个主动的、必须用最具体行动收回所有失去之物的执行者；从相信"我可以只通过缺席表达立场"，变成必须用一把剑当面说话的人
- **关键转折点**：
  - A2S3 首位发现弑君——成为剧中唯一在场公开承认"this is murder"的人（scenes/scene_A2S3.md:L161-L190）
  - A4S3 通过 Malcolm 自我诋毁测试——确认效忠对象，并在测试中暴露他"绝对句"式的判断方式（scenes/scene_A4S3.md:L237-L260）
  - A4S3 接到 Ross 关于 Fife 屠杀的消息——私人复仇欲望覆盖政治效忠成为主驱动力（scenes/scene_A4S3.md:L505-L533）
  - A5S7 揭示自己是剖腹产 + 斩下 Macbeth 首级 + 持首呼"Hail, King of Scotland"——三步连续动作完成弧光（scenes/scene_A5S7.md:L121-L143 + L233-L245）

来源：phase2_roles.yaml → roles.macduff.status_arc

> 弧光为内在转变；Macduff 在剧末活到加冕场景，无 canon-ending.md 附件。
