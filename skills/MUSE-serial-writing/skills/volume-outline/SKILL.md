---
name: volume-outline
description: 连载卷纲设计。由 serial-outline 在新作起卷、开新卷或补齐接管作品未定卷向时调用，形成供章节编排与卷收束消费的卷纲。
---

# volume-outline — 卷向与结构

产物为 `series/volumes/V0N.yaml`，由章级编排与卷收束消费。字段读 [卷纲模板](../serial-outline/references/templates/volume.yaml)及 [workspace-schema 的卷纲节](../serial-outline/references/workspace-schema.md)；共创权限和决策回写按 [共创协议](../serial-outline/references/collaboration-protocol.md)。通过当前宿主正式方式加载本包依赖，脚本根与系列工作区由调用者显式提供。

## 进入本卷

新卷通常承接已收束前卷，V01 承接立项；接管当前卷时保留已发布条目与已发生变化，只议未定部分。读取总纲中的已确认方向、当前 intent，前卷 digest/收束结果、相关人物状态与未解决线索；有具体疑点再回原文或台账。作品中的实际经历决定本卷起点，历史接管材料按来源截止点使用。

开卷前列出本卷尚待承接的决定：

需要人物后续轨迹时，按需读已有 `series/character-skills/phase2_character.yaml` 的作者侧设计；persona / V00 只表达开场成立的信息。接管无此设计时从既有经历与作者当前意图推演，不向角色输入补入未来答案。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/match_decisions.py list \
  --work-dir works/<slug> --level volume --volume V0N
```

新列出的方向、禁用事项与已采用在总纲中的决定共同约束设计。命中范围内的要求如相互冲突，指出受影响选择，按权限解决。仅有候选文件不代表作者已经选择；恢复时先读候选、决定与 `pending`，继续尚未完成的动作。

## 推演本卷

把人物现状、本卷问题和可能事件放在一起推演：人物想达成什么、遇到哪些有效阻力、选择与反应怎样改变局面。`protagonist_delta` 记录卷首到卷末的处境、关系、认识或性格变化；人物立场稳定时，写清其坚持带来的外部后果。卷问题 `volume_question` 说明读者本卷在等待什么及卷末怎样回应；可用局部结果形成收束，再把新的问题留给下一卷。

例如，人物卷首坚持救人、卷末仍坚持救人，单写“学会勇敢”会虚构内在变化；若经历使他从单独承担后果变为获得他人共同承担，则关系变化可以组织事件。决定性差异是事件造成的真实变化，人物无需匹配某种成长模板。

低对抗卷也可由阶段成果组织中段：形成一种能力、建立合作或取得共同认识，使下一阶段成为可能；亲历后的理解又可能改变完成标准。把这种变化放在 `protagonist_delta`、必要的卷转折与后续章意图中，逐章 logline 说明实际成果及承接。章条目的 `opened/closed` 继续只记录伏笔 thread_id。

多线可通过主题矛盾、主题回响、主线启动铺垫或制造纠葛形成联系；牵挂与判断也可让不同事务在同一人物内心相互影响。多位主人公分别保有追求，共同事件可以使一方成功、另一方失败；形成合作后仍依据各自欲望推演。保留各线的阶段发展，按当前读者关切、已有结果和另一线将带来的作用安排切换，允许错开启动与收束。需要推敲人物接力、跨线条件延迟生效、同期补叙或结局先后时，按问题读[场景与编排参考](../chapter-scene-plan/references/mckee-scenes.md#事件顺序与读者呈现)及其中案例；`narrative_lines` 继续承担定位，单线与纯对照无需增设交叉因果。

只在方向有实质分歧时提出候选，用关键剧情与取舍说明差别。需中断恢复时将候选落 `series/decisions/D-####-candidates.yaml`，保留问题、可选方向及各自代价即可。已有明确方案直接展开；作者已委托的范围由模型决定，需作者选择的开放决定按共创协议等待。候选数量和转折条数由本卷需要决定。

参考在能改变卷向时提前取得：

- 思想、关系或结构难点可由 `inspiration-research` 路由到可用的 `design-doc-reference`，提供本卷问题、活跃线和所需尺度。读取原作机制与条件后设计本作事件。
- 本作既有连载片段可用可选包的 `serial-scene-reference`，传实际发布册及可见截止序。跨作取材保留机制与迁移条件，同作连续性保留事实与名称。
- 副本取材由可选包 `takeover-distill` 的供材分支处理。把原作范围和允许改动的对象随当前卷向明确，按其格式读 world-card 与所需卡片，将生效规则和原作定位放进既有 worldbook 副本册；未知事实继续保留未知。

可靠参考不足时，按本卷人物和因果条件完成设计。外部作品来源的具体限制仍按供材包协议执行。

## 落盘与交接

选定或获委托自决的卷向写入卷纲：

- `protagonist_delta` 与 `volume_question` 保留上述创作意图。已有历史卷只写有来源的变化，未完部分保留作者的已定方向。
- `tentpoles[]` 写承担卷级转折的 `beat / value_shift / anchor`，没有适用转折时可为空。描述谁因何作出选择、局面怎样改变，保留后续实现空间。规划位置用 `unresolved`，章物化后锚到实际章号；已发布来源直接用 manifest 章号。
- `world_reveal_plan[]` 只列确需安排的世界揭示，使用稳定 `reveal_id`、内容与 `from_ceiling` 依据。揭示若违背已确认的世界边界，收窄方案或提出冻结修订；原有边界内的细化按相应 worldbook 册的规则处理。`planned_at` 记录预期单元或章；章级编排在兑现前确定位置，当前未指定位置时保留铺垫与正式揭示的区别。铺垫首次出现应有当场用途；重释型分晓保留事实、改变解释并产生后果，因果条件的延迟兑现则保留其形成、传递与后来生效的依据，具体区别见[伏笔与后续作用](../chapter-scene-plan/references/mckee-scenes.md#鸿沟伏笔与分晓)。普通伏笔与延迟条件继续沿已有章意图和适用的线索记录传递，世界揭示字段只承担原有职责。
- `narrative_lines[]` 仅在多线编排需要定位时记录，跨线因果仍写在转折、单元或章意图中。
- `chapters[]` 可为空；当前卷按实际编排滚动补章。逐章 logline、hook 与场景输入交 `serial-chapter-writing`。

本卷决定落既有 `D-####.yaml`（`kind: volume_direction`，`scope.level: volume`）。卷纲采用的决定在落盘后逐条回写：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/match_decisions.py consume \
  --work-dir works/<slug> --decision D-#### --by volume:V0N
```

确认本卷问题和变化能指导章节选择，所填转折含因果/价值变化与合法锚点，揭示可指认已有世界依据；命中的决定已承接或明确交回待决。普通完成由 serial-outline 接续交接。若存在具体跨来源矛盾或作者要求独立核对，由 serial-outline 调本包 `outline-validation scope=volume`，将报告反馈回对应设计；无须增设开卷审计。
