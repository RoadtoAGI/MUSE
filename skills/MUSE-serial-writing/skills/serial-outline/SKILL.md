---
name: serial-outline
description: 连载与衍生小说的立项、开卷和设计修订入口，承接同人、续写、番外与跨文风小说改编。组织世界、人物、脊椎和卷结构共创，维护系列工作区，也可导入 serial-distill 已生成的接管目录。已有工作区写下一章用 serial-chapter-writing；原始连载文本的接管蒸馏用 takeover-distill。
---

# serial-outline — 连载大纲

## §0 职责与加载

把作者的创作意图发展为能支持持续写作的世界、人物、主线方向和卷纲。新作走 S1–S5；开卷再入 S5；修订回到受影响的设计；接管继承来源中已成立的内容，补本次续写实际需要的缺口。

使用当前宿主的正式加载方式。本文中的同包技能由当前 `serial-outline/SKILL.md` 定位到同级技能；脚本位于本包 `scripts/`，示例的 `${CLAUDE_PLUGIN_ROOT}` 应替换为实际解析出的本包根。委派时显式传系列工作区、任务与来源路径，取得对应技能正文后再执行。跨包参考按可用的包入口加载；缺少可选参考时继续设计，缺少必要执行依赖时报告具体缺件。

字段与文件权威在 [workspace-schema](references/workspace-schema.md)。开始写某类产物前读对应节及模板；已有有效材料直接复用。共创决定、冻结修改按 [共创协议](references/collaboration-protocol.md)，章级交接按 [上下文协议](../serial-chapter-writing/references/context-contract.md)。

```text
新作意图 → S1 类型与表达方向 → S2 世界 / S3 人物 → S4 脊椎 → S5 卷纲
                                  ↑               |
                                  └── 发现前提变化 ┘
接管目录 → 导入、承接已知与未决事项 ────────────────┘
已有工作区 → 恢复当前任务 → 受影响设计 / 开卷 / 交章节撰写
```

S1–S5 是产物责任和依赖关系；世界、人物与主线在定稿前可以相互修正。公开正文与已确认的冻结设计继续按各自修改通道处理。

## §1 工作区、恢复与入口

`works/<slug>/series/` 保存设计、台账和状态，`chapters/V0N/C####/` 保存章工作区，`published/` 保存已发布正文；`published/manifest.yaml` 是发布序权威。已有工作区先读取 `series_state.yaml` 并执行：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_series.py --work-dir works/<slug>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_series.py --work-dir works/<slug> --claim-session <session-id>
```

先对账，再认领。对账 exit 2 时报告恢复矩阵、停下解决不完整发布事务；认领 exit 3 时报告他人会话占用，取得接管确认后再继续；exit 1 的数据错误先修复。矩阵给出的未完成动作按真实产物恢复。同一会话在工作区、任务与相关状态未变时复用已成功的对账和认领；有新发布、恢复操作、外部修改或会话归属疑点时重做。

每次进入仍检查 `pending`：未决事项需要作者回答或已有明确委托，才能推进依赖它的工作。离会时更新当前进度并释放本会话的 `active_session`；待决问题按共创协议保留。

外层入口拥有会话认领与释放。内部技能和子执行者使用外层传入的 session ID，复用同一 marker，返回时不释放；外层在整个作品事务结束，或保存 pending 后离会时运行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_series.py --work-dir <series_root> --release-session <session_id>`。空 marker 可重复释放；他人 marker 返回 exit 3，不能替其清除。


| 入口 | 动作 |
|---|---|
| 新作、工作区不存在 | S1 明确已知意图后用 `init_series.py --slug <slug>` 建骨架；同 slug 已存在时脚本 exit 2，转已有工作区 |
| serial-distill 接管交付目录 | `import_series.py --from <交付目录> --works-root works/`；失败按 stderr 处理，版本窗口不符由来源包重新导出；成功后对账与认领 |
| 已有工作区 | 根据作者任务、缺件和 cursor 进入对应设计；`cursor.stage: breaking` 再入 S5 |
| 大纲可供写章 | 加载本包 `serial-chapter-writing` 并交系列根、当前卷与已确认方向 |

接管同时读 `story_bible.intent.open_questions`。补齐下一段所需的类型、人物基线、世界规则与主线方向；来源未揭示的未来保留未决。缺世界全图或正式 Phase 2 文件本身不要求重新设计整部作品。

## §2 创作判断与来源

麦基《故事》第五、七章说明人物与结构的相互作用：压力下的选择揭示人物，人物的欲望与能力也限定可信事件。用于本作时，连同世界条件推演“他为什么这样选、对手如何回应、局面如何改变”；人物可以保持立场，通过处境、关系和别人对他的认识形成发展。有意识的追求可以独立成立；只有设计确有相互矛盾的不自觉欲望时才写入深层需要。

