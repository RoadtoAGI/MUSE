---
name: design-doc-reference
description: 为构想与 Phase 1–5 设计检索原作机制、成立条件和来源原文。用于设计取材或比较作品取舍；正文场景参考使用 scene-reference。
argument-hint: "phase=<0|1|2|3|4|5> narrative_problem=<问题> signals=<brief-json> output_dir=pipeline/references"
allowed-tools: Read Write Glob Bash
---

# 设计文档参考检索（Phase-aligned design reference）

命令中的 `${CLAUDE_PLUGIN_ROOT}` 以本技能所属包的实际安装根替换；Claude 插件可用宿主提供的该变量。其他宿主从当前技能位置定位包根。

> **职责边界**：本 skill 只服务"设计阶段参考"，**不**服务 Phase 6 正文写作（正文 few-shot 参考由姊妹 skill [`scene-reference`](../scene-reference/) 负责）。两者输入信号、输出形态、消费方都不同。

## 调用协议

由当前设计负责人通过宿主支持的 skill 机制调用，返回 run-local Markdown。phase=0 服务核心构想尚未定型的研究；Phase 1-5 服务相应设计。已有材料能回答同一问题时直接复用，新的问题、来源变化或反馈再触发补读。创作负责人决定怎样转化及采用，本 skill 提供来源事实、机制解释和适配条件。

## 输入契约

由调用方（MUSE-writing orchestrator 或人工）传入：

| 字段 | 取值 | 来源 |
|------|------|------|
| `phase_id` | 0 / 1 / 2 / 3 / 4 / 5 | 0 表示概念层问题，其余为设计尺度 |
| `genre` | 已知题材，可暂缺 | 原始需求或 Phase 0 `genre.primary` |
| `signals` | JSON 短串，各 phase 不同（见下表） | 主干当前 phase 已知的少量检索信号 |
| `narrative_problem` | 当前要解决的思想、关系、规则、结构或阅读问题；普通字段参照可省略 | 当前 owner 临时提炼，不新增 phase schema 字段 |
| `output_dir` | 通常 `pipeline/references`（run-local 路径） | 主干 run 目录 |
| `canon_reference_profile` | 可选；沿用 Phase 0 mapping | 手选作品、`intended_domains` 与 `reuse_mode` |

### 各 phase signals 推荐

| phase | signals |
|---|---|
| 0 | `narrative_problem, creative_intent, fixed_conditions, reader_effect`，有题材再传 `genre` |
| 1 | `genre, primary_drive, setting_scale, conflict_layer` |
| 2 | `genre, protagonist_register, antagonist_register, relationship_mode, primary_drive`；固定 canon 人物另传 `protagonist_name, story_timepoint` |
| 3 | `genre, spine_mode, protagonist_desire_or_information_goal, crisis_type, narrative_problem` |
| 4 | `genre, structure_mode, climax_shape, pov_mode, narrative_problem` |
| 5 | `genre, key_scene_types, pov_pattern, risk_families, narrative_problem` |

signals 按已有材料提供，`narrative_problem` 同时并入 signals 参与脚本召回。写清具体关系与条件，例如“已能保存全部记录，仍无法让两人互相理解”；思想问题可以跨题材取材。无需凑齐表中字段。

## 检索范围（内部）

在 canon-distill 包内部检索：

```text
${CLAUDE_PLUGIN_ROOT}/knowledge-base/{novels,dramas}/*/pipeline/phase{N}_*.yaml
${CLAUDE_PLUGIN_ROOT}/knowledge-base/{novels,dramas}/*/pipeline/*/phase{N}_*.yaml
# phase=2 需要个体信息时，按 character_map / 人名解析：
${CLAUDE_PLUGIN_ROOT}/knowledge-base/{novels,dramas}/{preferred-work}/characters/{character}.md
${CLAUDE_PLUGIN_ROOT}/knowledge-base/{novels,dramas}/{preferred-work}/characters/{character-slug}/SKILL.md
```

按实际来源容器检索；戏剧保留 `world_stage / roles / dramatic_spine / act_sequence / scene_table` 的原始结构与媒介条件。第二条路径服务合集、短篇集等集合型作品。`pipeline/` 的直属子目录各自作为独立作品单元参与匹配；来源定位保留“作品 / 单元 / Phase 文件”，Arc、序列与场景身份停留在所属单元内。跨单元结果只作为并列来源进入候选比较。

调用方通过宿主的已安装 skill 入口使用本技能，返回 run-local 内容；本技能内部按实际包根读取来源，避免让调用方依赖姊妹包的开发目录。

检索策略（实现可演进，本 SKILL.md 给框架）：

