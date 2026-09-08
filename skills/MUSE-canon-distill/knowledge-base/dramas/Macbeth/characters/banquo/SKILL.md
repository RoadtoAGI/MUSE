---
name: banquo
description: 班柯（Banquo） — 知识库参考角色，仅供加载，不扮演
version: 1
allowed-tools: Read
---

# 班柯（Banquo）

## 身份与处境

11 世纪苏格兰 thane、Macbeth 在战场上并肩作战的同袍，剧本开场时与 Macbeth 并称邓肯的"双柱"（"our captains, Macbeth and Banquo"）。A1S3 与 Macbeth 同时遇见三女巫，他得到的预言与 Macbeth 互补：他自己不会成王，但他的后裔将世代为王（"Thou shalt get kings, though thou be none"）。这一预言把他变成两件事——他是 Macbeth 一生的镜面（同样被预言、不同选择），也是 Macbeth 政权的结构性威胁（如果预言为真，Macbeth 杀邓肯的所有努力都将归 Banquo 的子孙）。他在剧的前三分之一以活人的身份出场，在 A3S3 被 Macbeth 派去的杀手杀死（其子 Fleance 逃脱），从 A3S4 起以幽灵 + A4S1 显灵中"持镜的第八代王"的形式继续在剧中行使戏剧功能。

来源：phase2_roles.yaml → roles.banquo.dramatic_role / status_arc
佐证：
- scenes/scene_A1S2.md:L80-L88（Duncan 称双柱：Dismayed not this our captains, Macbeth and Banquo?）
- scenes/scene_A1S3.md:L141-L160（女巫对 Banquo 的预言："Thou shalt get kings, though thou be none"）
- scenes/scene_A3S3.md:L66-L72（A3S3 中被杀，临死命 Fleance 逃 + 复仇）

## 核心欲望

- **自觉欲望**：在不出卖自己的诚实和忠诚的前提下，与预言共处——既不去推翻它，也不去主动加速它；A2S1 与 Macbeth 的对话中他明确表达"so I lose none / In seeking to augment it, but still keep / My bosom franchised and allegiance clear, / I shall be counselled"
- **不自觉欲望**：观察。他是剧中第一个怀疑女巫的人（A1S3"the instruments of darkness tell us truths, / Win us with honest trifles, to betray's / In deepest consequence"），他几乎不会自己启动行动，但他持续在看 Macbeth 怎么变
- **核心缺陷**：他相信"我自己保持清白就够了"，但他没有公开发声——A3S1 独白他已经明确认定"thou playedst most foully for't"，但他没有告诉任何人；他的沉默使 Macbeth 有了从容杀他的时间窗口

来源：phase2_roles.yaml → roles.banquo.desire / obstacle
佐证：
- scenes/scene_A2S1.md:L82-L89（"so I lose none ... my bosom franchised and allegiance clear"）
- scenes/scene_A1S3.md:L285-L300（怀疑女巫："the instruments of darkness tell us truths"）
- scenes/scene_A3S1.md:L9-L20（A3S1 独白：私下指认 Macbeth 弑君，但不公开行动）

## 性格真相

- **外在塑造**：可靠的副将、Macbeth 的同袍、邓肯信任的贵族；从不显得野心勃勃
- **压力下的真实反应**：A2S1 在 Macbeth 弑君前夜，他独自时坦承"cursèd thoughts that nature / Gives way to in repose"——他自己也有过对预言的非分之想，只是他祈求"merciful powers, restrain in me"，他不容许自己沿这个方向走第二步；A3S1 加冕后他单独时已经看清 Macbeth 是怎么得到王位的（"thou played'st most foully for't"），但他立刻把这个判断私下转向自己的预言（"may they not be my oracles as well, / And set me up in hope?"）——他的反应是从公共道德回撤到私人期望
- **裂隙**：他的"诚实"是私人的诚实，不是公共的诚实——他对自己说真话，但不对邓肯 / 朝廷说真话。这个裂隙是剧本对他的最严厉的暗讽——他成为 Macbeth 之后唯一公开存活但已知真相的人，却没有用这个真相做任何事

来源：phase2_roles.yaml → roles.banquo.status_arc / voice_function
佐证：
- scenes/scene_A2S1.md:L29-L36（"cursèd thoughts ... merciful powers, restrain in me"）
- scenes/scene_A3S1.md:L9-L20（私下知真相但不公开）
- scenes/scene_A1S3.md:L137-L144（"If you can look into the seeds of time" — 主动向女巫询问自己的部分，他不只是 Macbeth 的旁观者）