《故事》第六章以价值及其变化原因解释主控思想，完整故事的结尾动作使它成立。新连载可先提出待剧情检验的表达方向；已经确认的放入创作锚，尚未确定的放在 `intent.open_questions`。主线可以指向阶段性追求与终点意象，具体结局按作者授权和作品进展决定。`primary_drive`、类型三档、S1–S5 与冻结机制是项目设计，用于组织选择和连续性，不据字段自动推导情节或普遍创作定律。

作者只给宽泛意图时，提出具体关系、处境和值得表达的认识；作者已固定思想、人物或行动时，深化开放部分。候选要说明关键事件与人物如何起作用、会得到什么、需要付出或调整什么。抒情、重复、稳定人物和多线组织按其实际阅读作用判断。事实、因果与明确意图不符由模型指出；审美取舍交作者。

## §3 S1–S5 的产物与消费者

| 阶段 | 本阶段决定与产物 | 后续用途 |
|---|---|---|
| S1 类型与表达方向 | `genre_profile.yaml`；`story_bible.frozen.creative_anchors` 与 `intent` | 类型分册选择、人物和结构设计、表达方向对照 |
| S2 世界 | 本包 `world-bible-design`：`worldbook/` 及 `world_ceiling`，适用时填 `power_system_pyramid` | 人物行动条件、后续世界揭示的已定边界 |
| S3 人物 | 本包 `character-system-design`：角色关系与 persona、初始快照、传记骨架、按需 runtime 包 | 卷向推演、连续性与按时点派生人物输入 |
| S4 脊椎 | `frozen.premise / protagonist_want_need / spine_direction` | 卷向与章级推进的因果和方向约束 |
| S5 卷结构 | 本包 `volume-outline`：本卷问题、人物经历变化、必要转折与揭示安排 | 章节侧滚动编排、场景上下文与卷收束 |

S1 先采用作者给定信息；对标作品用于理解其想保留的阅读体验。需要判断时读取 `genre_profile` 契约与对应 genre-pack，填写 `substrate`、`engine.primary`、可空的 secondary、`pacing_contract`、标签和对标作品。三档节奏是配置选项，任何具体数字需按其依据与适用条件使用；已给定的信息不重问。类型判断确认后按冻结纪律维护。

S2/S3 的深度由本作冲突与持续写作所需信息决定，具体理论、格式和类型分支归各自技能。S4 将已推演的前提、追求与方向合在现有总纲中；变更牵动世界或人物时同步调整相应未冻结设计。S5 只形成卷级框架，逐章 logline、hook 和场景设计归章节撰写；编排结果在既有章卡与 `phase5_scenes.yaml` 中承载。

## §4 按问题取参考与诊断

作者指定书目优先。本包 `inspiration-research` 可贯穿 S1–S5：传开放的 `narrative_problem`、已有条件和参考偏好，取原作的作用机制、成立条件与来源。思想和核心关系问题用概念尺度 phase=0，结构问题按卷、幕/Arc 或序列尺度取材。当前设计负责人负责提出本作的新联系；采用的来源与迁移条件进入既有候选、创作锚及 `pipeline/inspiration_ledger.yaml`。已有材料足够时直接使用；参考改变了什么判断应能解释。

S2–S4 完成或修订后，存在具体跨来源疑点或作者要求检查时，加载本包 `outline-validation`，传作品根 `series_root`（含 `series/` 与 `published/`）、报告根 `work_dir=series_root`、疑点、相关来源绝对路径和 `scope=series`；卷纲问题用 `scope=volume` 并传 `volume_id`。按报告定位原设计，修正事实/因果错误或交作者决定意图冲突。读取 `<work_dir>/pipeline/review/design_validation.yaml` 处理发现与缺失输入；无需每阶段或每章另设例行审计。

## §5 共创、修订与完成

共创按 [共创协议](references/collaboration-protocol.md) 执行。已有方向和授权直接继承；需要比较的分歧才提出候选。退回后修正最先失效的思想、迁移或剧情决定，保留认可部分；若不理解参考为何有效或语境缺失，补读相关原文和后果，再更新受影响产物。

本轮产物落盘后运行 `serial_lint.py --work-dir works/<slug> --check <受影响检查>`，exit 2 处理违规，exit 1 先修数据。冻结字段修改还要核对本次授权；lint 和宿主 hooks 的实际覆盖不代替授权判断。阶段完成以交付物能供直接消费者使用、必要决定已确认或已获委托为准，格式通过单独说明。S5 完成后交章节撰写；后续大纲变化回到相应责任阶段。
