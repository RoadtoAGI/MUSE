---
name: live-staging
description: 让常驻角色进程在同一场景里逐回合实况演出，主控兼舞台监督，正文仍交 writer；由 Phase 6 的实况场景调用，构思阶段的人物试演也用它。
---

# 实况演出

麦基《故事》第五章用压力下的选择揭示人物。实况演出把人物放进同一个处境，每名人物由一个持续的宿主会话扮演：它记得此前的日记，只看得见自己看得见的东西，下一回合读到的是对手真实说出的话。主控兼舞台监督，决定谁在场、世界发生什么、何时收场；人物自己的行动归角色进程；正文归 writer。演出的产物是实况记录，writer 从一段已经互相回应过的交锋写这一场。

## 概念

- **角色进程**：一名人物的宿主会话（Claude Code 或 Codex），名册 `pipeline/stage/roster.yaml` 记它的宿主、模型、会话 id 与会话里已有的日记。身份在人物目录的文件里（角色包、`state.md`、`diary/`），会话失效时舞台按文件重建。角色进程没有任何文件工具，开场与每回合的内容由舞台送入，它的回复就是回合。
- **舞台**：本包 `scripts/stage.py`，负责唤醒、解析回合、按可见性路由与归档，不做判断。
- **实况记录**：`pipeline/stage/scene_{id}/transcript.yaml`，按回合记下谁做了什么、说了什么、谁听见看见，以及 POV 人物的内心，是 writer 的人物输入。
- **日记**：收场时人物以自己的口吻写下的记忆，舞台存为人物目录下的 `diary/{scene_id}.md`。日记是人物记得和相信的事，允许误解；什么确实发生过以实况记录为准。

## 一场演出

### 开场前

deriver 已为每名参与者写好本场 role view，字段按实况场景的含义写（见 [role-brief-deriver](../role-brief-deriver/SKILL.md)）；自上一篇日记以来有场外经历的人物另有场外补记 `pipeline/scene_{id}/offstage/{slug}.md`。主控按场景卡写 `pipeline/stage/scene_{id}/setup.yaml`：

```yaml
scene_id: S07
reason: 杜芷方与沈砚舟争的是同一只卷匣，本场的变化来自两人当面交锋
present: [shen-yan-zhou, du-zhi-fang, qiao-lin]   # 开场在场，顺序即轮转顺序
late: [han-tuo]                                   # 迟到者，主控在暂停点让他登场
pov: shen-yan-zhou                                # 只有他的【想】进记录
initiative: du-zhi-fang                           # 可空
story_after: [S01, S03, S05]                      # 可省；倒叙时写本场故事时点之前已演的场景
known_as:                                         # 可省；某人对另一人的称呼不同于显示名时写
  qiao-lin: {han-tuo: 穿灰袍的书吏}
pause_every: 5                                    # 每几回合交主控判断
max_turns: 16                                     # 到达后暂停，由主控收场或追加
world_events:                                     # condition 写给主控自己看
  - id: plate_breaks
    text: 托盘边角撞到瓷盘，盘子落地碎开。
    condition: 争夺卷匣时
```

- 在场者与迟到者按场景卡。人物只从舞台给的称呼认识在场的人，不写 `known_as` 时舞台用显示名：家人之间要写称谓（爸、奶奶），否则人物会叫错；人物不知道对方的名字或身份时写他对对方的叫法，否则等于替人物泄露身份。
- `world_events` 只写场景卡里属于世界的结果（物件、空间、时间、外来者），不写人物该有的反应。
- `pause_every` 决定主控多久看一次实况，交锋密、容易出现说法冲突的场面取小；`max_turns` 是本场的回合预算。
- `story_after` 不写时取本场首演开场时已收场的场景；倒叙场景必须写，否则人物会带着未来的记忆进场。

### 演出与暂停

```bash
python3 "$MUSE_WRITING_ROOT/scripts/stage.py" open --work-dir "$WORK_DIR" --scene-id S07
python3 "$MUSE_WRITING_ROOT/scripts/stage.py" run --work-dir "$WORK_DIR" --scene-id S07
```

`open` 补齐名册并送达场外补记，人物以日记记下；有补记没送达时 `run` 拒绝开演，重新 `open` 只补发没送达的。认不出主控所在宿主时加 `--host claude|codex`。`run` 一直演到暂停点，返回本轮新回合的全知渲染和暂停原因：

| 暂停原因 | 主控怎样判断 |
|---|---|
| `checkpoint` | 读新回合：有说法不相容、到了世界事件的条件或该让迟到者登场时处理，否则继续 `run` |
| `left`、`one_present` | 有人离场：还有戏就继续或让人登场，否则收场 |
| `all_silent` | 在场者一轮都没有动作：注入世界事件、指定一人，或收场 |
| `max_turns` | 场面已完成就收场；还缺关键交锋时 `run --extend N` |
| `invalid_turn` | 人物改过一次仍没按记法回应：看 `log.yaml` 里的原回复，换人或注入事件后继续 |
| `host_error` | 宿主调用失败，瞬时错误舞台已重试过；按错误类别处理后继续 `run` |

暂停点可做的操作：`run --next <slug>` 指定下一个行动者；`event --id <id>` 或 `event --text "<世界事件>" [--perceived-by <谁>]` 注入事件，事件须有世界条件与既有因果支持；`enter --slug <slug> --view "<他登场时看到、听到的场面>" [--arrival "<在场者看到他到来的样子>"]` 让迟到者登场；`show --since <N>` 查看实况记录。

人物的 `做` 只写自己能完成的部分，被针对者优先接下一回合，结果从他的回应里出来。双方说法仍不相容时（一方说夺到了，另一方说还在手里），主控在暂停点以世界事件写出成立的结果。主控不替人物说话或行动，也不往人物的提示里放场景目标。

