---
name: story-writing
description: 完成原创中篇或篇幅未明的完整小说，从点子推进到终稿；明确短篇交 short-story-writing，剧本交 screenplay-writing，衍生与连载交 MUSE-serial-writing。
---

# 完整小说创作

按阶段组织创作，保证作者要求、人物、世界与结构进入正确消费者。麦基《故事》第二部分导言讨论故事诸要素的统一；本入口拥有阶段交接、作者裁决与完成条件，阶段内部的创作和修订方法由相应技能负责。

```text
需求 → 构想 → 世界 → 人物 → 脊椎 → 结构 → 场景编排
                                          │
                         设计校验 → 作者大纲裁决
                                          │
                              Phase 6 正文与场景审阅
                                          │
                              Phase 7 整合与终稿交付
```

## 初始化与恢复

用本包 `scripts/init_run.py` 建立工作目录；已有目录先核对当前任务与有效产物，恢复到尚未完成的阶段。脚本仅创建骨架，设计与正文由后续阶段写入。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_run.py --run-intent release --results-dir results/ --query "<本次创作需求>"
# 调用方已给工作目录时：
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_run.py --run-intent release --run-dir <work_dir>
```

`run_intent` 必须显式传入：成稿用 `release`，评测和链路探针用 `evaluation/smoke`。复用目录时沿用已存 intent，禁止改写其发布资格。派生路径可传 `--slug`、`--timestamp`；具体冲突按脚本返回处理。

## 阶段推进与上下文

按当前宿主的正式方式加载本包技能；文件加载时从本入口定位同级 `SKILL.md`，脚本根为本包根。进入阶段前取得其规则、必要参考及有效输入，已加载且未变化的内容可复用。全篇主控留在主会话，局部任务按阶段协议派发；委派显式给工作目录、当前任务及正确包入口。

| 阶段 | 技能与责任 |
|---|---|
| 0 | `phase0-conception`：构想、表达方向与作者要求 |
| 1 | `phase1-world-building`：世界条件与生活经验 |
| 2 | `phase2-character`：人物追求、关系、轨迹及运行资料 |
| 3 | `phase3-spine`：组织力、激励事件与幕/Arc |
| 4 | `phase4-structure`：序列及其因果、呈现关系 |
| 5 | `phase5-scene-arrangement`：当前场景清单与必要结果 |
| 6 | `phase6-scene-development`：正文、场景审阅与修订 |
| 7 | `phase7-integration`：整合、全文审阅与最终资格判断 |

交接时读[阶段与上下文协议](references/pipeline-overview.md)。输入存在后仍需确认内容足以支持本次决策；发现人物经历与世界条件不合等问题，回写最早失效的设计，再更新受影响下游。进度按实际阶段和当前任务维护，无需固定 todo 模板或清空重建。

参考由当前设计负责人按开放问题取材；有效材料直接复用，新增需求再加载 `design-doc-reference`。来源绑定与实际采用记录按交接协议执行。思想、迁移或剧情方向尚待比较、推荐或被退回时使用[大纲构思与回读](references/outline-exploration.md)，由当前设计负责人完成候选评价与补强，沿用已有共创授权。

Phase 2 的人物资产是当前写作链依赖。其构建和校验由 Phase 2 完成；进入逐场展开前，沿 [Phase 6 协议](../phase6-scene-development/references/execution-protocol.md) 对齐实际参与者，缺人物设计或构建决定时回 Phase 2。资产变化、未校验或校验失败时运行 `scripts/verify_phase2_assets.py <work_dir>` 并处理具体缺件；已通过且输入未变时复用结果。

## 设计交接与大纲裁决

Phase 5 完成后派发 `design-validation`，传工作目录、设计路径及本包技能入口；取得并读取 `pipeline/review/design_validation.yaml`。解决确定矛盾和阻止后续决策的缺失输入，按报告定位修正原阶段，只复查受影响关系。审美取舍交作者。

读取 `pipeline/run_state.yaml` 的 `outline_gate`；缺省为 `pending`。用户已明确免审或直接写完时记 `waived`，已批准当前大纲时记 `passed`；其余情况提交可供判断的大纲、关键剧情与链接，等待通过、修改或中止。更新该字段时保留 `run_intent` 等其他状态。

修改意见回到思想、来源理解或剧情决定，保留认可部分。已批准后若实质改变作者选定的方向或结果，回到同一大纲裁决；局部完善沿用已有批准。免审沿用本次授权范围。批准或免审后加载 Phase 6，按其实际协议继续。

## 正文到交付

写作产物与交付说明不自报执行模型的名称、版本或身份，不添加模型署名或生成来源声明；模型信息可保留在目录路径、内部运行元数据和日志中。主控将这条内容约束随任务传给设计、写作、修订和整合执行者，收尾时核对交付文本。作品题材涉及模型时，按题意叙述相关内容，不将其写成执行者的身份声明。

Phase 6 拥有逐场输入、writer、审阅、补丁与重写路由。入口只消费其完成状态及需要上游处理的问题，不重复定义局部步骤。缺少宿主自动 hook 时，按阶段协议显式执行必要脚本；文件存在和插件声明不能代替检查已经运行。

场景和机器通道按 Phase 6 当前合同完成后进入 Phase 7。正文生成与修改交给对应执行者，主控读取设计、诊断与状态组织工作。Phase 7 按索引装配、处理全文反馈并给出终态，最终正文为工作目录根的 `story.md`；`pipeline/` 保存设计、引用和执行所需工件。

完成需确认目标正文已经生成、明确要求得到承接、现有发布资格满足。格式与脚本通过只证明相应结构或状态，作品的审美判断仍由作者作出。
