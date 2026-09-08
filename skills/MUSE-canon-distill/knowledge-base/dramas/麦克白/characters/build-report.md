# Build Report — 麦克白 — 第一批（4 角色）

**构建时间**：2026-05-24
**来源**：`knowledge-base/dramas/麦克白/`（drama-analysis Phase A 已落盘 phase0-5 yaml + 27 场切片 + dramatic_scene_index.jsonl）
**触发条件**：用户显式触发 drama-analysis Phase B（角色蒸馏）；候选池 7 名，本次先做最高优先级 4 名（phase3 spine 全 10 节点贡献者）
**构建路径**：character-kb-distill 蒸馏（工作区模式 — `--scenes-base dramas/麦克白` + `--character-map dramas/麦克白/characters/character_map.json`，跳过 novels/ 知识库默认路径）

## 已构建

| role_slug | display_name | dramatic_role | locator_count | has_canon_ending | Layer 1 gate |
|-----------|--------------|---------------|---------------|------------------|--------------|
| macbeth | 麦克白 | protagonist_and_tragic_villain | 20 | true (战死 + 首级悬挂) | ✅ exit 0 |
| lady-macbeth | 麦克白夫人 | co-protagonist_charge_engine | 16 | true (自杀，台下，Malcolm 间接报道) | ✅ exit 0 |
| banquo | 班柯 | mirror_pole_to_macbeth | 13 | true (A3S3 被刺 + A3S4/A4S1 鬼魂存续) | ✅ exit 0 |
| macduff | 麦克德夫 | avenger_and_kingmaker | 14 | **false** (剧终活态承担 kingmaker) | ✅ exit 0 |

## 未构建（pool 中暂未蒸馏的候选 + 原因）

| 候选 | 暂未蒸馏原因 |
|------|-------------|
| three-witches（三女巫） | 集体身份，单独 SKILL 包不合形态；声音是 trochaic tetrameter rhymed chant 的整体腔调而非个体；建议作为整体"chorus-character"另立专项格式，不走 character-kb-distill 默认模板 |
| malcolm（马尔康） | 角色弧光集中在 A4S3 一场 + A5S6/A5S7 的礼仪收尾，独立 voice 较薄；可作为第二批蒸馏（搭配剧本续写需要时） |
| porter（门房） | 全剧仅 A2S3 一场（132-141 行），是结构性 comic relief 而非有持续 voice 的角色；可作为"single-scene chorus comic"蒸馏，但优先级低 |
| 其他（Lady Macduff / Hecate / Ross / Lennox / Seyton / Doctor 等） | 都是结构功能位（messenger / chorus / collateral_victim），可在用户特定需求触发时按需补蒸 |

## 补充输入读取记录

- `pipeline/phase2_roles.yaml`：本次 4 角色全部主要字段来源（dramatic_role / desire / obstacle / voice_function / voice_markers / subtext_signature / status_arc / relationship_anchors）
- `pipeline/phase3_dramatic_spine.yaml`：本次蒸馏的"哪些场景属于核心 spine 节点"判定的依据
- `pipeline/phase0_conception.yaml`：用于校验 controlling_idea 与角色弧光的对齐（特别是 macbeth 与 macduff 的"controlling idea payoff"贡献）
- `pipeline/phase1_world_stage.yaml`：仅在 macbeth/macduff 的"身份与处境"段引用了 sacred_kingship / feudal_thanedom 等权力结构概念
- `scenes/*.md`：按各角色 build-meta `built_from` 字段所列——参见各角色 build-meta.yaml

## drama-analysis 媒介隔离备注

本批角色蒸馏的产物全部继承自 work-meta.yaml 的 medium-aware 设置：
- `source_medium: stage_play`
- `forbidden_phases: [novel_phase6_prose_fewshot]`
- `default_consumption.novel_writing.phase6: forbidden_as_prose_style`

下游消费方提醒：本批角色的"声音框架"维度大量描述 medium_grammar 特征（独白密度 / 韵文-散文切换 / 公开-私下声音分裂）——
这些是戏剧专属特征。若用于小说写作，需 transform 为对等的小说叙事手法（内心独白 / 自由间接引语 / 视角切换），
不可直接作为 prose few-shot 输入。