## 声音框架

冷静的五步抑扬格 + 偏好"时间 / 种子 / 树木 / 收获"这一组农事 - 时间隐喻（"seeds of time"，"if there come truth from them"，"thou hast it now"——以"现在"为锚点判断未来）。他几乎没有命令式 / 感叹式句子；他大多用条件从句和反问。在公开场合他比 Macbeth 更短小直接（A1S6 martlet 描述、A3S1 公开应答 Macbeth 的晚宴邀请），从不长篇大论。他的独白与 aside（A1S3 怀疑女巫 / A2S1 cursèd thoughts / A3S1 thou hast it now）都很短——他不是会被语言冲走的人，而是用语言反复检查自己的人。死后作为幽灵他没有台词，但在 A4S1"show of eight kings"中作为视觉物再次出现，承担"被预言确认"的最终视觉功能。

来源：phase2_roles.yaml → roles.banquo.voice_signature
佐证：
- scenes/scene_A1S3.md:L137-L144（seeds of time）
- scenes/scene_A2S1.md:L25-L36（A2S1 cursèd thoughts — 短独白）
- scenes/scene_A3S1.md:L9-L20（A3S1 thou hast it now — 短独白）

## 边界（Layer 0 硬规则）

- 不会主动协助任何形式的弑君 / 篡位——A2S1 他明确告诉 Macbeth"so I lose none / In seeking to augment it, but still keep / My bosom franchised and allegiance clear, / I shall be counselled"——他可以受咨询但不会出卖忠诚 ← 佐证：scenes/scene_A2S1.md:L82-L89
- 不会向 Macbeth 隐瞒他对女巫的怀疑——A1S3 他当场说出"the instruments of darkness tell us truths"，A2S1 他主动提起"I dreamt last night of the three weyard sisters"；他对 Macbeth 是公开记账的 ← 佐证：scenes/scene_A1S3.md:L285-L300 + scenes/scene_A2S1.md:L37-L45
- 不会向邓肯或朝廷公开他对 Macbeth 的怀疑——A3S1 私下已认定 Macbeth 弑君，但没有告诉任何人；这是他的边界但也是他的盲点，剧本不掩饰这一点 ← 佐证：scenes/scene_A3S1.md:L9-L20
- 不会舍弃 Fleance——A3S3 临死的两件事是"Fly, good Fleance, fly, fly, fly!"和"Thou mayst revenge"；他在最后一刻为儿子的逃生和未来的复仇创造可能 ← 佐证：scenes/scene_A3S3.md:L66-L72

来源：phase2_roles.yaml → roles.banquo.dramatic_role / status_arc

## 弧光（已完成）

- **起点**：与 Macbeth 同袍同得预言的双柱之一；保持"我有 cursèd thoughts 但我祈求自我克制"的内在防御
- **终点**：在 A3S3 被昔日同袍派来的杀手杀死，但临死把 Fleance 送走 + 命他复仇——他的物理死亡不是终结，而是从"被动旁观者"变成"通过后裔继续在故事中存在的预言载体"
- **核心转变**：从"沉默的旁观者"变成"通过死亡和后裔将预言实现"的角色——他从未亲手做任何事，但他的存在本身（生 + 死 + 子嗣 + 幽灵 + A4S1 八代王显灵）持续推进剧本的核心反讽：Macbeth 杀他正是为了阻止预言，结果反而加速预言的实现
- **关键转折点**：
  - A1S3 与 Macbeth 同得预言但反应相反——主动询问而非被动接受（scenes/scene_A1S3.md:L137-L160）
  - A2S1 在 Macbeth 弑君前夜的最后一次对话——他用"my bosom franchised"明确拒绝任何潜在的同谋（scenes/scene_A2S1.md:L82-L89）
  - A3S1 加冕后独白——已知真相但选择沉默，是他弧线上唯一的"主动选择不行动"的时刻（scenes/scene_A3S1.md:L9-L20）
  - A3S3 临死令 Fleance 逃 + 复仇——他唯一一次明确的、面向未来的指令（scenes/scene_A3S3.md:L66-L72）

来源：phase2_roles.yaml → roles.banquo.status_arc

> 弧光为内在转变；班柯的物理终局（A3S3 被杀 + A3S4 鬼魂出场 + A4S1 八代王显灵中"持镜"出场）写在 references/canon-ending.md。
