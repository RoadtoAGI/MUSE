# Build Report — 狂病-莫千回 — luo-yun

## 罗允（luo-yun）

- **构建时间**：2026-05-29T15:58:07+08:00
- **构建器**：character-kb-distill（reference 模式）
- **来源（built_from）**：
  - `pipeline/phase2_character.yaml`（protagonist 罗允 full 条目 — 结构化字段唯一来源）
  - `scenes/scene_XX-S11.md`（学校 · 首登场）
  - `scenes/scene_RS-S10.md`（燃烧 · 救盲女、转达周全遗言）
  - `scenes/scene_SB-S11.md`（死亡奔赴 · 读遗书塞进笔记本 + 洪扬温差）
  - `scenes/scene_YY-S08.md`（医院 · 救盲女失败 + 决定奔西北科考站）
  - `scenes/scene_HJ-S13.md`（黄金国 · 奔死动机袒露 + 结尾再启程）
  - `scenes/scene_EE-S05.md`（恶 · 假罗允诱杀伪装 — 反向对位佐证）
  - `scenes/scene_BX-S08.md`（不详 · 假罗允毁队 — 反向对位佐证）
- **触发条件 / Layer 3 状态**：本系列无 `novel-meta.yaml`（非 canonical），按 reference 模式跳过 claims.yaml（2f/2g）；罗允为活态主角，弧光按"已完成的内在转变轨迹"写，不生成 `canon-ending.md`（`has_canon_ending: false`）。
- **补充输入（精读 phase / scene）**：
  - phase 文档：`pipeline/phase2_character.yaml`（全字段来源）。
  - 真罗允证据场景精读：XX-S11、RS-S10、KR-S01/S02/S11（狂人日志框层 POV）、SB-S11、YY-S02/S03/S05/S06/S07/S08、HJ-S01、HJ-S13、TZ-S11。
  - 黄金国 13 场按需精读关键场（HJ-S01 开篇、HJ-S13 line 825 动机 + 结尾），HJ-S02~S12 多为大厦内部情节推进，作背景对齐未逐字精读。
  - 假罗允反向对位：EE-S05、BX-S08（仅用于"不冒充他人 / 不以正义感为伪装诱杀"两条边界的否证佐证，未用于刻画真罗允人格）。

### 已构建表

| 角色 | role_slug | mode | locator_count | has_canon_ending | structure gate |
|------|-----------|------|---------------|------------------|----------------|
| 罗允 | luo-yun | reference | 13 | false | ✅ exit 0 |
| 吴先生 | wu-xiansheng | reference | 16 | false | ✅ exit 0 |
| 陈雨琪 | chen-yuqi | reference | 12 | true | ✅ exit 0 |
| 洪扬 | hong-yang | reference | 14 | false | ✅ exit 0 |

# Build Report — 狂病-莫千回 — wu-xiansheng

## 吴先生（wu-xiansheng）— 合并了石浩洋

- **构建时间**：2026-05-29T16:30:00+08:00
- **构建器**：character-kb-distill（reference 模式）
- **合并决策（关键）**：吴先生（《狂人日志》录音机主人 / 录音自白主体）＝ 石浩洋（《医院》诈死后操盘的录音机杀手）
  ＝《恶》全程伪装"罗允"系统性诱杀整队者，三者经用户拍板确认为**同一人**，统一蒸馏为 `wu-xiansheng`。
  `character_map.json` 把"吴先生"与"石浩洋"双键都指向 `wu-xiansheng`；display_name 用"吴先生"。
- **活态反派 → 不生成 canon-ending.md**（`has_canon_ending: false`）：《恶》结尾他牵林东青隐入山林，
  用同套"带孩子的可靠男人"话术接触下一支队伍，循环不止，无不可逆终局。reference 模式无 novel-meta.yaml，
  跳过 claims.yaml；不产 state.md。
