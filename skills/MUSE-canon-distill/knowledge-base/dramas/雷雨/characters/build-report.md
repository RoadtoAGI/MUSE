# Build Report — 雷雨 — 角色 Skill 批量蒸馏

**构建时间**：2026-05-24
**来源**：[`drama-analysis`](../../../../../.claude/plugins/cache/muse-canon-distill/muse-canon-distill/0.4.1/skills/drama-analysis) Phase B（character-kb-distill 工序适配 `dramas/` 路径）
**底本**：`dramas/雷雨/full_text.md`（曹禺四幕悲剧含序幕 + 尾声完整版）
**触发条件**：drama-analysis Phase A 已完成 + Phase B 进入角色蒸馏阶段
**篇幅路径**：剧本约 10 万字符 = 6 个场景文件（PROLOGUE / A1-A4 / EPILOGUE）一次性可读，无需流式

## 已构建（8 角色全部已蒸馏）

| display_name | role_slug | locator 数 | scenes 覆盖 | has_canon_ending |
|---|---|---|---|---|
| 周朴园 | zhou-puyuan | 15 | A1 / A2 / A4 | false（十年后仍在世） |
| 周蘩漪 | zhou-fanyi | 13 | A1 / A2 / A4 | true（不可逆精神疯癫） |
| 周萍 | zhou-ping | 11 | A1 / A2 / A3 / A4 | true（开枪自杀） |
| 周冲 | zhou-chong | 14 | A1 / A3 / A4 | true（触电死亡） |
| 鲁侍萍 | lu-shiping | 14 | PROLOGUE / A2 / A4 | true（不可逆痴呆） |
| 鲁大海 | lu-dahai | 12 | A1 / A2 / A3 / A4 | true（不可逆失踪） |
| 鲁四凤 | lu-sifeng | 13 | A1 / A2 / A3 / A4 | true（触电死亡） |
| 鲁贵 | lu-gui | 12 | A1 / A3 / A4 | false（剧本未明确给终局） |

## 未构建（候选池中无遗漏）

剧本主要人物 8 名（rulesheet `phase2_roles.yaml.roles[*]` 全部）已全部构建。
chorus / 功能性角色（姑奶奶甲、姑奶奶乙、姊姊、弟弟、老仆、仆人若干）未构建——
他们是 chorus_functional_roles，dramatic_role 非主线性，按 character-kb-distill skill §候选 pool 准则跳过。

## 补充输入

- `dramas/雷雨/pipeline/phase2_roles.yaml`（角色结构化数据来源）
- `dramas/雷雨/pipeline/phase0_conception.yaml`（用于声音风格对齐 - dramatic_engine + theatricality_notes）
- `dramas/雷雨/pipeline/phase1_world_stage.yaml`（用于角色处境描述 - power_structure + key_offstage_action）
- `dramas/雷雨/scenes/scene_*.md`（按 locator 实际引用的 6 个 scene 文件）

## medium 隔离备注

雷雨为 `source_medium: stage_play` / `dramatic_form: tragedy`。
所有 8 角色 SKILL.md 的"声音框架"段已按 drama-analysis Phase B 特别提示标注独白 / 潜台词 / 上下场调度的戏剧化特征——
不同于 novel-analysis 的"叙述者描写 voice"。
角色 Skill 包默认 `reference_lanes: [story_design, scene_function, medium_grammar, dramatic_surface_style]`，
**禁止**作为 `novel_phase6_prose_fewshot` 使用——
该约束已在 `dramas/雷雨/dramatic_scene_index.jsonl` 与 `work-meta.yaml` 中显式落字段。

## 后续步骤

- 跑 `build_character_references.py` 按 locator 切出 `references/key-dialogues.md`（每角色一份）
- 由于本仓库当前 character-kb-distill 脚本针对 `novels/` 路径硬编码部分逻辑，
  `dramas/` 下的 `verify_character_skills.py --check-structure` 需要 `--novel-dir dramas/雷雨` 适配——
  适配性见各 SKILL.md 字段完整性的人工核查。
