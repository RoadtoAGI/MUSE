# 台账回填

按卷或章窗口扫描，回填三台账与角色快照序列。中断后从已保存的分析范围和台账继续；fast 档按入口 skill 的读取深度选择来源。完整字段契约位于 MUSE-serial-writing 包内 `skills/serial-outline/references/workspace-schema.md`；本页各节链接到生成时所需的本包模板。

## threads.yaml 回填

生成前读取 [悬线模板](templates/threads.yaml)。

- **入账判据**：伏笔（埋设待收）/ 悬线（持续未决冲突）/ 承诺（叙事者对读者的预告）/ 谜团（显式未答问题）——正文有埋设证据才立条目，读者脑补的期待不算。
- 每条：`thread_id`（T-### 顺序分配）+ `kind` + `opened_at`（裸章号）+ `events[]`（`{at, kind: advance|payoff, note}` 逐卷追加）。
- `statement` 保留开启时已成立的问题，后续揭示按发生章追加到 `events`。消费者会单独截取历史窗口，初始描述中的后章信息无法被事件过滤撤回。`intended_payoff` 仅承接明确作者计划，已经发生的回收记为 payoff 事件。
- **未回收项 `status: open`**——在连作品大量 open 是常态，不强行判收束；跨多卷仍 open 的主干 threads 在交付报告中点名（接管方开卷时的天然输入）。

## world_facts.yaml 回填

生成前读取 [世界事实模板](templates/world_facts.yaml)。

- **入账粒度判据**：只有**跨章持久 + 未来章会消费/校验**的状态入账——装备易主、能力获得/损毁、境界突破、规则揭示、秘密扩散。场景内瞬态（血量波动、临时位置、一次性情绪）不入账。
- 出处锚 `established_at`：优先场景级 `C####S##`；**缺场景号 fallback**——切分产物无场景切分或定位不到场景时降为章号 `C####`，合法不阻断。
- 一条事实承载同一生效时点、条件下的属性值。不同时间成立的职责、经历或规则分别入账；同一属性发生变化时追加新条目，以 `supersedes` 指向旧值。合并不同时间的事实会让早期状态消失或后期状态提前出现。
- 人物实体的 `entity` 在所有 `kind` 下均使用角色目录 `char_id`；关系以 `attribute: relation:<对方 char_id>` 表示，`known_by[].char_id` 同样用该标识。非人物实体使用作品内稳定名字，与后续章卡 `recap_inputs.locations/items` 保持一致。
- 能力/规则类 `limitation` 写原文支持的代价与边界；未知时写“原文未揭示代价/边界”，满足导入的非空接口。影响续写的未知同时进入 `story_bible.intent.open_questions`。
- 秘密类 `kind: secret` + `known_by`（谁在哪章获知，append 语义）。

## biography.yaml 回填（每目标角色一份）

生成前读取 [人物经历模板](templates/biography.yaml)，`char_id` 与所在角色目录一致。

- `milestones[]`：原文已经发生且持续影响人物的变化；每条填写 `at/kind/before/after/evidence`，`at` 使用 manifest 中的裸章号或其场景锚 `C####S##`，`evidence` 为足以支持变化的原文片段。`before/after` 写明事件造成的差异，已有摘要不能代替这两个字段。
- `kind` 按事件选认知转变、能力获得、关系变化、创伤、誓言或退场；不匹配时可采用类型扩展。普通目标只有在原文出现誓言行为时才归为誓言。持续变化没有来源证据时，`milestones: []` 合法；不为填满种类补造成长。
- `growth_track[]`：按已有文本分段归纳弧光（`{segment, mode, from, to, spans}`）；未完结段的 `to` 以当前状态写实，不预测；稳定轨迹或尚无可归纳转变时可留空列表，不补造成长。
- `last_seen` 取该角色最后出场章。

## 角色快照序列

目标角色按 `Skill character-kb-distill` 的连载快照模式产 per-volume `snapshots/V##.yaml`（`extends` 上卷、卷粒度演化基线）+ `persona.md` 静态人格层。fast 档优先主角、断章活跃角色、近期续写关系及仍有后果的历史人物；角色出现较晚也可以是必要输入。full 档覆盖全部已出现角色。具体范围沿入口确定，不重复按数量筛选。

## 回填自检

- 每条台账条目的锚章号必须真实存在于 manifest entries——锚不上的条目回炉；
- threads 双向：卷纲条目 `opened`/`closed` 与 threads 台账互查一致（现有 export gate 检查引用一致性）；
- 会影响续写的未知随 intent.open_questions 交付；没有证据的可选内容保持缺省，报告不代替机器导入的内容。
