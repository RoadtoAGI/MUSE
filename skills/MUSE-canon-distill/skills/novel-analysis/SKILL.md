---
name: novel-analysis
description: 逆向分析已完结小说，提取构想、人物和结构，按任务建立场景与角色参考。用于小说拆解和建库；在连作品使用 serial-analysis。
---

# 小说逆向分析

命令中的 `${CLAUDE_PLUGIN_ROOT}` 以本技能所属包的实际安装根替换；Claude 插件可用宿主提供的该变量。其他宿主从当前技能位置定位包根。

以指定版本原文解释事件、人物与表达怎样产生作用，供设计与手艺参考。麦基的结构分析帮助寻找选择与后果；分析者重建的解释保留依据，不冒充作者自述。结局能帮助检验整体解释，阅读顺序按来源与当前问题安排。

## 范围与执行关系

输入为本包 `knowledge-base/novels/{书名}/full_text.md` 及已有版本资料。用户限定作品单元、章节、阶段或角色时沿用该范围；完整建库授权包含下述已选工作，不逐步重复征求确认。

| 部分 | 产物与直接消费者 |
|---|---|
| A：设计与场景 | Phase 0–5 分析供 design-doc-reference；按任务切片与索引供 scene-reference、对白事件蒸馏 |
| B：角色参考 | character-kb-distill 生成角色包、来源片段与 character_map，供人物研究及创作参考 |
| C：手艺标注 | craft_notes 及按需 sidecar，供技巧与文风参考；结构化标注由 kb-annotator 拥有 |

仅请求设计分析时不自动切片；角色蒸馏须有系统人物图与可回读原文，切片和个体画像不是前置门槛。B、C 可独立续做，已有磁盘产物保留来源与覆盖范围。

## A：设计、切片与检索

### 阅读与分析

能容纳原文则通读；长篇加载 [导航与定向阅读](references/long-novel-analysis-path.md)，以章节导航定位实际原文。摘要供导航，关键事实和解释回到原文确认。

读取 [分析框架](references/analysis-schema.md) 后，按已有证据形成下列文件；相关理论、字段与原文定位在框架中就地解释。已读规则无需每个 Phase 重载。

| 文件 | 主要信息 |
|---|---|
| `pipeline/phase0_conception.yaml` | 前提、价值问题、整体解释、类型与表达特点 |
| `pipeline/phase1_world.yaml` | 世界条件及其对人物选择的影响 |
| `pipeline/phase2_character.yaml` | 人物功能、对比与关系；个体分析按需要另存 |
| `pipeline/phase3_spine.yaml` | 组织力、实际轨迹与整体结果 |
| `pipeline/phase4_structure.yaml` | 序列及跨段关系 |
| `pipeline/phase5_scenes.yaml` | 有分析价值的场景、情境、作用与原文定位 |

每份 YAML 带 `analysis_meta`。合集共享的 Phase 0–2 可留在 `pipeline/`，独立单元的 Phase 3–5 放在 `pipeline/{作品单元}/`；单元名进入来源定位，合并索引使用不冲突的场景 ID。原作存在多线、信息释放或时间重组时，保留具体跨线影响和知识变化。短篇可压缩分析层级，场景内节拍也可承担主要转折；层级与场景数量由实际结构决定。进一步拆解时读取 [节拍分析](references/beat-analysis.md)。

### 原文切片

场景入库或下游确需原文片段时，从 Phase 5 定位起止行；片段应保留理解行动、回应和效果所需的上下文。使用绝对路径，避免宿主工作目录改变输入位置：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/extract_scene.py   --source <作品目录>/full_text.md --batch <切片范围JSON绝对路径>   --output-dir <作品目录>/scenes
```

范围 JSON 为 `[{"scene_id":"S01","start":60,"end":85,"chapter":"第1章"}]`。单场可用 `--scene-id / --start / --end / --chapter`。脚本先验证整批范围再裁剪；非零退出时修正定位，不把旧切片作为本次成功结果。

在作品根 `scene_index.json` 写条目列表：

```json
{"scene_id":"S01","novel":"作品名","author":"作者名","genre":"题材","lang":"zh","source_medium":"novel","tags":[],"characters":[],"conflict_type":"personal","pov":"视角人物","word_count":800,"source_chapter":"第1章","file":"scenes/scene_S01.md","description":"当前情境及其作用","has_craft_notes":false}
```

身份与 `file` 用于原文定位；genre、lang、source_medium 用于查询过滤；人物、标签和描述用于召回；word_count 填实际统计。未成立的冲突或视角不按示例补造，相关可选项可省略。索引覆盖本次实际选取的场景，抽样场景不代表全书全部事件。

场景与索引完成后，加载 `dialogue-kb-distill` 处理本作品目录；对白事件、原文核对与 coverage 由其负责。覆盖状态只针对已登记的场景，不因全部切片已标注就宣称全书对白穷尽。

### 进入检索

新建或修改场景索引后，现有向量检索使用聚合索引与对应嵌入：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/merge_scene_index.py
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/build_embeddings.py --channel all --novel "{书名}"
```

已有向量却没有快照文件的旧库，首次合并前用 `build_embeddings.py --bootstrap` 领养现有向量；无需重复。聚合包含小说与戏剧，按实际来源索引核对本次作品条目及其向量对应关系；无 style_profile 的行可无文风向量。嵌入服务不可用时交付已完成的分析和切片并报告检索尚未更新，不称其已经可召回。

## B：角色参考

从系统人物图与本次用途确定目标角色。组织、时代压力等抽象对抗力量不当作人物建包。按 [角色定向阅读](references/long-novel-distill-path.md) 取得有关身份、选择、关系与声音的证据；没有场景切片时直接定位 full_text。证据足以支持有用参考即可构建，稳定人物或声音证据少不等于没有参考价值。

通过宿主明确调用本 canon 包：

```text
/character-kb-distill build --novel-dir <作品绝对目录> --role <显示名>
```

传入本次来源版本、允许范围和已有材料。子技能拥有模板、原文引用生成、character_map 与结构检查；此处不重复其检查过程。新材料改变结论或范围时 rebuild，未改变时沿用。未构建的目标在已有 `characters/build-report.md` 说明具体证据缺口。

## C：手艺与结构化标注（按需）

按 [手艺标注](references/craft-notes-template.md) 写 `craft_notes/scene_{id}_beats.md`，并更新索引的 `has_craft_notes`。保留原作选择、效果依据与迁移条件。

需要文风、技巧 sidecar 或灵感提名时，向本包 `kb-annotator` 传作品目录名、实际 annotated_by 与入口/档位。agent 及其任务包拥有字段和命令，不重复嵌入整套标注工作流。全库灵感聚类须属于当前全库任务范围，单作品建库不自动扩张为全库重做。

## 交接与反馈

返回已完成范围、实际产物路径及影响消费的缺口。解释失真时回到来源和分析，切片失败修定位，角色参考问题交构建入口，索引问题修对应工具输入。字段齐全、可检索和原文解释成立分别判断；作品优劣与审美选择留给使用者。