### 收场与偏差

`close` 向每个在场过的人物收日记，人物记忆随之推进；有人的宿主调用失败时，已写好的日记保留，再次 `close` 只向还没写的人收。收场前，主控把场景卡里本场的结果分三类对照演出：

| 场景卡内容 | 主控怎样对待 |
|---|---|
| 作者确认的结果：用户要求、已批准大纲里写定的方向与结局 | 演出自然到达则接受；到不了时写明人物前提与该结果的冲突，回 [story-writing](../story-writing/SKILL.md) 的大纲裁决 |
| 世界事实与因果：世界规则、物件与空间的后果、`irreversible_action` 里属于外部世界的部分 | 作为世界事件注入，须有世界条件与既有因果支持 |
| 模型暂拟的人物反应：Phase 5 预写的立场、表态与配合 | 演出结果直接替换它，并更新场景卡的对应字段 |

`value_end`、`handoff` 按三类拆开看：外部状态归第二类，人物立场归第三类，作者写定的归第一类。改变作者已批准方向的偏离回大纲裁决，只改本场实现的更新场景卡。重演只因演出过程无效（宿主中断、隔离失效、回合无法解析），用 `open --reperform`；结果与预设不同按上表处理。

## 交给 writer

派 writer 时给出实况记录路径，实况场景不给 role move。writer 按[实况记录契约](../writer/references/live-transcript.md)消费：可以删、压缩、调序，不改人物原话，需要新台词时在回复里提出索句。主控按索句运行：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/stage.py" line --work-dir "$WORK_DIR" --scene-id S07 \
  --slug du-zhi-fang --after 7 --cue "<此刻人物面对什么，用故事内的话写>"
```

舞台按该时点重建人物、补一回合，记为 `kind: line`。主控让原 writer 接着写；宿主不能续接时，把更新后的记录交新 writer。

## 事实改变后的记忆

正文省略某事不改变发生过的事。回滚、重写或获授权的修订改变了已发生的事（谁在场、谁听见、某件事是否发生）时，主控运行：

```bash
python3 "$MUSE_WRITING_ROOT/scripts/stage.py" invalidate --work-dir "$WORK_DIR" --scene-id S03 --change "<改了什么>"
```

该场日记作废，含这段经历的会话失效，此后已演的场景标为待核。随后重演（`open --reperform`），或用 `amend --n <条目号>` 把实况记录改成修订后的样子再 `rediary`，舞台按改正后的记录让人物重写日记。待核场景由主控判断：不受影响时 `review`，受影响时作废后重演或更正。修订者只在回复里报告改了哪项事实，不碰舞台文件。`status` 列出各场状态与待核标记，中断后据此恢复。

## 试演

构思阶段需要知道人物在一个未定处境里会怎么做时，可以用试演代替或补充设计负责人自己的推演；何时用见[大纲构思与回读](../story-writing/references/outline-exploration.md)。试演沿用上面的演出与暂停，区别在下面几处：

- 设计负责人写 `pipeline/stage/tryout/{名}/setup.yaml`。字段同上，另写 `situation`（谁在场、在哪、刚发生了什么，在场者都看得见），可选 `views`（某人这边的处境：手里有什么、刚知道什么）；不写期望结果。试演没有 role view。
- 命令用 `--tryout {名}` 代替 `--scene-id`：`open`、`run`、`event`、`enter`、`show`、`close` 都适用。
- 人物从正式会话分叉，带着全部有效日记；正式会话不可用时，舞台按日记重建。试演里发生的事不写日记，不进正式名册，分叉用完即弃。
- `close` 对每个人做一次意图探针：此刻最想做什么、最怕什么、以为对方要做什么，存为试演目录下的 `probes/{slug}.md`。
- 想问人物为什么那样做时，运行 `interview --tryout {名} --slug {slug} --question "<问题>"`：舞台从试演实例再分叉一次，让它以演员身份回答，存在 `interviews/` 下；演出实例本身不被问这类问题。
- 同一处境要比较不同走向时，换世界事件或首发另开一支试演，每支一个名字。

设计负责人从试演记录、探针与访谈里提炼候选：发生了什么，哪一步改变了关系或代价，读者会在哪里重新理解。候选按大纲构思的现行协议并列交给作者，不自评分、不自动选优；被采用的分支把成立条件写进对应的 phase 文件。试演里人物说过的话不进大纲，正式演出时让人物重新说。

## 名册、宿主与隔离

新进名册的人物默认与主控同宿主：Claude 用 Sonnet，Codex 用本机 Codex 配置里的模型、推理档 medium。作者要求某个人物换模型或换宿主时，改 `roster.yaml` 里该人物的 `host`、`model`、`effort`，舞台下次唤醒时按新配置重建会话。会话是否可以继续由舞台判断：会话里已有的日记与本场时点之前的有效日记一致才恢复，否则重建。

角色进程读不到任何文件：Claude 侧不给工具并以 safe-mode 运行，Codex 侧使用 `~/.muse/codex-role-home` 的最小配置。宿主升级后用 `stage.py check-isolation --host <宿主>` 复核；结果为 `isolated: false` 时停用该宿主的角色进程并报告作者。

退出码 0 表示成功或正常暂停；1 是输入或状态问题，按错误信息修 setup、补 role view 或换操作；2 是宿主调用失败，人物回了空白也算。`open`、`close`、`rediary` 按人物并行，结果的 `errors` 记每人的失败原因，`error_kinds` 标出各人是宿主失败（`host`）还是输入或状态问题（`state`）；两类都有时退出码取 2，成功的人物照常记下，修好后重跑同一命令只补失败的人。同一作品同时只能有一个舞台命令改动状态。
