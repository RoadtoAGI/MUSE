# Build Report — 狂病-莫千回·地铁 — lu-xiake

- display_name: 陆霞克
- role_slug: lu-xiake
- persona-desc: 黑色幽默吟游诗人·反英雄断后型守护者（陆霞克·狂病-莫千回·地铁）
- mode: reference
- locator_count: 14
- 声音/边界跨场景: 声音 3 场景（S03/S05/S11）；边界跨 S05/S06/S11 3 场景
- canon-ending: 有（山顶弹完最后一首歌后吉他抡向沦陷的杨和修、被感染者群杀死，不可逆物理死亡，自尽断后；不进弧光本体）
- built_from scenes: DT-S01/S03/S05/S06/S08/S11（结构化依据另含 phase0 controlling_idea candidate_b 反英雄侧对照）
- 子目录: characters/地铁/lu-xiake/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/地铁/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/地铁/lu-xiake` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界 5 条每条带 locator；frontmatter 4 字段齐全；
  key-dialogues 14 section == SKILL 唯一 locator 14 == build-meta.locator_count 14；character_map 含 {陆霞克: lu-xiake}。

---

# Build Report — 狂病-莫千回·地铁 — yang-hexiu

- display_name: 杨和修
- role_slug: yang-hexiu
- persona-desc: 好人沦陷载体·理性自救者反成最致命猎手（杨和修·狂病-莫千回·地铁）
- mode: reference
- locator_count: 15
- 声音/边界跨场景: 声音 3 场景（S05/S07/S10，覆盖理性期+沦陷期两副嗓子）；边界跨 S06/S10 2 场景
- canon-ending: 有（涂血伪装失败被感染 → 暗杀刘敏 + 反向猎杀陆霞克陈雨琪 → 沦陷为保留智力的嗜虐感染者，篇末带感染者群游动；不可逆人格沦陷，不进弧光本体）
- built_from scenes: DT-S01/S05/S06/S07/S08/S10（主题型人设依据 phase0 controlling_idea candidate_b，杨和修为该机制核心载体）
- 子目录: characters/地铁/yang-hexiu/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/地铁/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/地铁/yang-hexiu` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界 5 条每条带 locator；frontmatter 4 字段齐全；
  key-dialogues 15 section == SKILL 唯一 locator 15 == build-meta.locator_count 15；character_map 累加后含 {杨和修: yang-hexiu}。
- 备注: 候选清单标杨和修跨篇归属（待累积其他篇章证据统一蒸馏）；本包是其完整沦陷弧光的唯一深度载体（《地铁》），作为单篇 reference 蒸馏，与未来根级跨篇包由 地铁 子目录 + per-part map 隔离。

---

# Build Report — 狂病-莫千回·地铁 — xu-haishui

- display_name: 徐海水
- role_slug: xu-haishui
- persona-desc: 被困的上帝视角见证者·制度性善意的无能守护者（徐海水·狂病-莫千回·地铁）
- mode: reference
- locator_count: 8
- 声音/边界跨场景: 声音 3 场景（S07/S10/S11）；边界跨 S07/S10 2 场景
- canon-ending: 无（终局仅被暗示——S11:L23 "再也帮不到" 发送时间半小时前 + 窗外挤满感染者；phase3 open_lores 标注"暗示已遇难或沦陷"但无明示。按"宁可漏不可错"不产 canon-ending.md，has_canon_ending: false）
- built_from scenes: DT-S07/S10/S11
- 子目录: characters/地铁/xu-haishui/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/地铁/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/地铁/xu-haishui` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界 5 条每条带 locator；frontmatter 4 字段齐全；
  key-dialogues 8 section == SKILL 唯一 locator 8 == build-meta.locator_count 8；character_map 累加后含 {徐海水: xu-haishui}。

---

# Build Report — 狂病-莫千回·地铁 — liu-min

- display_name: 刘敏
- role_slug: liu-min
- persona-desc: 易受惊吓的普通受害者·关键死亡用省略承担的同行者（刘敏·狂病-莫千回·地铁）
- mode: reference
- locator_count: 8
- 声音/边界跨场景: 声音 3 场景（S01/S03/S10）；边界跨 S03/S10 2 场景
- canon-ending: 有（进风井口逃生通道告别杨和修时被刚沦陷的杨和修暗杀；死亡用"省略 + 完成态"承担——徐海水群消息转述 + 染血人头扔下；不可逆物理死亡，不进弧光本体）
- built_from scenes: DT-S01/S03/S08/S10
- 子目录: characters/地铁/liu-min/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/地铁/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/地铁/liu-min` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界 3 条每条带 locator；frontmatter 4 字段齐全；
  key-dialogues 8 section == SKILL 唯一 locator 8 == build-meta.locator_count 8；character_map 累加后含 {刘敏: liu-min}。
- 备注: 纯功能性角色（候选清单"可做但非必需"），信息密度低-中，按"普通受害者 + 关键死亡用省略承担"原型蒸馏，深度有限但结构完整。