0. **卡库物化先行**：若需要灵感范式候选，先运行：

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/inspiration_query.py \
     --phase {N} \
     --signals '<signals JSON>' \
     --output-dir {output_dir}
   ```

   用户手选作品承担当前设计域时，为每部作品追加 `--preferred-work '<作品名>'`。手选作品中的语义相关卡优先排序；卡库无对应卡时，直接读取该作品当前 Phase YAML 的来源事实。

   已有 Phase 0 文件时传 `--canon-reference-profile '<当前 YAML 路径>'`，跨来源卡按卡内全部来源的用途交集选择，含 avoid 来源的卡跳过。输出不在 `{work_dir}/pipeline/...` 下时显式传 `--work-dir '{work_dir}'`。任务已有必要条件可逐条传 `--must '<一个条件>'`。

   产物为 `{output_dir}/inspiration/phase{N}_cards.md`，候选来源以 card id 标识。相关性分数只决定阅读顺序。比较 `mechanism`、逐作品 `source_analyses` 与本作条件；旧卡只有摘要时按问题补读。exit 2（卡库缺失 / 无命中）时按下方步骤从原作取材；本次失败不得把上次同名文件当成新结果。
1. **先处理手选作品**：当前 phase 学习面命中某个 `prefer` 项的 `intended_domains` 时，精确限定到该作品；结合该来源的 `reuse_mode` 确定采用范围，自动候选只补充未覆盖领域。`style_only` 只提供表达参考；其他用途仅在已选领域中提供机制或素材。阅读原文用于理解来源，原作事实进入本篇的义务须有本次采用依据。phase=2 且指定固定人物时，完整读取该人物档案或角色 Skill，先看清全弧再按 `story_timepoint` 切开；随后只沿 locator 读取与切片前承重经历、当前决定、声音或盲区直接相关的原作场景。相关证据充分时停止，不为形式完整通读全书
2. **按问题扩展来源**：题材用于理解语境；功能与关系相通的跨题材作品可进入候选。phase=0 可从作品构想与整体拆解进入，再沿线索补读相关层级；不要求先有本作 Phase 0 YAML
3. **按 signals 排序**：用 signals 与候选作品的 phase{N}_*.yaml 对应字段做语义近似匹配
4. **精选参考**：已有证据能回答当前结构问题时停止扩展；手选作品在绑定领域排首位，其他作品只补证据缺口

phase=2 的系统 YAML 主要记录人物功能与关系。普通人物参考需要解释具体选择、声音或轨迹时，也按缺口读取已有个体档案 / 角色包及相关原文，无需先调用构建器。概括保留来源时点、适用关系和压力条件；旧包中的绝对边界须与原文核对，不能仅凭章节名提高强度。无来源的潜意识欲望或转变保持未明，由当前人物设计者决定新作是否需要。

候选过少 / 无匹配时降级（见 §失败降级）。

### 理解机制与回读原文

准备采用的主要参考，应有足以解释其效果的原文语境；已读且仍适用的材料直接使用。需要补读卡片来源时，在本包执行：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/inspiration_query.py \
  --read-card <card_id> --source '<作品目录名>:<scene_id>' \
  --output-dir {output_dir}
```

`--source` 可重复，省略时返回卡内所有来源。脚本按每作品权威索引精确定位，采用卡内场景行范围，未指定范围则保留完整场景；输出 `{output_dir}/inspiration/{card_id}_reading.md`，来源缺失返回 2。读取所需段落，必要时补充前置铺垫或后续兑现，再把可消费的原文窗口与设计解释一同返回。未建卡的作品由本 skill 沿作品索引读取并写入本次参考。

解释原作的具体构想与作用、叙事理由、可迁移关系与条件。涉及思想时，指出它如何由具体经验形成或变得复杂；涉及隐喻时，说明形象的性质如何同时参与表层故事与深层理解。`narrative_reason` 是文本分析，作者本人的创作动机须有单独来源。多义作品保留有文本依据的不同理解。

反馈或解释暴露语境缺口时，定向回读所用原文，将新发现用于修订解释或更换来源；已有理解足以支持修订时直接使用。通常只交付影响本次构思的材料与结论，不附逐次阅读或检查日志。

## 输出

写入 run-local 文件：

```text
{output_dir}/phase{N}_design_ref.md
```

内容按本次问题与命中证据组织，保留以下适用信息：

1. **选中参考作品**：含书名、匹配的设计尺度与结构问题；逐来源保留本次 `reuse_mode / intended_domains` 及作者明确的采用条件。字段未提供时记录实际已知用途，普通选材偏好保持候选性质；一份来源的范围不覆盖其他来源。
2. **每个参考作品的 phase-aligned 设计摘要**：
   - 来源事实（世界规则、人物或结构在原作中实际是什么，并给出原文件定位）
   - 本篇采用关系：区分原作事实、适配建议与本作已采纳事实。只有本次已授权采用且要求保留的事实进入本篇因果约束，注明其用途依据；其余机制或承载方式供设计者选择。`style_only` 的内容只用于表达参考
   - 结构组织（字段间的依赖 / 因果链 / 对位）
   - 原作选择的作用与成立条件；字段填满程度不作为学习目标
   - phase=2 固定人物的时间点切片：此前承重经历、此刻欲望/信念/关系、当时已知与未知、当前弧光位置、时间点之后须隔离的知识与反思
