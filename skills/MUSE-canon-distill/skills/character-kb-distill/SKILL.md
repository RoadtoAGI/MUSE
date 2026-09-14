---
name: character-kb-distill
description: 蒸馏名著角色的知识库参考包，供人物研究与创作参考。由小说/戏剧分析调用，或显式 build/rebuild；连载接管快照使用 serial 包同名入口。
user-invocable: true
argument-hint: "build (--novel <书名> | --novel-dir <目录>) --role <中文名> | rebuild <role-slug> (--novel <书名> | --novel-dir <目录>)"
allowed-tools: Read Write Edit Bash Glob WebSearch WebFetch
---

# 知识库角色蒸馏

命令中的 `${CLAUDE_PLUGIN_ROOT}` 以本技能所属包的实际安装根替换；Claude 插件可用宿主提供的该变量。其他宿主从当前技能位置定位包根。

从目标版本的人物系统与原文提炼可追溯参考，供设计者理解身份、关系、选择和声音。产物是知识库参考包；人物运行状态与当前故事适配由创作侧负责。

## 输入与来源

`--novel <书名>` 解析到本 canon 包 `knowledge-base/novels/<书名>`；`--novel-dir <绝对目录>` 沿显式来源，两者择一。以下 `${NOVEL_DIR}` 均指该目录，`${CLAUDE_PLUGIN_ROOT}` 始终指 canon 工具根。外部作品在原目录构建，不复制到 canon 库，也不依据宿主 cwd 重新选择同名作品。

build 传 `--role <显示名>`；rebuild 传既有 role-slug。定位人物系统：戏剧优先 `pipeline/phase2_roles.yaml`，小说及旧资产使用 `phase2_character.yaml`；缺系统图时返回分析入口。小说兼容 cast_overview 与旧 protagonist / antagonist(s) / supporting_cast，戏剧兼容 roles mapping 或列表，按 name/name_zh 或原键定位实际人物。组织、时代压力等抽象力量不建人物包。

系统图提供人物关系和功能，个体档案提供已有解释，原文决定事实与概括强度。角色身份或声音需要时再读取 Phase 0、实际世界资料、已有个人档案与相关原文；戏剧世界资料优先 phase1_world_stage.yaml。没有个人档案或切片时直接定位 full_text，不新增前置交付物。

版本与已读截止点沿调用范围。后来的总结可作导航，不能越界提供人物事实；对抗功能、声音职能与作者分析不能直接变成人物自知或永久禁令。来源有冲突时回到目标原文修订本次解释，并在既有 build-report 说明分析位置。

## 人物与证据

生成前读取 [参考包模板](references/reference-skill-template.md) 与 [填写指南](references/reference-writing-guide.md)；理论解释见 [人物与声音](references/mckee-voice-principles.md)。身份与处境必备，其余章节按实际证据生成。自觉目标、稳定人物、直接坦白与尚未明示的动机均可成立。

关键断言附 `{相对作品根的路径}:L{start}-L{end}`，例如 `full_text.md:L10-L25`。保留对象、压力、知识、阶段与概括强度；单次选择不足以支持永久底线。定位必须来自实际回读的原文，足以支撑判断；已读反例会改变结论时一并处理。

目录为 `${NOVEL_DIR}/characters/{role-slug}/`。slug 使用小写字母与连字符，在本作品内唯一；已有 character_map 映射优先，rebuild 沿用。生成 SKILL.md 的 name/description/version 依模板；参考包提供只读来源，宿主支持 allowed-tools 时沿模板映射读取能力。

## 资产与条件附件

`SKILL.md` 保存人物参考，`build-meta.yaml` 保存本次实际来源与范围：

```yaml
mode: reference
display_name: 角色显示名
role_slug: role-slug
source_novel: 作品目录名
builder_skill: character-kb-distill
built_from: []                    # 实际采用的人物系统、个体档案及原文相对路径
built_at: ISO时间
skill_version: 1                  # 与 SKILL.md version 一致
locator_count: 0                  # parse_locators 对 SKILL.md 去重统计
has_canon_ending: false
coverage_note: 本次来源版本、范围及会影响使用的未覆盖内容
```

人物或来源断言实质重写时两处 version 同步递增；单纯元数据修补不需要新人格版本。built_from 至少含实际人物系统及已采用原文，不把仅浏览文件列为采用依据。

- **references/key-dialogues.md**：由下述脚本按 SKILL 定位生成，保留原文证据，不另写一套分析。
- **references/canon-ending.md**：仅在目标原文已明确不可逆终局时，按模板另存其条件与来源。退出、失踪或暂时封闭不足以证明不可逆；不确定时省略附件并说明缺口。
- **dialogue-profile.yaml**：有可观察表达证据时，按 [对白画像](references/dialogue-profile-schema.md) 生成。引用原文或已建事件；没有的轴留空。基于现有声音摘要的投影使用 compact 与 derived_from_character_skill，不冒充完整原型。
- **claims.yaml**：本次有具体来源冲突或用户要求事实核对时，按 [事实核对](references/claims-verify.md) 记录相关断言。canonical 标签不自动触发全角色联网；未生成 claims 不影响已有原文参考。

参考模式不生成 state.md、backstory.md 或当前创作的 adapter。回读相关来源后证据足以支撑本次参考即可结束取材，不按场数反复检查。

## 引用生成与接口检查

SKILL 与 meta 完成后运行：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/build_character_references.py \
  --novel-dir ${NOVEL_DIR} \
  --skill-file ${NOVEL_DIR}/characters/{role-slug}/SKILL.md \
  --role-slug {role-slug} --display-name "{角色显示名}"
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/verify_character_skills.py \
  --novel-dir ${NOVEL_DIR} --role {role-slug} --check-structure
```

生成器先读取全部引用，成功后写 key-dialogues 并更新 character_map。定位、文件或范围错误时修实际来源与派生物，不能改原文迎合引用。结构检查核对已有章节、边界条目的定位、frontmatter、slug、版本及引用数量一致性；它不能证明引文支持人物解释。

自定义工作区的定位根不同于作品根时，生成器用 `--scenes-base <定位根> --character-map <映射路径>`；scenes-base 是 locator 相对的根，通常不再追加 scenes/。验证器若用 `--role-dir`，同时传 `--character-map` 才能检查映射。失败时返回具体缺口，未解决项保持未完成，不反复编造内容直至通过。

## 交接与重建

在 `${NOVEL_DIR}/characters/build-report.md` 按角色追加本次完成范围、实际版本、来源与未决缺口，保留前次记录；上层的候选范围不在单角色构建中重复汇报。回主控实际路径、版本与是否存在影响使用的来源分歧。

rebuild 沿原 slug、原来源范围及新授权读取证据，实质变化更新人格与元数据，再生成引用和检查。来源、模板或用户任务改变时才重建，已有版本不因读过更多无关场景自动升版。角色参考供采用者作判断，不能把文件存在或脚本成功称为当前创作已经消费。