- **来源（built_from）**：
  - `pipeline/phase2_character.yaml`（antagonists 吴先生 + 石浩洋条 + contrast_axes 真假罗允轴 — 结构化字段来源）
  - 《狂人日志》KR-S01/S03/S09/S10/S11（核心建档篇：voice / 拒绝感染 / 升华 / 起源 / "我可以是任何人"）
  - 《恶》EE-S05/S10/S11（伪装"罗允"最完整演示：盗用模板入队 / 自陈"更纯粹" / 排座次 + 隐入山林）
  - 《医院》YY-S10（石浩洋＝录音机杀手揭示 / 林东青精神延续 / 评罗允城府太浅 / 想慢慢玩弄）
- **三篇证据处理**：
  - 《恶》里自称/标注"罗允"的男人 = 吴先生本人伪装（盗用罗允之名正是其 MO），有效证据。
  - 《医院》里的"石浩洋" = 其另一身份/本名，有效证据。
  - 真罗允（luo-yun，已蒸馏）的声音 / 欲望 / 性格真相 / 弧光不掺入本包；本包不引用真罗允本人画像证据。
- **背景对齐未取 locator**：石浩洋"讲义气硬汉"面具戏 YY-S02/YY-S03/YY-S07、EE 内伪装诱杀细节 EE-S06/S08/S09。
- **structure gate**：`verify_character_skills.py --check-structure` exit 0（locator 数 16 == key-dialogues section 数 == build-meta.locator_count）。

---

# Build Report — 狂病-莫千回 — chen-yuqi

## 陈雨琪（chen-yuqi）

- **构建时间**：2026-05-29T16:30:00+08:00
- **构建器**：character-kb-distill（reference 模式）
- **来源（built_from）**：
  - `pipeline/phase2_character.yaml`（supporting_cast 陈雨琪 concise 条目 + 地铁/_candidates.md — 结构化字段来源）
  - `scenes/scene_DT-S01.md`（地铁 · 初遇陆霞克、身份/旷课/吐槽声音）
  - `scenes/scene_DT-S03.md`（地铁 · 目睹车厢虐杀跌坐、白眼吐槽）
  - `scenes/scene_DT-S08.md`（地铁 · 给家人打电话、陆小虎家庭线）
  - `scenes/scene_DT-S10.md`（地铁 · 拽出陆霞克 + 推门锁住沦陷的杨和修）
  - `scenes/scene_DT-S11.md`（地铁 · 压力命令式、接受陆霞克断后、末段遇陆小虎守口如瓶 POV 转交）
  - `scenes/scene_YY-S03.md`（医院 · 骂张华侮辱军队）
  - `scenes/scene_YY-S05.md`（医院 · 第三方观察 中性/强壮/被纳入嫌疑）
  - `scenes/scene_YY-S09.md`（医院 · 被侯楚霖虐杀终局 — 拆入 canon-ending.md，未取人格本体 locator）
- **触发条件 / Layer 3 状态**：本系列无 `novel-meta.yaml`（非 canonical），按 reference 模式跳过 claims.yaml；不产 state.md。陈雨琪在《医院》YY-S09 被感染者侯楚霖虐杀致死（灶台上四肢砍断、开膛、五脏外流，原文确证"正是陈雨琪"且尸体随后被当凶器），为不可逆物理终局，按"宁可漏不可错"判定 `has_canon_ending: true`，生成 `references/canon-ending.md`；物理死亡不写入弧光本体，弧光仅描《地铁》内在转变（"最普通幸存者"→ 守口如瓶的转达者）。
- **补充输入（精读 phase / scene）**：
  - phase 文档：`pipeline/phase2_character.yaml`（supporting_cast / contrast / relationships）。
  - 识别细节：`characters/地铁/_candidates.md`、`characters/医院/_candidates.md`（陈雨琪 sighting + 死法登记）。
  - 地铁主 POV 精读：DT-S01/S03/S08/S10/S11（身份/声音/欲望/性格真相/弧光证据最富）。
  - 医院群像精读：YY-S03（骂张华）、YY-S05（外观描写）、YY-S09（虐杀终局 + 时序钩核对）。
