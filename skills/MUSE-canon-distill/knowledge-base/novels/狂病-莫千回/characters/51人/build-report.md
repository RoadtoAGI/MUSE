# 《51人》篇 — 单篇人物蒸馏 build-report

- 篇：51人（scene 前缀 PREFIX = 51）
- 模式：reference（参考包）
- 构建器：character-kb-distill
- per-part map：characters/51人/character_map.json（5 条，本篇隔离，未写根级跨篇 map）
- 构建日期：2026-05-29

## 蒸馏了谁（5 个，verify 全部 exit 0）

| slug | 中文名 | desc（人设类型原型） | has_canon_ending | locator_count | verify |
|------|--------|----------------------|------------------|---------------|--------|
| zhang-yichuan | 张亦川 | 无存在感的反英雄式幸存者（张亦川·狂病-莫千回·51人） | false | 15 | exit 0 |
| ci-chengyundan | 刺成云丹 | 守人性底线的忠义异族搭档（刺成云丹·狂病-莫千回·51人） | false | 7 | exit 0 |
| qin-liangyue | 秦良岳 | 好人没好报的灰色救赎者医生（秦良岳·狂病-莫千回·51人） | true | 10 | exit 0 |
| tao-yiren | 陶亦仁 | 死亡奔赴型邪教感召者领袖（陶亦仁·狂病-莫千回·51人） | true | 11 | exit 0 |
| lao-dage | 老大哥 | 仁慈而自知不宜掌兵的过渡型队伍领袖（老大哥·狂病-莫千回·51人） | true | 7 | exit 0 |

取舍依据：完全按 _candidates.md 的"蒸馏建议"——
- floor = 全部"值得做"：zhang-yichuan / ci-chengyundan / qin-liangyue / tao-yiren（4）。
- 追加 1 个有原型价值的"可做但非必需"：lao-dage（"仁慈但自知不宜掌兵"的过渡型领袖 + "2 比 1 纪律"战术载体，原型与世界观资产价值）。

canon-ending（仅 has_canon_ending=true 生成，均回 scene 原文核对不可逆终局）：
- qin-liangyue：自选感染作为安乐死（scene_51-S11.md L31-L43），化为感染者蹦跳奔向夕阳倒下。
- tao-yiren：被感染创世军同伴撕成米黄色骸骨（scene_51-S05.md L3-L7）+ 遗留"追杀罗允"命令。
- lao-dage：创世军崩塌时被感染，抱陶亦仁头颅自毁式泄欲（痛苦型感染者，scene_51-S05.md L13-L15）。

## 跳过了谁（+原因）

| 名称 | 原因 |
|------|------|
| 无名自爆同伴（汽修工） | _candidates.md 标"不蒸馏"——主题（被遗忘）要求其保持无名，信息不足以独立成角。其自爆是 main climax 的功能/主题承重点，已在 zhang-yichuan 弧光转折处以 locator 引用承载。 |
| 三个拆收音机的年轻人 | _candidates.md 标"不蒸馏"——群体功能性角色，信息不足；激励事件载体，已在 phase3 inciting_incident 记录。 |
| 罗允（真） | 跨篇主角级，本篇未出场仅被点名（陶亦仁遗留命令"追杀罗允，两个人在行动"）。归属 characters/luo-yun/，本篇不蒸馏，仅作 sighting + 跨篇钩登记（已并入 tao-yiren canon-ending 与 build-meta 跨篇说明）。 |
| 双刀感染者 | 头领型感染者样本，属世界观/感染者类型资产而非可复现独立人格；建议登记到系列统一"头领型感染者"归并，非本目录蒸馏。 |
| 30 岁同伴（妻儿被虐杀者） | 纯功能性配角，单场告白（S03）承载 Arc 2 价值转折的群像证言，信息不足以独立成角。 |

## 跨篇人物（绝不重建，本篇均未出现，无需处理）

罗允（仅被点名，见上）/ 洪扬 / 吴先生 / 石浩洋(wu-xiansheng) / 林东青 / 陶亦仁注：phase0 记 tao-yiren = 李鸾第二人格——本篇以"陶亦仁"在场身份蒸馏，未并入第二人格设定，李鸾 slug 归属《不详》篇。

## 遗留问题

- tao-yiren 与跨篇 li-luan（李鸾第二人格，《不详》人格起源）的 reconciliation：本篇按"陶亦仁"在场身份独立蒸馏，build-meta coverage_note 已显式标注 phase0 的人格归属说明，留待系列统一蒸馏阶段定夺是否合并 / 互链。
- 创世军组织设定 + 双刀感染者（头领型感染者）属世界观资产，未在本人物目录落地，建议归世界观/感染者类型资产层。
- tao-yiren 神格（一人杀七八感染者沾血不染 / 吓跑感染者群）原文为传闻态，已按"据说 / 有人说"承担、未当既成事实外推（遵守跨场景拼因果链 anti-pattern）。
