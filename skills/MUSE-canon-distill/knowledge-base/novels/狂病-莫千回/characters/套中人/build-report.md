# 《套中人》篇 — 单篇人物蒸馏 build-report

篇 = 套中人 / scene 前缀 PREFIX = TZ / 模式 = reference / 本篇全新蒸馏。
per-part map = `characters/套中人/character_map.json`（已含 4 条，逐个 build 写入）。

## 蒸馏了谁

| slug | display_name | desc（人设类型原型标签） | has_canon_ending | locator_count | verify |
|---|---|---|---|---|---|
| `hong-baoshan` | 洪宝山 | 壮胆型灰色守护者父亲（洪宝山·狂病-莫千回·套中人） | true | 12 | exit 0 ✅ |
| `tang-zhilin` | 唐志林 | 末日哲思型转达者·镜像创伤的小学老师（唐志林·狂病-莫千回·套中人） | false | 13 | exit 0 ✅ |
| `wan-qing` | 婉清 | 善意者祭品·灾难献祭的幼童（婉清·狂病-莫千回·套中人） | true | 6 | exit 0 ✅ |
| `duilou-5lou-zhuhu` | 对楼5楼住户 | 网络暴力实体化的操纵型平庸之恶（对楼5楼住户·狂病-莫千回·套中人） | true | 7 | exit 0 ✅ |

蒸馏取舍依据 `_candidates.md` 的"蒸馏建议"：
- **值得做**：洪宝山、唐志林 —— 全部蒸馏。
- **可做（有二创原型价值）**：婉清（善意者祭品 / 轻盈意象写残忍死的样本）、对楼5楼住户（网络暴力人格末日实体化的反派变体）—— 均蒸馏。

canon-ending.md 已为 3 个 has_canon_ending: true 角色生成（hong-baoshan / wan-qing / duilou-5lou-zhuhu），
唐志林（结局开放，骑摩托南下"走到不能走的那天"，活态离场）不生成。
3 个终局均回 scene 原文核对确认为不可逆物理死亡（hong-baoshan TZ-S10:L15-L31 断后惨死；
wan-qing TZ-S03:L15-L17 洒水车碾碎；duilou-5lou-zhuhu TZ-S11:L95 四肢折断全身塞洞）。

## 跳过了谁（+原因）

| 角色 | 原因 |
|---|---|
| 婉清奶奶 | `_candidates.md` 标"不蒸馏" —— 外视角功能性配角，无独立人设原型价值。 |
| 徐永恒 / 欧星旭（士兵） | `_candidates.md` 列入"跨篇人物（待确认）" —— 具名军人 + 具体连队/基地坐标，疑跨篇；当前仅登记不蒸馏，待后续篇章再现军方建制后再定归属。蒸馏前还需核对"徐永恒/欧星旭"是否同一人（狗牌歧义）。 |
| 罗允（真） | 跨篇主角级，已建于顶层 `characters/luo-yun/`。本篇尾段第三次实质性登场（line 695），归属跨篇，**绝不重建**。 |
| 洪扬（本篇 POV 主角） | **已建于顶层跨篇 `characters/hong-yang/`**（desc：全身包裹的自我封闭者·罗允的沉默搭档/现实主义对照镜）。`_candidates.md` 的撞名待确认（hong-yang-tz）经 phase0 evidence_basis（line 19：line 695 = 罗允+洪扬搭档关系起点；reading_strategy："套中人是洪扬 origin 前传"）+ 既有 hong-yang/build-meta.yaml coverage_note 确认 = **同一人时间线前置（可能性 1）**，slug 已统一为 `hong-yang`，built_from 已含 TZ-S02/S10/S11 等套中人场景。本篇**不重建**，不另建 hong-yang-tz。 |

## 遗留问题

1. **徐永恒/欧星旭跨篇归属未决**：若后续篇章再现"越纽市丰台镇山区连队 / 勒德州空军基地"军方建制，应在完整蒸馏阶段统一归跨篇 slug（待确认是否一人）；洪扬带走其狗牌（承诺"送还有关部门"）是潜在跨篇钩。本篇暂不蒸馏。
2. **洪扬 slug 统一已落定**：本轮确认 `hong-yang-tz` 仅为 `_candidates.md` 阶段的 part-local 占位，**不**落地为独立 slug；跨篇 `hong-yang` 已是权威条目，本篇主角戏份作为其 origin 前传已被该跨篇档覆盖。
3. **唐志林南下线开放钩**：其"载母亲遗照南下 S 市晴天明珠塔坐船"的死亡奔赴式愿望可能与《死亡奔赴》篇主题相通（见 phase3 cross_chapter_hooks open_lores）；属世界观钩，不影响本角色单篇蒸馏完整性。
4. **locator 去重计数口径**：build_character_references.py 对 SKILL.md 内重复 locator 去重后生成 key-dialogues section，故 build-meta.locator_count 取"唯一 locator 数"（hong-baoshan 原文 15 处引用、去重后 12）。4 个角色 build-meta.locator_count 均已与 verify 的唯一计数对齐，verify --check-structure 全部 exit 0。