- **跨篇同一性 / 时序**：《地铁》陈雨琪（主 POV，活到篇末）与《医院》陈雨琪（群像配角并死亡）经原文确认为同一跨篇人物（视角反转线呼应、二人均与陆小虎绑定），《医院》为《地铁》之后辗转至机场旁医院的延续，无同名歧义。
- **structure gate**：`verify_character_skills.py --check-structure` exit 0（locator 数 12 == key-dialogues section 数 12 == build-meta.locator_count 12；6 段各 ≥1 locator；边界 4 条 bullet 各带 locator；character_map 含 陈雨琪→chen-yuqi）。

---

# Build Report — 狂病-莫千回 — lu-xiaohu

- **角色**：陆小虎（lu-xiaohu）— 陆霞克的双胞胎弟弟；跨《地铁》《医院》两篇的配角，戏份相对少。
- **定位**：《地铁》line393 末段 POV 接管（陈雨琪把视角转交给他——戏剧性反讽，他不知陈雨琪为何对他特别）；《医院》机场地勤幸存者 + 火车站口述者之一，后扑感染者侯楚霖被咬同归于尽身亡。
- **模式**：reference 模式（仅供加载，不扮演）。产 SKILL.md + references/key-dialogues.md + references/canon-ending.md + build-meta.yaml；不产 claims.yaml / state.md。
- **locator_count**：6（distinct）。覆盖篇：《地铁》+《医院》两篇；覆盖场景文件：scene_DT-S08 / scene_DT-S11 / scene_YY-S05 / scene_YY-S07 / scene_YY-S09（5 个场景文件）。
- **六段 locator 分布**：
  - 身份与处境：DT-S08:L11-L13 / YY-S05:L13-L15 / YY-S07:L37-L39（3）
  - 核心欲望：DT-S11:L45-L47 / YY-S09:L15-L19（2）
  - 性格真相：YY-S07:L37-L39 / YY-S09:L15-L19（2）
  - 声音框架：DT-S11:L45-L47 / YY-S09:L3-L11（2）
  - 边界（每条 bullet 带 locator）：YY-S09:L15-L19 / YY-S09:L3-L11 / YY-S05:L13-L15 / DT-S11:L45-L47（4 bullet）
  - 弧光：DT-S11:L45-L47 / YY-S09:L15-L19（2）
  - 去重后 distinct locator = 6（DT-S08:L11-L13、DT-S11:L45-L47、YY-S05:L13-L15、YY-S07:L37-L39、YY-S09:L3-L11、YY-S09:L15-L19）。
- **canon-ending**：has_canon_ending=true，产 references/canon-ending.md。判定依据《医院》原文行 531-537（scenes/scene_YY-S09.md:L21-L27）——被完全感染的侯楚霖咬伤后中招、被肠子缠颈，刘医生当场判定"已被咬、救不回来"，随后"脸色逐渐变青、倒在地上"身亡，为不可逆物理死亡终局（"宁可漏不可错"）。物理死亡拆入 canon-ending.md，弧光本体只描内在转变。
- **戏份少的单点维度处理**：核心欲望/弧光"被在乎"主线主要靠 DT-S11:L45-L47 末段内心独白单点承载（全篇唯一直陈其内在渴望处），辅以 YY-S09:L15-L19 行动印证；声音框架以内心独白 + 动作外化两场取证（直接台词仅一声"雨琪"）。均已在 build-meta.coverage_note 注明单点支撑。
- **角色区分**：陆小虎 ≠ 双胞胎哥哥陆霞克（lu-xiake，单篇人物，本次不蒸馏）。DT-S08/DT-S11 中陆霞克言行仅用于定位陆小虎的"被惦念者/POV 承接者"处境，未刻画陆小虎人格。
- **来源（built_from）**：pipeline/phase2_character.yaml（supporting_cast 陆小虎条）+ scene_DT-S08 / scene_DT-S11 / scene_YY-S05 / scene_YY-S07 / scene_YY-S09。
- **脚本结果**：build_character_references.py exit 0；verify_character_skills.py --check-structure exit 0（locator 数 6 == key-dialogues section 数 6 == build-meta.locator_count 6；边界每条 bullet 有 locator；6 段各 ≥1 locator；character_map.json 含 陆小虎→lu-xiaohu）。

---

# Build Report — 狂病-莫千回 — hong-yang

## 洪扬（hong-yang）

