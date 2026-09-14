# 连载人物表演的输出约定

## 写作前 role_move

本节是本包 role_move 的字段权威。每个角色单独写入 `pipeline/staging/scene_{scene_id}/{slug}_role_move.yaml`：

```yaml
scene_id: S0X
character: <已绑定的角色文件键>
moves:
  - "on": cue_1
    meaning: "<本人已有前提如何使这一刺激或主动意图具有当场含义>"
    move: "<本角色会实施的一次言语、身体或心理行动，含有作用的沉默或自然组合>"
    intended_effect: "<角色希望对方、现场或自己的态度、预期、理解发生的即时变化>"
```

`scene_id`、`character` 与 dispatch 及本人 view 一致，`moves` 为 list。`moves: []` 是完整产物，表示没有能改变 writer 实现的独特人物候选。

每条 move 的 `meaning`、`move`、`intended_effect` 均为非空字符串。`"on"` 可选：回应刺激时引用本人 view 的 `observable_stimuli[].id`；主动发起时省略，以已知承诺、追求或事实支撑其 `meaning`。写入时为 `on` 保持引号，兼容 YAML 1.1。多个 cue 共推同一选择时只写一个 move，锚定最直接的 cue。

一次选择不再拆成独立的心理、决策、动作、台词和反应栏目。`meaning` 保留简短人物依据，`move` 提供候选行动，`intended_effect` 提供人物当下希望促成的作用；心理行动可在内心完成，期待的效果也不保证实现。三者各有用途，不重复陈述同一内容，不把作者的潜意识诊断与弧光目标写成人物自觉。

文件键由[上下文协议](../../serial-chapter-writing/references/context-contract.md)绑定，不根据中文名临时猜测。orchestrator 只向 writer 授权本次完成的角色文件，不因旧文件存在就默认生效。

## 审稿 validation

输出路径沿用 `pipeline/staging/scene_{scene_id}/{slug}_validation.md`。反馈只记录被审片段、支持判断的人物或事实依据、冲突或合法变化的解释，以及必要的修订方向；没有可定位问题时简述所查范围与结果即可。

角色校验不产 role_move，也不把参考意见升级成新的角色设定或已发布事实。反馈由当前审阅者消费，纳入既有审稿和修订路径，见[校验方法](validation-method.md)。
