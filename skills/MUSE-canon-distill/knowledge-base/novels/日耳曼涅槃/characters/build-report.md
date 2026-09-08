# Build Report — 日耳曼涅槃

> Phase B 流式蒸馏 · builder: character-kb-distill · 触发条件：非 canonical 网文（无 novel-meta.yaml，跳过 claims 流程）· 长篇 163 万字，B2-short 批式路径（union 场景集 16 场）+ B3 定向补切 4 场（scene_27-30）

## 已构建（2026-07-06，单会话流式完成）

| display_name | role_slug | locators | 场景覆盖 | 验证 |
|---|---|---|---|---|
| 方彦 | fang-yan | 26 | 11 场（scene_01/03/04/05/07/09/11/12/13/15/19），弧光四转折全锚定 | --check-structure exit 0 |
| 希特勒 | hitler | 20 | 9 场（scene_03/05/06/12/13/14/18/19/26），声音四档全锚定 | --check-structure exit 0 |
| 琳娜 | lina | 19 | 3 场（scene_07/27/28），要挟-真爱-同志三段变奏 | --check-structure exit 0 |
| 雷德尔 | raeder | 20 | 4 场（scene_04/05/09/29），伯乐-防备-锁才三点弧光 | --check-structure exit 0 |
| 西尔维娅 | sylvia | 14 | 5 场（scene_02/12/28/29/30），占有→成全的换轨弧光 | --check-structure exit 0 |

B3 破例记录：为补齐雷德尔（第368-369章）、琳娜（第92、301-302章）、西尔维娅（第162章）的关键证据，按 B3 路径定向读原文并补切 scene_27-30 入库（这四段同时是 ARC1-SEQ6 / ARC4 暗线 / ARC5-SEQ2 / ARC2-SEQ4 的结构关键拍，双重价值成立）。

## 未构建（候选 pool 内，留档原因）

| 候选 | 原因 |
|---|---|
| 沃克 | 单场景窗口角色（scene_06）——民意底座采样功能，无独立欲望-对抗结构，声音仅一场；不满足"少而强" |
| 鲍曼 | 零对白切片——构陷线（第366-377章）以叙述层活动为主，无可锚定声音样本；其威胁形态已在 hitler / fang-yan 包中侧写 |
| 丘吉尔 | 切片内无出场（仅被转述）——第426章演说等关键声音章未切；对手视角蒸馏价值高，后续若补切可单独 build |
| 瓦尔特 | 零对白切片——庞氏/经济线以叙述概括为主，声音样本不足 |
| 邓尼茨 | scene_21 为战场群像视角，个人声音不足一场；游说戏（第373-374章）未切片 |
| 古德里安 / 墨索里尼 / 福布斯 | 功能性出场，声音分散于叙述；对比轴信息已由 phase2_character.yaml 系统级承载 |

## 补充输入

- `pipeline/phase2_character.yaml`：全部五包的功能定位 / 对比轴 / 关系张力来源
- `pipeline/phase0_conception.yaml`：style_directives（声音框架与作品风格对齐）
- `pipeline/phase3_spine.yaml`：desire_object / opposing_forces（方彦欲望系统的结构参照）
- 个体画像 `characters/方彦.md`、`characters/希特勒.md`（Phase A 第二轮产物）：历史原型差异与手艺决策的分析底稿
- 原文破例阅读：第92 / 162 / 301-302 / 368-369 章（B3，全部已转化为 scene_27-30 切片，locator 均可回验）