- **构建时间**：2026-05-29T16:21:36+08:00
- **构建器**：character-kb-distill（reference 模式）
- **角色定位**：罗允固定搭档 + 现实主义对照镜。《套中人》是其主角篇 / 前传（"套中人"原型 = 全身层层包裹的怪人，童年家暴起源；TZ-S11 原文 line 695 与罗允相遇 = 搭档关系缘起）；在《死亡奔赴》《黄金国》是罗允搭档。活态角色 → 不生成 canon-ending.md（`has_canon_ending: false`）。
- **slug 消歧**：《套中人》_candidates.md 曾标注本篇主角"洪扬"与跨篇登记表"洪扬（罗允搭档）"疑似撞名（三种可能）。本轮按可能性 1（同一人时间线前置）判定：套中人篇是洪扬"成为罗允搭档之前"的前传，line 695 罗允从背后追上 = 二人结识起点；统一 slug 为 `hong-yang`（character_map 既有条目），非撞名的不同角色。
- **来源（built_from）**：
  - `pipeline/phase2_character.yaml`（supporting_cast.洪扬 条 + contrast_axes "罗允'转达' vs 洪扬'现实主义'" + relationships "罗允—洪扬" — 结构化字段唯一来源）
  - `scenes/scene_TZ-S02.md`（套子外形 + 初中起被当怪物 + 守规则人格）
  - `scenes/scene_TZ-S10.md`（父亲洪宝山断后惨死 + 套子撕开"在自己死之前杀掉所有人" + 差点引爆手雷）
  - `scenes/scene_TZ-S11.md`（焚家送葬 + 沿铁路南下 + line 695 被罗允追上 + 对唐志林"己所不欲勿施于人"）
  - `scenes/scene_SB-S11.md`（罗允搭档"正常末日嘛"现实主义 + 读遗书温差 + 相遇后磨合速降梗）
  - `scenes/scene_HJ-S04.md`（地狱冷笑话"祝你痛快地死去" + "两个人一起痛快地死掉"，跟老爹学的）
  - `scenes/scene_HJ-S06.md`（拒留袒露自杀背景"铁路尽头本是归宿，罗允给了活下去的理由" + 输液港/PICC 阶级创伤 + 盖被子套子残留）
- **触发条件 / Layer 3 状态**：本系列无 `novel-meta.yaml`（非 canonical），按 reference 模式跳过 claims.yaml（2f/2g）。
- **locator 覆盖**：6 段共 14 条 distinct locator（parse_locators 去重计），跨 3 篇 7 场景。声音框架跨 3 场（SB-S11 / HJ-S04 / HJ-S06），弧光跨起点（TZ-S02 套子成形）/ 转折（TZ-S10 父死撕套、TZ-S11 相遇）/ 终点（HJ-S06 活下去理由外挂）四个 locator，均非单点外推。父亲洪宝山（前传中已死）、唐志林等《套中人》单篇人物仅作佐证背景，未独立蒸馏。
- **脚本结果**：build_character_references.py exit 0；verify_character_skills.py --check-structure exit 0（locator 数 14 == key-dialogues section 数 14 == build-meta.locator_count 14；边界 5 条 bullet 每条有 locator；6 段各 ≥1 locator；character_map.json 含 洪扬→hong-yang）。

---

# Build Report — 狂病-莫千回 — mang-nv

## 盲女（mang-nv）

