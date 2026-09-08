# Build Report — 狂病-莫千回·狂人日志 — zhao-weisheng

- display_name: 赵维胜
- role_slug: zhao-weisheng
- persona-desc: 道德感被亲情绑架的好人·被精神虐杀气死的受害者（赵维胜·狂病-莫千回·狂人日志）
- mode: reference
- locator_count: 11
- 声音/边界跨场景: 声音 3 场景（S05 自我打气+道谢 / S08 丧子辱骂 / S10 临终诅咒）；边界跨 S05/S08/S09/S10 4 场景
- canon-ending: 有（被吴先生"活活气死"，非物理外伤的不可逆死亡，莫千回式"非物理死亡"顶点，不进弧光本体）
- built_from scenes: KR-S04/S05/S08/S09/S10（结构化依据另含 phase3_spine 狂人日志 + phase0 受害者侧）
- 子目录: characters/狂人日志/zhao-weisheng/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/狂人日志/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/狂人日志/zhao-weisheng` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界 5 条每条带 locator；frontmatter 4 字段齐全；
  key-dialogues 11 section == SKILL locator 11 == build-meta.locator_count 11；character_map 含 {赵维胜: zhao-weisheng}。

---

# Build Report — 狂病-莫千回·狂人日志 — li-wei

- display_name: 李伟
- role_slug: li-wei
- persona-desc: 渴望家庭归属的孤儿·被反派剧本完整玩弄至精神崩溃的猎物（李伟·狂病-莫千回·狂人日志）
- mode: reference
- locator_count: 9
- 声音/边界跨场景: 声音 3 场景（S06 家庭憧憬 / S08 丧偶辱骂 / S09 疯语哭笑）；边界跨 S06/S08/S09 3 场景
- canon-ending: 有（精神崩溃、不可逆疯癫——吴先生眼中"猪仔残次品，没有玩乐价值"，精神性死亡，不进弧光本体）
- built_from scenes: KR-S04/S06/S07/S08/S09（S07 信任顶点作过程证据；结构化依据另含 phase3_spine pov_structure L2 李伟限知 + phase0 受害者侧）
- 子目录: characters/狂人日志/li-wei/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/狂人日志/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/狂人日志/li-wei` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界 5 条每条带 locator；frontmatter 4 字段齐全；
  key-dialogues 9 section == SKILL locator 9 == build-meta.locator_count 9；character_map 累加后含 {李伟: li-wei}。

---

# Build Report — 狂病-莫千回·狂人日志 — zhang-lulu

- display_name: 张露露
- role_slug: zhang-lulu
- persona-desc: 直觉识破反派却被身边人劝服的预警者·真话被理性消解的反讽受害者（张露露·狂病-莫千回·狂人日志）
- mode: reference
- locator_count: 7
- 声音/边界跨场景: 声音核心集中于 S06（多段落）；边界跨 S06/S08；弧光终点延伸至 S08。识破者集中登场角色，跨场景稳定性弱于另两角，已在 coverage_note 标注
- canon-ending: 有（被感染的赵小军咬死，完成态"脖插水果刀+眼眶塞蜡烛"；死后被开膛+赵小军缝入肚子的"升华"意象，不可逆物理死亡，不进弧光本体）
- built_from scenes: KR-S04/S06/S08/S09（结构化依据另含 phase3_spine layer_2_fake_trust + arc_4 反讽装置 + phase0 受害者侧）
- 子目录: characters/狂人日志/zhang-lulu/
- 脚本流（子目录模式）:
  - build: `--scenes-base NOVEL` + `--character-map characters/狂人日志/character_map.json`（不用 --novel-dir）→ exit 0
  - verify: `--role-dir characters/狂人日志/zhang-lulu` + `--character-map ...` `--check-structure` → exit 0
- 结构自检: SKILL.md 6 段齐全且每段 ≥1 locator；边界 4 条每条带 locator；frontmatter 4 字段齐全；
  key-dialogues 7 section == SKILL locator 7 == build-meta.locator_count 7；character_map 累加后含 {张露露: zhang-lulu}（与 赵维胜/李伟 共存，per-part map 无冲突）。

---

## 跳过说明（本轮不蒸）

- 罗允（luo-yun）/ 吴先生（wu-xiansheng）：跨篇人物，归属根级 characters/，本篇只识别不在本目录建档。
- 赵小军 / 老康 / 豆豆鞋青年二人组 / 夫妻猪仔：纯功能性剧本道具或已死且全程缺席，信息不足，按 _candidates.md「不蒸馏」判定跳过。
