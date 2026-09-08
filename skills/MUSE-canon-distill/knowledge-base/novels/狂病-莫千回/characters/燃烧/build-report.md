# Build Report — 狂病-莫千回·燃烧 — zhou-quan

- display_name: 周全
- role_slug: zhou-quan
- persona-desc: 灰色男主·自我牺牲型守护者（周全·狂病-莫千回·燃烧）
- mode: reference
- locator_count: 12
- 声音/边界跨场景: 声音 3 场景（S08/S06/S09）；边界跨 S04/S05/S06/S08/S09 5 场景
- canon-ending: 有（感染后浇汽油自燃身亡，不可逆物理死亡，不进弧光本体）
- built_from scenes: RS-S01/S04/S05/S06/S08/S09/S10
- 子目录: characters/燃烧/zhou-quan/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/燃烧/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/燃烧/zhou-quan` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界每条 bullet 带 locator；frontmatter 4 字段齐全；
  key-dialogues 12 section == SKILL locator 12 == build-meta.locator_count 12；character_map 含 {周全: zhou-quan}。

---

# Build Report — 狂病-莫千回·燃烧 — li-taitai

- display_name: 李太太
- role_slug: li-taitai
- persona-desc: 自私链式幸存者·承担反派功能的平民（李太太·狂病-莫千回·燃烧）
- mode: reference
- locator_count: 10
- 声音/边界跨场景: 声音 3 场景（S03/S04/S08）；边界跨 S03/S04/S08 3 场景
- canon-ending: 有（被感染者群撕裂身亡，声音递减死法，不可逆物理死亡，不进弧光本体）
- built_from scenes: RS-S01/S02/S03/S04/S06/S08（结构化依据另含 phase0 反派谱系）
- 子目录: characters/燃烧/li-taitai/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/燃烧/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/燃烧/li-taitai` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界每条 bullet 带 locator；frontmatter 4 字段齐全；
  key-dialogues 10 section == SKILL locator 10 == build-meta.locator_count 10；character_map 累加后含 {李太太: li-taitai}（与 周全 共存，per-part map 无冲突）。