3. **候选灵感卡**（structured YAML 段，status=candidate，供调用方按需 promote）：
   - pattern 卡保留 source / abstraction / fit_signal / project_encoding；原作确有分段揭示且适用于本作时才附 disclosure_ladder
   - phase=2 需要人物原型候选时输出 archetype 卡，保留 archetype_role / archetype_target_slug / weight / merge_boundary；只查询具体人物事实时无需另造原型
   - 候选卡引用卡库范式时，`source` 字段附 card_id（如 `card: mentor-death-delayed-reveal`），便于 promote 后回溯
   - `abstraction` 保留思想或叙事机制，`fit_signal` 说明本作已有与缺少的条件；`project_encoding` 与 `disclosure_ladder` 仅给适配可能，由创作负责人定案。卡片对应的原作分析和原文窗口保留在本参考中，供其作决定
4. **可参考的问题**（按本次缺口选择）：
   - phase=0：值得展开的思想与经验、形象与关系如何承载它、原作如何形成相关认识；概念尚未确定时保留不同问题方向
   - phase=1：题材世界规则的密度 / driver 选型 / 平台样态
   - phase=2：人物维度组合 / 声音特征写法 / 弧光模式；固定人物同时给目标时间点的主观切片，不能把整条人物弧光压成恒常人设
   - phase=3：脊椎字段收束 / 因果链 / desire vs information vs motif spine 组织
   - phase=4：结构卷构编织 / 卷末对位 / 跨系统编织
   - phase=5：场景编排节奏 / POV 切分 / key_scene 类型分布
5. **当前 phase 的使用建议**：只写会改变当前设计决定的指引
6. **用途范围内的复用候选**：先按每份来源的作者用途与已选领域限定范围，再按项目适配度列出人物、设定、情节、专名或原文候选；`style_only` 仅列可学习的表达机制，不产生原句、情节或世界事实的复用义务。复制原词、原句和连续段落须符合本次明确的原文采用约定；跨语言处理沿该约定选择翻译、转写或原文。没有适用候选时省略本项

**禁止**：

- 把无关原文装入当前参考；读懂机制所需的原文窗口按问题提供，Phase 6 的写作 few-shot 仍由 `scene-reference` 承担
- 要求主干 Read canon-distill 物理路径（由本包读取并返回当前参考内容）
- 用自动候选覆盖手选作品在 `intended_domains` 内的来源事实

## 失败降级

| 情形 | 行为 | 退出码 |
|------|------|-------|
| 扩展包未装（主干侧 `Skill design-doc-reference` 不可触发） | 本 skill 不被调用，整层跳过 | — |
| KB 缺失（本次有效来源容器 novels / dramas 均无可用资料） | stderr 提示 `KB_MISSING`，**不落盘**，主干按本次失败结果跳过消费 | 2 |
| 按问题扩展后仍无相关候选 | 提示 `NO_MATCH`，不落盘 | 2 |
| 手选作品缺失 | 报告 `MANUAL_REFERENCE_MISSING` 与受影响领域；该领域不以其他作品替代，其余领域继续 | 2 或局部降级 |
| signals 全空 + 仅有 genre | 仅作题材候选召回，不补默认人物语域；有可用结果时说明匹配依据有限 | 0 |
| 写入 output_dir 失败（路径不存在 / 权限） | stderr 提示，不重试 | 2 |

主干侧：按本次成功返回的路径消费自动参考，不因同名旧文件存在而加载；手选作品绑定领域必须消费成功返回的来源事实。缺失时保留该领域未完成状态。

## 与姊妹 skill 的关系

| Skill | 服务阶段 | 输入信号 | 输出 | 消费方 |
|---|---|---|---|---|
| `design-doc-reference`（本） | 构想及 Phase 1-5 设计 | phase_id + signals + narrative_problem | `phase{N}_design_ref.md` 与按需原文 | 设计负责人 |
| [`scene-reference`](../scene-reference/) | Phase 6 写作 | scene_id + 场景类型 / 冲突 / 情绪 | `{sid}_ref.md` | writer |
| [`character-kb-distill`](../character-kb-distill/) | KB 建设 | 名著原文 + Phase A 产物 | `knowledge-base/.../characters/` | builder（offline） |
| [`novel-analysis`](../novel-analysis/) | KB 建设 | 名著原文 | `knowledge-base/novels/<书>/pipeline[/<作品单元>]/phase{N}_*.yaml` | builder（offline） |

四 skill 形成完整闭环：novel-analysis + character-kb-distill 离线**产** KB → design-doc-reference + scene-reference 在线**查** KB 服务写作主干。

## 消费边界

候选卡按调用方现行 `pipeline/inspiration_ledger.yaml` 契约输出，连载保留章范围绑定；`status: candidate` 留在参考文件，调用方实际采纳后再分配 INS-* 并写入 ledger。每个入选结果携带来源作品、scene id、原作事实、主要设计尺度、可复用因果关系和失效边界。

当前 owner 优先取得同层证据，相邻尺度证据只在机制跨层时补充。候选菜单不进入 writer 热路径；writer/composer 只接收已采纳结构决定、相应原文与少量微观手艺。可靠结果为空时返回 `NO_MATCH`，当前 owner 依理论自主设计。