- **构建时间**：2026-05-29T16:35:00+08:00
- **构建器**：character-kb-distill（reference 模式）
- **角色定位**：跨《燃烧》《医院》两篇的盲人女性，本名全篇未给（display_name=盲女）。《燃烧》是其第二人称"你"POV 主角篇（证据最富）——失明致嗅觉灵敏 → 队伍预警救星 → 命压身上的负担；男友周全自燃换药、托付罗允后，她被罗允强行救活、带着周全遗言被护送。《医院》中她是罗允护送的盲女（第三人称，刘医生"我"的转述对象）。活态角色（被救活、被护送）→ 不生成 canon-ending.md（`has_canon_ending: false`）。
- **第二人称 POV 取证口径**：《燃烧》全篇为第二人称"你…"叙述，所有"你"的感知与言行即盲女本人——这是她的 POV / 声音载体，故 RS 篇所有 locator 均直接取自其本人视角，非旁观外推。
- **来源（built_from）**：
  - `pipeline/phase2_character.yaml`（supporting_cast.盲女 条 + relationships.key_tensions "罗允—被救者（盲女 / 周全的遗志）" — 结构化字段唯一来源）
  - `scenes/scene_RS-S01.md`（盲女 POV 开篇 + 幼年失明 + 末日五人队伍背景）
  - `scenes/scene_RS-S02.md`（通感穿过人肉树林 — 气味 / 声音 / 触觉替代视觉）
  - `scenes/scene_RS-S03.md`（凭"糖浆 + 咸味"气味记忆认出感染者 — 救星能力）
  - `scenes/scene_RS-S05.md`（周全提醒"前面有台阶"被引领跨障 — 依赖搀扶）
  - `scenes/scene_RS-S06.md`（堵门绝境第一次说出"杀了我吧" — 求死预演）
  - `scenes/scene_RS-S08.md`（用嗅觉反过来安慰周全 — 救星能力工具性）
  - `scenes/scene_RS-S10.md`（焦尸旁拒药 + 被罗允喂药强行救活 + 接过周全遗言崩溃咆哮）
  - `scenes/scene_YY-S02.md`（罗允携盲女抵达医院 — 坐实跨篇身份）
  - `scenes/scene_YY-S08.md`（王幸子转述"黑暗中伸手无人回应" + "想要的也许是死亡"）
- **触发条件 / Layer 3 状态**：本系列无 `novel-meta.yaml`（非 canonical），按 reference 模式跳过 claims.yaml。
- **locator 覆盖**：6 段共 14 条 distinct locator（parse_locators 去重计），跨 2 篇（燃烧 RS + 医院 YY）9 个场景文件。声音框架跨 2 篇取证（RS-S03 / RS-S08 燃烧 + YY-S08 医院），弧光跨起点（RS-S01，并入身份段）/ 转折（RS-S06"杀了我吧"、RS-S10:L11 拒药）/ 终点（RS-S10:L15-L19 被救活成债务）多 locator，均非单点外推。周全（《燃烧》已死灰色男主）、王幸子等单篇人物仅作佐证背景，未独立蒸馏。
- **canon-ending 判定**：has_canon_ending=false。按"被救活、被护送的活态角色"建档——《燃烧》收笔于盲女被罗允强行救活带遗言活下去，弧光终点为内在的"债务般的活"，物理层无终局。《医院》篇虽叙及盲女最终扑焦尸而亡，但本参考包定位其为活态被护送者、弧光只描内在转变（不含物理生死），故不拆 canon-ending.md（已在 build-meta.coverage_note 说明）。
- **脚本结果**：build_character_references.py exit 0；verify_character_skills.py --check-structure exit 0（locator 数 14 == key-dialogues section 数 14 == build-meta.locator_count 14；边界 5 条 bullet 每条有 locator；6 段各 ≥1 locator；character_map.json 含 盲女→mang-nv）。

---

# Build Report — 狂病-莫千回 — lin-dongqing

## 林东青（lin-dongqing）

