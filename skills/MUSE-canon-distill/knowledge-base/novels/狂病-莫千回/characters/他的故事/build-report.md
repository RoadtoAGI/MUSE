# 《他的故事》篇 — 单篇人物蒸馏 build-report

- 篇：他的故事（scene 前缀 TG）
- 模式：reference（知识库参考包）
- per-part map：`characters/他的故事/character_map.json`（本轮新建为 `{}` 后逐个 build 写入，最终 3 条）
- builder：character-kb-distill；构建脚本 build_character_references.py + verify_character_skills.py --check-structure

## 蒸馏了谁

| slug | display_name | desc（人设类型原型标签） | has_canon_ending | locator_count | verify |
|---|---|---|---|---|---|
| `lao-zhang` | 老张 | 拧巴反英雄·第一人称录音遗书叙述者（老张·狂病-莫千回·他的故事） | true | 16 | exit 0 ✅ |
| `wang-huayi` | 汪华依 | 游戏化信念理想主义者·末日免疫者（汪华依·狂病-莫千回·他的故事） | true | 12 | exit 0 ✅ |
| `cui-zhouping` | 崔周平 | 希望提供者·末日小队的精神支柱（崔周平/小崔·狂病-莫千回·他的故事） | true | 9 | exit 0 ✅ |

每个角色目录含：SKILL.md / build-meta.yaml / references/key-dialogues.md（脚本切片）/ references/canon-ending.md（三人均不可逆终局）。

### 取舍依据
- `lao-zhang`、`wang-huayi`：_candidates.md 标"蒸馏建议：值得做"——本篇双主角对照（拧巴 vs 纯粹），信息密度极高，且分别是系列"拧巴反英雄第一人称录音遗书 POV"与"唯一被纯粹定义的理想主义者 + 免疫者"的典型原型，必做。
- `cui-zhouping`：_candidates.md 标"可做"，理由是"希望提供者"功能性角色具二创原型价值（与《燃烧》周全功能位错但精神同源——给盲目/拧巴者提供活下去理由的人）。按任务"也做有二创原型价值的可做角色"纳入。

### has_canon_ending 判定（均回 scene 原文核对，非凭印象）
- `lao-zhang`：被感染者围困乡镇药店、生死悬置、录下遗言托付陌生人（scene_TG-S12.md L47-L61）→ 不可逆终局（被困/大概率死，文本刻意悬置）。
- `wang-huayi`：月儿洞被腐臭感染者咬伤（S11 死因伏笔）→ 伤口化脓发烧、被弃农家乐、大概率已死（S12 L3-L33）→ 不可逆终局。
- `cui-zhouping`：树下自缢身亡，以闪前方式泄露（S10 L15-L19）→ 不可逆终局（物理死亡）。
- 弧光本体均只描内在转变；物理终局（围困/化脓死/自缢）一律隔离到各自 references/canon-ending.md。

## 跳过了谁（+原因）

| 角色 | _candidates 建议 | 跳过原因 |
|---|---|---|
| 死老鼠 | 可做但非必需 | "怂者幸存"功能性样本，非必需，按蒸馏范围跳过（纯功能性"可做但非必需"不做）。 |
| 杨老头 | 不蒸馏 | 信息不足，功能性配角（结局未明确）。 |
| 郑新宇 | 不蒸馏 | 功能性 + 单场景（铁桶活烹弃人链实例）。 |
| 养老头 | 不蒸馏 | 信息不足（仅"安全套黑色幽默"单点）。 |
| 打电话大妈 | 不蒸馏 | 功能性道德困境承担者；其"打电话"桥段宜作 TG-S04 场景 few-shot，非角色蒸馏对象。 |
| 厕所兼职男（无名） | 不蒸馏 | 单场景、无姓名无前史，"灾难无差别"纯示例。 |

跨篇人物：本篇无已知跨篇人物正面出场，全部为本篇 local cast，无重建已建跨篇人物之虞。

## 遗留问题
- `lao-zhang` / `wang-huayi` 在 _candidates.md 与 phase3 cross_chapter_hooks 中均标"本篇候选 / 局部跨篇候选"（汪华依"免疫者"身份、录音笔接续点为弱钩）。本轮按"本篇人物"蒸馏，per-part map 隔离在 `characters/他的故事/character_map.json`，未升格跨篇、未写根级跨篇 map。若后续篇章出现"捡到龙门客栈农家乐录音笔 / 护送腿伤免疫女子"的接续证据，再评估是否升格。
- `cui-zhouping` 自缢的"下半身被野物啃成白骨"细节落在原文 line 289，该行未被切入任何 TG 场景文件（位于 S03 行尾 199 与 S04 行首 295 之间的未切片区间），canon-ending 仅以 scene 文件内可定位的 S10 闪前泄露段取证；物理细节描述以散文带过、不强加无 scene 来源的 locator。
- 软建议单点支撑项已在各自 build-meta.coverage_note 注明（lao-zhang 边界#3、wang-huayi 免疫者身份与外貌细节、cui-zhouping 功能性配角台词量有限）。
