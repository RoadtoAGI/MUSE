# Build Report — 海的女儿

> 构建时间：2026-05-23
> 触发：novel-analysis Phase B 流式蒸馏，短中篇路径（B2-short）
> 总场景预算：6 场 / 16,032 字（union = 全部场景）
> canonical 状态：novel-meta.yaml 不存在，跳过 Step 2f-2g（claims.yaml 抽取与联网核对）

## 候选角色 pool（按 Step B0 启发式扫描 phase2_character.yaml）

按 phase2 启发式规则识别 7 个候选：

| # | 角色 | 入选依据（phase2） |
|---|------|-----------------|
| 1 | 小人鱼 | protagonist 字段 |
| 2 | 王子 | antagonist.components 之一 + 在 supporting_cast 中扮演核心 + 独立 voice / 关系 |
| 3 | 海的巫婆 | antagonist.components 之一 + 独立 voice 特征极强 |
| 4 | 邻国公主（神庙女子） | antagonist.components + contrast_axes 对照（"在王子面前的位置"轴）+ key_tensions 零和位置 |
| 5 | 海王祖母 | supporting_cast 有功能 + contrast_axes 保守一极 + key_tensions "保守长寿主义" |
| 6 | 五个姐姐（集体） | contrast_axes 第一条 + key_tensions "亲情召唤"（终局剪发换刀）|
| 7 | 天空的女儿（集体） | 仅在 ensemble_design.redemption_cluster 中作为结局接引者 |

未进入候选 pool：
- 海王 — 仅 supporting_cast 中一句功能描述（"缺席的父权"），无独立 voice / 弧光 / 关系记录

## 已构建（4 个）

| Role | 中文名 | locator_count | 覆盖场景 | 备注 |
|------|--------|---------------|---------|------|
| `xiao-ren-yu` | 小人鱼 | 19 | scene_S01 / S03 / S04 / S06 | 主角；6 场全出场，4 场作 locator 佐证；S02 / S05 在画像维度冗余支撑 |
| `wang-zi` | 王子 | 7 | scene_S02 / S04 / S05 | 无内在 character arc——一致塑造的角色，本作让"善良无辜的认知盲点"成为悲剧引擎 |
| `hai-wang-zu-mu` | 海王祖母 | 10 | scene_S01 / S02 / S03 / S04 | 无内在 character arc——稳态人格，"知道事实但选择平静"立场的代表 |
| `hai-de-wu-po` | 海的巫婆 | 10 | scene_S03（单场出场）| 无内在 character arc——规则的人格化执行者；"诚实反派"框架的范本 |

软建议覆盖度集中观察：

- `xiao-ren-yu` 全部软建议达标
- `wang-zi` 全部软建议达标
- `hai-wang-zu-mu` 全部软建议达标
- `hai-de-wu-po` 单场出场——违反"声音跨 ≥2 场"软建议，但单场内五种对白模式（预判型 / 列条款 / 不施压 / 附赠 / 仪式语）已穷尽其声音；属于稳态角色不可避免的软建议违反。已在 build-meta.coverage_note 中说明

## 未构建（3 个）

| 候选 | 原因 |
|------|------|
| 邻国公主（神庙女子） | **声音几乎不存在**——她在原文中无任何对白；scene_S02 神庙岸她"似乎非常吃惊" + "找了许多人来" 仅描述行为；scene_S05 她出现时被王子认领为新娘"羞答答地被紧紧抱在怀里" 仅描述被动反应。作为"误认结构的填位者"功能性配角，独立 SKILL 价值低。其角色定义已在 `xiao-ren-yu` SKILL 的"边界 2"（绝不揭穿邻国公主的误占）和 `wang-zi` SKILL 的"性格真相"（视觉相似认领机制）中通过反射性引用涵盖 |
| 五个姐姐（集体） | **集体角色无个体差异**——五人 voice 统一（旅行式好奇 / 家庭立场 / 终局递刀）。character-kb-distill 设计针对单一角色，不适配集体身份。其集体功能已在 phase2_character.yaml 的 `ensemble_design.family_cluster` 和 `xiao-ren-yu` SKILL 的"边界 5"（绝不通过回到海底逃避代价）+ 弧光关键转折点中说明。**如下游需要单独提取"递刀场景的姐姐声音"**，可基于 scene_S06.md:L4-L4（剪发换刀对白）按需建一个集体 SKILL（`wu-ge-jie-jie`），但当前不蒸馏 |
| 天空的女儿（集体） | **仅在结尾接引段（scene_S06）短暂出场**，作为开放式救赎机制的人格化解说者，功能性大于角色性。她们的"声音"在 scene_S06.md:L9-L9 已被 `xiao-ren-yu` SKILL 的"核心欲望"段（不自觉欲望的揭示）涵盖。**作为题材构件而非可扮演的人格**，独立 SKILL 价值低 |

## 补充输入读取记录

- `phase0_conception.yaml`：未引用——本作的 controlling_idea / style_directives 在 phase2_character.yaml 中已通过 `contrast_axes` 和 `relationships` 间接反映，无需直接读取
- `phase1_world.yaml`：未引用——人鱼物种规则（无眼泪 / 无灵魂 / 三百年寿命 / 化为泡沫）在小人鱼身份段直接溯源到 scenes/scene_S01.md 和 scenes/scene_S03.md 的对白，未通过 phase1 中转
- `scenes/*.md`：6 场中 5 场被作 locator 佐证（S01 / S02 / S03 / S04 / S06），S05 在画像维度冗余支撑未独立 locator

## 知识库下游用法提示

本次蒸馏的 4 个角色 SKILL 包对应不同下游用例：

| 用例 | 推荐加载 | 不推荐加载 |
|------|---------|-----------|
| 同人 / 重生 / 平行时空（让小人鱼有不同结局） | `xiao-ren-yu` + `wang-zi` | 不必加载 `hai-de-wu-po`（同人通常要让契约可改） |
| 续写（延续原作精神 / 类似结构的新故事） | 全部 4 个 | — |
| 安徒生研究 / 原著范式学习 | 全部 4 个 + `phase2_character.yaml` | — |
| "诚实反派"语言模型范本研究 | `hai-de-wu-po` 单独使用 | — |
| "认知盲点制造悲剧"机制学习 | `wang-zi` + `xiao-ren-yu`（成对加载） | — |
