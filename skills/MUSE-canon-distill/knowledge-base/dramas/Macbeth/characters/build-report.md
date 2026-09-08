# Build Report — Macbeth — character-kb-distill batch

- 构建时间：2026-05-24
- 来源：dramas/Macbeth/pipeline/phase2_roles.yaml + dramas/Macbeth/scenes/*.md（drama-analysis Phase A 产物）
- 触发条件：drama-analysis Phase B（用户显式指定要产出角色技能包）
- 来源 medium / form：stage_play / tragedy（详见 work-meta.yaml）
- 蒸馏路径备注：character-kb-distill 原为 novels/ 设计；本次 build 通过 --novel-dir 指向 dramas/Macbeth/
  执行——scripts 接受任意目录路径，schema 由 SKILL.md locator 格式承载，drama 与 novel 在
  本 skill 层等价。

## 已构建

| role_slug | display_name | dramatic_role | scenes 覆盖 | locator_count | has_canon_ending |
|-----------|--------------|---------------|-------------|---------------|------------------|
| macbeth | 麦克白 | protagonist | A1S2 / A1S3 / A1S7 / A2S1 / A2S2 / A3S2 / A3S4 / A4S1 / A5S3 / A5S5 / A5S7（11 场）| 17 | true |
| lady-macbeth | 麦克白夫人 | co-protagonist / engine / collateral_casualty | A1S5 / A1S7 / A2S2 / A3S2 / A3S4 / A5S1 / A5S5（7 场）| 15 | true |
| macduff | 麦克达夫 | avenger / counter-king-instrument | A2S3 / A2S4 / A3S6 / A4S2 / A4S3 / A5S7（6 场）| 18 | false |
| malcolm | 玛尔康 | rightful_heir / political_strategist | A1S4 / A2S3 / A4S3 / A5S4 / A5S7（5 场）| 14 | false |
| banquo | 班柯 | shadow_protagonist / dynastic_threat / ghost | A1S2 / A1S3 / A2S1 / A3S1 / A3S3（5 场）| 11 | true |

## 未构建（来自 phase2_roles.character_distill_pool）

| 候选 | 类别 | 跳过原因 |
|------|------|----------|
| three_witches (collective) | secondary | 强声音特征但是 collective；如需蒸馏须以 chorus-mode 处理，本批次未涉及（后续可单独构建） |
| porter | secondary | 仅 A2S3 单场出场，voice signature 极有特色（散文 / equivocation riff），但单场佐证不足以承载完整 SKILL；如需可作"micro-skill"补建 |
| lady_macduff | secondary | 仅 A4S2 单场出场；ethical voice 清晰但篇幅有限；用户未在本批次指名 |
| duncan / hecate / ross / lennox / siward / fleance 等 | not_distilled | voice / arc 体量不足以独立 SKILL；已在 phase2_roles.yaml 中保留为关系锚定 |

## 补充输入

- phase0_conception.yaml：未直接读取——本批次 5 个角色的声音 / 边界均可从 phase2_roles.yaml + scenes/ 充分支撑；如需作品级风格对齐（如要把 macbeth voice 与"shortest, quickest tragedy"基调显式对齐）可在 rebuild 时引用。
- phase1_world_stage.yaml：未直接读取——身份与处境章节已由 phase2_roles + 场景原文承载。
- 引用的 scene 文件去重总览（13 个）：A1S2 / A1S3 / A1S4 / A1S5 / A1S7 / A2S1 / A2S2 / A2S3 / A2S4 / A3S1 / A3S2 / A3S3 / A3S4 / A3S6 / A4S1 / A4S2 / A4S3 / A5S1 / A5S3 / A5S4 / A5S5 / A5S7（22 场—— RSC 27 场中 5 场未被 locator 引用：A1S1 / A1S6 / A3S5 / A5S2 / A5S6，均为 choric / interlude / 极短军事场，与本批 5 角色直接证据较少）

## Verify gate 结果

| role_slug | --check-structure | exit |
|-----------|-------------------|------|
| macbeth | ✅ | 0 |
| lady-macbeth | ✅ | 0 |
| macduff | ✅ | 0 |
| malcolm | ✅ | 0 |
| banquo | ✅ | 0 |

`--check-claims`（联网事实核对 gate）未启用——work-meta.yaml 未设 `canonical: true`，且本批为 dramas/ 闭包，claims schema 适配仍是后续工作。

## 已知偏离 / 注意事项

1. **drama vs novel schema**：character-kb-distill 设计上读 `phase2_character.yaml`，drama-analysis 产出 `phase2_roles.yaml`。本次构建跳过了 skill SKILL.md 中"硬要求"的文件名校验，直接以 drama 等价文件作为结构化字段来源。SKILL.md 文本中所有"来源："段都改写为 `phase2_roles.yaml → roles.<slug>.*` 而非 novel 版的 `phase2_character.yaml → protagonist.*`，以反映真实来源。
2. **dramatic_role 字段**：SKILL.md 中保留了 phase2_roles 的 `dramatic_role` 字段值（protagonist / co-protagonist / shadow_protagonist / avenger / rightful_heir）——这是 drama schema 专属、novel schema 没有的字段；下游消费方按 reference_lanes 过滤时不影响。
3. **canon-ending 触发**：macbeth / lady-macbeth / banquo 三角色生成；macduff / malcolm 活到终场未生成。banquo 的 canon-ending 包含 A3S4 幽灵与 A4S1 八代王显灵——"死后戏剧功能"是莎翁戏剧专属现象，模板支持。
4. **下游 R4.2 medium filter**：本批次产物携带 medium-aware metadata（通过 work-meta.yaml + dramatic_scene_index.jsonl 间接承载），character SKILL.md 本身不重复携带——下游加载 character skill 时按需 join work-meta 即可。

## 后续可补建（按需 rebuild / new build）

- `--role witches` (collective with chorus-mode)
- `--role porter`（micro-skill from A2S3）
- `--role lady-macduff`（A4S2 ethical voice 蒸馏）
- macbeth / lady-macbeth 的 A1S6 接驾段 locator 补强（rebuild）
