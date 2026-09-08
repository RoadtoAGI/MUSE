---
name: dialogue-reference
description: 为当前单个角色检索有来源的连续对白事件，供 role_move 排练理解互动机制；无适用事件时返回 NO_MATCH。文风场景检索使用 scene-reference。
allowed-tools: Read Write Bash
---

# 角色对白参考

接收 work_dir、scene_id、role_slug，读取 `{work_dir}/pipeline/scene_{scene_id}/role_views/{role_slug}.yaml`，以本人 `character_basis` 和当前事实为人物依据；仅在调用方显式提供合时补充时读取，不自动打开共享人物包的最新版本。query 只从本人已知事实、可见刺激、关系认识和声音依据形成；完整 scene_card、对手私密目标与预定结果不进入角色参考。缺 role_view 时返回输入缺失。

## 查询

描述对方可见的言行、本人的回应目的及当场关系/压力。relationship、pressure、speech_action 是相容查询的必要信息，无法确认时不猜测；脚本返回 NO_MATCH。power、cooperation、capacity、medium 仅在明确时附加。词表与库中同名字段相对照，含义不确定时不强行映射。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/dialogue_query.py   --scene-id S01 --role-slug role-a   --query "本人可见的交锋及回应目的"   --relationship peer --pressure concealment --speech-action probe   --output-dir "{work_dir}/pipeline/references"
```

使用实际安装位置与宿主执行能力；字段缺失时省略相应参数。查询只使用 source_checked/reviewed 的事件，同一目标回合必须同时满足所传的 speech_action/cooperation/capacity，不能将对手属性拼接。关键词只在相容事件中排序。独白需要时显式传 --include-monologue。

## 交接与使用

输出 `{work_dir}/pipeline/references/{scene_id}_{role_slug}_dialogue_ref.md`，回主控本次有效路径及 MATCH/NO_MATCH。失败时明确回“无”，不能让同名旧文件生效。主控只把本次选中的角色参考交给相应 actor；writer 取得本轮获准的 role_move 候选。

MATCH 表示存在可供判断的来源事件，单一有据案例也可使用。读取连续回合及定位，判断上一轮怎样影响下一轮、目标说话者为何这样回应，按当前人物条件迁移机制。不同来源可相互比较，但来源数量不证明通法。人物姓名、经历、世界事实、标志性原句和口癖不随例子进入当前角色。

缺条件、无相容事件或索引不可用时不伪造示例。NO_MATCH 不含 dialogue_exemplar，actor 按现有角色材料与对白理论继续。来源定位与检索相容性不代替对本次候选的实际判断。
