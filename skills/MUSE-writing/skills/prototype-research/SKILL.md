---
name: prototype-research
description: 为 screenplay-writing 的改编、历史或戏曲题材补充有来源的原型资料。内部按 reference_only 查询已有知识库、公开来源或用户资料，产出 prototype_card.yaml 候选；由设计者选择采用。同人、续写与小说改编使用 MUSE-serial-writing。
---

# 原型调研

## 输入与职责

接收 `work_dir`、`prototype_description`，以及已有的版本、改编范围和具体问题；`slug` 缺省时生成 ASCII kebab-case。需要设计参考时传 `phase_id / genre / signals / narrative_problem`，场景检索传实际 `source_medium`。固定使用 `reference_only`，其他模式返回 `unsupported_reuse_mode`。

资料足以回答当前问题时停止扩展。产出候选资料，设计阶段决定采用与改写；作者明确的内容要求由调用方保留。

## 取材与交付

```text
具体问题与来源范围
  ├─ 已入库作品 → canon 查询已有分析和原文
  ├─ 公开资料   → web 搜索并打开来源核对
  └─ 用户资料   → direct 按实际位置抽取
                         ↓
    references/prototypes/{slug}/prototype_card.yaml
                         ↓
             设计采用 → ledger → 当前场次
```

按来源加载 [canon 路径](references/canon-path.md) 或 [web 路径](references/web-path.md)。使用宿主实际可用的技能与检索工具；用户资料直接读取。补充来源仅解决剩余缺口，保留各项真实来源和版本；本技能只读查询既有知识库。

按 [card 契约](references/prototype-card-schema.md) 写 `<work_dir>/pipeline/references/prototypes/{slug}/prototype_card.yaml`，返回路径、可用发现和影响设计的缺口。查询失败不复用上次同名结果冒充本次成功。无可用证据时返回缺口，不编造来源。

采用者将本次采用的机制、对象、时点和限制写入既有设计字段或 inspiration ledger。writer 消费当前场次指向的采用项；未采用的候选保留在 card。
