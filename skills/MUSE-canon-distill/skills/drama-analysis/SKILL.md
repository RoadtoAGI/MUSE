---
name: drama-analysis
description: 从用户指定的戏剧、影视、广播、音乐剧、歌剧或戏曲文本逆向分析作品，建立有原文定位的设计、场景和角色参考。用于剧本知识库建设；写新剧本由 screenplay-writing 承担。
---

# 戏剧分析与建库

本技能以指定版本原文为依据，把构想、世界、人物、故事组织与媒介表达整理成可检索参考。事实、文本解释和新作启发保留不同效力；麦基的戏剧问题、冲突、选择与后果用于理解作品，具体结构由原文决定。

## 输入与执行关系

输入为 `${CLAUDE_PLUGIN_ROOT}/knowledge-base/dramas/{剧名}/full_text.md` 及已有 `work-meta.yaml`。用户指定范围或版本时沿用；原始文件格式需先完成转写。

```text
核对文本与版本 → Phase A：设计分析、场景切片与索引
                             ├─ 对白资料 → dialogue-kb-distill
                             ├─ Phase B：角色证据 → character-kb-distill
                             └─ Phase C：按需手艺标注 → kb-annotator
```

按本次授权范围连续执行；用户明确指定的审阅点仍保留。Phase B 依赖人物分析与场景证据，Phase C 依赖场景切片，二者可独立补做。可选标注未被请求时不自动扩大到全库。

## Phase A：设计与场景

### 阅读与来源

读取目录、版本信息及足以判断形式的正文，确认分析对象。幕场、角色台词与舞台指示可帮助识别媒介；同一书名可能有小说、改编剧本或不同演出本，以实际文本为准。形态或版本歧义影响任务时报告依据；已有原文与目录保持原位。

依据实际篇幅和上下文容量选择通读或分段阅读；分段时保留幕场导航、人物状态与未闭合线索。加载 [分析契约](references/analysis-schema.md) 中当前对象的字段和解释。

### 六层分析

| 产物 | 承载信息与消费者 |
|---|---|
| `pipeline/phase0_conception.yaml` | 整体构想、主要张力与解释；供设计参考与灵感提名 |
| `pipeline/phase1_world_stage.yaml` | 世界条件、空间、制度与实际演出约束；供世界与媒介参考 |
| `pipeline/phase2_roles.yaml` | 人物欲望、处境、关系、声音与轨迹；供角色蒸馏与设计参考 |
| `pipeline/phase3_dramatic_spine.yaml` | 冲突或其他组织力、选择与后果；供结构参考 |
| `pipeline/phase4_act_sequence.yaml` | 原文幕场与分析序列的组织关系；供结构参考 |
| `pipeline/phase5_scene_table.yaml` | 全部场次的作用、条件、变化及原文边界；供切片与索引 |

阅读后按依赖完成上述分析，发现反证时回修已有解释。每个文件保留 `analysis_meta`，关键分析附实际原文定位。印刷幕场、分析序列与节拍分别处理；场景内可有多个节拍与出入场，稳定、缓场和开放结构照实记录。情节模板、固定节点数、每幕逆转或每人独白均不作为完整性的要求。

### 原文切片与检索索引

按 Phase 5 的原文边界覆盖所分析文本的全部场次；原作无分场时，根据实际时空或行动组织划分，并标明这是分析划分。使用本包 `knowledge-base/scripts/extract_scene.py`，其文件名为 `scenes/scene_{scene_id}.md`。保持原文，索引指向真实输出路径。

写 `dramatic_scene_index.jsonl`，每行一个场次，字段见分析契约。`genre / lang / source_medium` 对应现有查询器；`lang` 指当前切片文本语言。相同目录若有历史 `scene_index.json`，现行 JSONL 为权威。索引负责定位和召回，Phase 文件保留完整分析。

场景与索引落盘后，加载 `dialogue-kb-distill` 处理本剧目；它负责交互、群体交锋、独白、戏剧独语及 coverage。已有有效资料按其恢复规则继续。

## Phase B：角色参考

按用户范围和证据选择值得构建的角色：其选择、关系或声音能提供可迁移的理解时建包。通过宿主 skill 机制调用：

```text
/character-kb-distill build --novel-dir <本剧目绝对目录> --role <角色显示名>
```

人物系统使用 `phase2_roles.yaml`；角色键与显示名依实际数据匹配，输出 slug 沿现有 `character_map.json`。角色身份、欲望、知识与声音从原文提炼；`dramatic_role / voice_function / status_arc` 属于分析线索，不能直接变为人物自觉或永久行为禁令。

对白、独语、旁语、唱段和舞台指示按其对象与表演约定解读。观众得知的内容不自动成为其他角色所知；有独白或潜台词证据时再分析其作用。构建、定位与验证沿 character-kb-distill 契约，本技能不另列一套角色规则。

## Phase C：手艺标注（按需）

选取能回答当前手艺问题的场景，按 [手艺说明](references/analysis-schema.md#手艺标注) 写 `craft_notes/scene_{scene_id}_beats.md`。解释独语展开、上下场、转场、地位变化、声画或戏曲程式怎样影响人物与观众；节拍按实际变化划分。

需要结构化文风、技巧或灵感资料时，向 `kb-annotator` 传剧目目录名、实际 `annotated_by` 与所需入口。技巧消费者读取上述 beats 文件；缺所需场景标注时先补对应材料。全库聚类按独立的全库任务执行。

## 交接

`design-doc-reference` 查询原样的六层分析和角色资料；`scene-reference` 查询索引与原文；灵感提名保留戏剧专有机制。跨媒介参考须说明当前用途和需改变的表达载体，小说正文不能因故事机制相通就直接套用剧本排版。

现有产物包含 work-meta、六份 Phase、原文切片与索引，以及按范围完成的 characters、dialogue、craft_notes。运行时返回完成范围、实际路径及阻碍后续消费的缺口。