- **构建时间**：2026-05-29T16:35:30+08:00
- **构建器**：character-kb-distill（reference 模式）
- **角色定位**：反派 wu-xiansheng（吴先生＝石浩洋，同一人）的随身"诱杀工具童"——七八岁男孩，被包装成"师父路上搭救、视若己出的可怜孩子"作诱饵，从内部拆掉信任他们的求生队伍。跨《恶》《医院》《不详》三篇出场，执行偷窃 / 注射麻醉 / 投毒 / 纵火 / 嫁祸 / 灭口 / 放感染者。
- **师父合并**：经用户拍板，《恶》全程伪装"罗允"者＝《医院》诈死操盘的石浩洋＝《狂人日志》吴先生，为同一人，已合并蒸馏为 wu-xiansheng；本包凡提及师父均指向 wu-xiansheng，不再区分"吴先生 / 石浩洋"两壳。character_map.json 既有 林东青→lin-dongqing 条目。
- **canon-ending**：has_canon_ending=false，**不产** canon-ending.md。判定依据《恶》收束 EE-S11:L13-L15——他牵着师父的手"又一次隐入山林之中"，紧接着下一支队伍又遇到"带着孩子的可靠男人"（L15）：活态工具童，循环作恶，原文未给任何不可逆终局（无死亡 / 疯癫 / 被捕 / 脱离师父）。与师父 wu-xiansheng 同为活态反派、同判 false。
- **来源（built_from）**：pipeline/phase2_character.yaml（antagonists.吴先生.characterization "诱导孩童（林东青）作棋子投毒纵火" — 林东青无独立 desire_system / character_arc 字段）+ scene_EE-S06 / scene_EE-S08 / scene_EE-S11 / scene_YY-S05 / scene_YY-S10 / scene_BX-S08。
- **六段 locator 分布**：
  - 身份与处境：EE-S06:L13-L15 / YY-S05:L17-L19（2）
  - 核心欲望：YY-S10:L67-L69 / BX-S08:L17-L19（2）
  - 性格真相：YY-S05:L35-L41 / YY-S10:L47-L49 / BX-S08:L21-L23（3）
  - 声音框架：YY-S05:L33-L41 / EE-S08:L21-L23（2）
  - 边界（每条 bullet 带 locator，5 bullet）：YY-S05:L33-L41 / YY-S10:L53-L63 / YY-S10:L67-L69 + EE-S08:L25-L29 / YY-S10:L67-L69 / BX-S08:L21-L23（5 bullet / 6 locator，其中"执行最残忍指令不犹豫"条带 2 locator）
  - 弧光（已完成）：YY-S10:L67-L69 / YY-S10:L47-L53 / EE-S11:L13-L15（3）
  - 去重后 distinct locator = 13。
- **戏份少的单点维度处理**：林东青为被驯化工具童，几乎无独立内心戏与自陈。核心欲望与弧光内在转变主要由师父 wu-xiansheng 的"精神延续 / 天选之人 / 代际传承"设计反推 + 行为证据外推；phase2 中林东青仅作"吴先生诱导的孩童棋子"被引用，无独立结构化字段，故来源标注挂在 antagonists.吴先生（师父）名下据其延伸设计反推。已在 build-meta.coverage_note 注明。
- **角色区分**：BX/EE 中"自称罗允 / 假罗允"的成年人均为师父 wu-xiansheng 伪装，本包不引用真罗允（luo-yun）本人画像；林东青与真罗允无关系。EE-S10 的"脸画箭头给感染者指路"在原文中由师父自陈实施（"就是我用来告诉感染者们往哪走的"），故未据此为林东青取 locator，仅用 EE-S10 L17"小林找到录像机"链条理解其偷 DV 成果被利用（声音/性格段改用 EE-S08 沉默摇头证据）。
- **脚本结果**：build_character_references.py exit 0；verify_character_skills.py --check-structure exit 0（locator 数 13 == key-dialogues section 数 13 == build-meta.locator_count 13；边界 5 条 bullet 每条有 locator；6 段各 ≥1 locator；character_map.json 含 林东青→lin-dongqing）。

# Build Report — 狂病-莫千回 — tao-yiren

## 陶亦仁（tao-yiren）

- **构建时间**：2026-05-29T17:10:00+08:00
- **构建器**：character-kb-distill（reference 模式）
- **角色定位**：创世军（死亡奔赴式邪教武装）感召者/教主——发明"创造"手势、建电台吸纳幸存者、抹名改编号把队伍铸成"只有陶亦仁一个名字"的巨人；被神格化（沾血不感染、吓退感染者群）；《51人》遗令"追杀罗允"。跨《不详》《51人》《黄金国》三篇出场。
- **identity_link（关键）**：陶亦仁 = 《不详》主角**李鸾（li-luan）裂脑术后衍生的第二人格**（《搏击俱乐部》式"你是我"，BX-S10:L13-L21 直接佐证）。经用户拍板采"两个独立包 + identity_link"方案——本包蒸陶亦仁人格侧，李鸾另有并行独立包 li-luan，两包互标 identity_link（phase2 antagonists.陶亦仁 ↔ supporting_cast.李鸾 均已登记 link；character_map.json 既有 李鸾→li-luan 条目）。SKILL.md「身份与处境」「性格真相」两段均显式写出 identity_link 并带 BX-S10:L13-L21 locator 佐证；build-meta 顶层加 `identity_link: li-luan` 字段。
- **canon-ending**：**has_canon_ending=true，产 references/canon-ending.md**（"宁可漏不可错"）。判定依据三线交叉确证人格+肉身双重不可逆毁灭：(1)《不详》BX-S10——李鸾识破"你是我"后自我感染、命创世军分食自身、咬舌阻其取消命令，与陶亦仁人格同归于尽；(2)《51人》S05——创世军 51 人巅峰崩塌，陶亦仁被感染同伴撕成"米黄色骸骨"，尸周衍生"痛苦型"自毁式感染者；(3)《黄金国》HJ-S13——仅余脸皮被感染后老大哥缝在胯下。物理死亡/感染衍生不写入弧光本体，拆入 canon-ending.md。
- **来源（built_from）**：pipeline/phase2_character.yaml（antagonists.陶亦仁，含 truth_core "= 李鸾第二人格" + identity_link）+ scene_51-S03 / 51-S04 / 51-S05 / 51-S07 / BX-S06 / BX-S10 / HJ-S13。
- **六段 locator 分布（去重后 distinct = 18）**：
  - 身份与处境：51-S04:L3-L9 / 51-S04:L21-L23 / BX-S06:L41-L47（3，含 identity_link 说明段，佐证含 BX-S06 影音店组团起点）
  - 核心欲望：51-S03:L7-L9 / BX-S10:L29-L35（2）
  - 性格真相：BX-S10:L13-L21 / 51-S03:L29-L31（2，**identity_link "你是我·第二人格" 暴露在此段，BX-S10:L13-L21**）
  - 声音框架：51-S03:L51-L53 / 51-S04:L11-L17 / BX-S10:L31-L37（3，跨教主感召腔 + 布道腔 ≥2 场）
  - 边界（每条 bullet 带 locator，5 bullet）：51-S03:L15-L21 / 51-S04:L13-L17 / 51-S04:L19-L23 / BX-S10:L21-L25 / 51-S05:L3-L7（5）
  - 弧光（已完成）：BX-S06:L27-L41 / 51-S04:L9-L19 / 51-S03:L13-L17（3，起点 BX-S06 / 转折 51-S04+51-S03）
- **跨篇时序说明**：《不详》是 identity_link 真相所在（李鸾梦游→陶亦仁人格接管→"你是我"识破→双人格同归于尽）；《51人》是张亦川 POV 回溯线，从外部旁观陶亦仁/创世军的建制、神格化与崩塌；《黄金国》仅余残骸态。三篇时序与"同一具身体两个人格"的关系在 build-meta.coverage_note 注明。《51人》S07:L9（刺成云丹转述"追杀罗允"遗令）收入 built_from 作跨篇钩/contrast_axes 关系证据，但未直接刻画人格本体，故未取作章节 locator。
- **脚本结果**：build_character_references.py exit 0；verify_character_skills.py --check-structure exit 0（locator 数 18 == key-dialogues section 数 18 == build-meta.locator_count 18；边界 5 条 bullet 每条有 locator；6 段各 ≥1 locator；frontmatter 含 name/description/version/allowed-tools；目录名=build-meta.role_slug=frontmatter.name=tao-yiren；character_map.json 含 陶亦仁→tao-yiren）。

---

# Build Report — 狂病-莫千回 — li-luan

## 李鸾（li-luan）

- **构建时间**：2026-05-29T16:40:00+08:00
- **构建器**：character-kb-distill（reference 模式）
- **角色定位**：《不详》篇第一人称叙述者 / 宿主人格——末日前大学维修工，十岁裂脑术（偏执体切割）后衍生出第二人格"陶亦仁"（创世军教主）。《搏击俱乐部》式双人格设定，自我认同为"灾星 / 不祥的暴风眼"，"免疫者 / 无症状感染者身份不明"双关。
- **identity_link（关键）**：陶亦仁（role_slug `tao-yiren`）= 李鸾裂脑术后衍生的强势第二人格，二者共用同一具身体。原文锚 BX-S10:L13-L15 "你是我，和那个《搏击俱乐部》里的剧情一样，你是我的第二人格"。本包与并行蒸馏的 tao-yiren 包互标 identity_link：本包 build-meta 设 `identity_link: tao-yiren`，性格真相段显式写出该 link 并带 BX-S10:L13-L15 佐证。
- **canon-ending 判定**：has_canon_ending=**true**，**产** `references/canon-ending.md`。判定依据《不详》结局 BX-S10:L47-L57——李鸾认清"我们才是应被清除的 bug"后，倒母猪配种发情粉自我感染、命令成员吃掉自己，并用"左手抓右手、左脚踢右脚"压住第二人格逃跑冲动，两个人格在被撕咬中同归于尽。这是不可逆的肉体毁灭 + 双人格双双消亡，按"宁可漏不可错"判为不可逆终局。弧光只描内在转变（"灾星"自我认知 + 双人格觉察 + 承担"bug"认知），物理自感染/毁灭拆入 canon-ending.md。
- **来源（built_from）**：pipeline/phase2_character.yaml（supporting_cast.李鸾，已标 identity_link: tao-yiren）+ characters/不详/_candidates.md + scene_BX-S01 / S03 / S06 / S07 / S08 / S09 / S10。
- **六段 locator 分布**：
  - 身份与处境：BX-S01:L9-L11 / BX-S03:L3-L5 / BX-S01:L11-L13（3）
  - 核心欲望：BX-S03:L49-L51 / BX-S06:L41-L45 / BX-S10:L53-L57（3）
  - 性格真相（含 identity_link）：BX-S10:L13-L15 / BX-S03:L43-L43 / BX-S06:L3-L5（3）
  - 声音框架：BX-S01:L3-L5 / BX-S10:L41-L41 / BX-S08:L37-L37（3）
  - 边界（每条 bullet 带 locator，5 bullet）：BX-S09:L7-L7 + BX-S07:L23-L23 / BX-S08:L37-L37 / BX-S03:L49-L51 / BX-S10:L13-L15 / BX-S10:L53-L57（5 bullet / 6 locator，首条带 2 locator）
  - 弧光（已完成）：BX-S06:L3-L7 / BX-S10:L13-L15 / BX-S10:L53-L53（3）
  - 去重后 distinct locator = 16（parse_locators 去重计；跨章节复用的 BX-S10:L13-L15、BX-S10:L53-L57、BX-S08:L37-L37 等只计一次）。
- **单篇取证说明**：李鸾仅在《不详》单篇出场（场景前缀 BX，BX-S01~S10），无跨篇证据——固有约束。软建议"跨 ≥2 场景"靠 BX 内不同场满足：声音框架跨 3 场（BX-S01 回溯自白 / BX-S10 自嘲疯话 / BX-S08 动作截断情感），弧光跨起点（BX-S01 并入身份/弧光起点）/ 转折（BX-S06、BX-S10）/ 终点（BX-S10）多 locator，均非单点外推。已在 build-meta.coverage_note 注明。
- **角色区分**：BX-S08 中"自称罗允 + 带孩子小林系统性诱杀沈曾祺队"的反派（转述入场）为假罗允（wu-xiansheng 型），不用于刻画李鸾人格，仅作《不详》篇内反派背景，未取 locator。
- **locator 区间格式修正**：build 脚本 LOCATOR_PATTERN 仅匹配 `:L{a}-L{b}` 区间，不匹配单行 `:Ln`；初稿误用单行格式（被静默丢弃导致边界 bullet 缺 locator），已全部改为区间格式（单行内容用 `Ln-Ln`），符合"区间格式（非单行）"硬约束。
- **脚本结果**：build_character_references.py exit 0；verify_character_skills.py --check-structure exit 0（locator 数 16 == key-dialogues section 数 16 == build-meta.locator_count 16；边界 5 条 bullet 每条有 locator；6 段各 ≥1 locator；character_map.json 含 李鸾→li-luan）。
