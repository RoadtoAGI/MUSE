---
name: short-phase3-composition
description: 原创短篇的成稿与修订编排，在大纲批准或免审后装配写作简报、派发一次全文创作，组织已有检查与全文审修，交付 story.md。
---

# 短篇成稿与全文修订

取得当前有效的 conception、characters、outline、本篇范文与大纲批准。正文由 short-composer 生成，修订由 short-manuscript-reviser 完成；主控负责装配简报、运行检查与派发。

## 范文与写作简报

写作者只读一份写作简报 `pipeline/shortform/writer_brief.md`，由脚本把作者要求、构想、人物、事件、范文窗口、手法导航、本轮条目和指令装在一起。范文 `pipeline/shortform/reference_pack.md` 在构想阶段已取（short-phase0-conception 的“取本篇范文”），这里复用；缺失，或装配时脚本提示范文早于构想，就按那一节重取。

读过范文后写两行“本篇可以怎样用”：哪些写法可借，哪些不采用，对白的引号等标点不随范文时也写在这里，例如“范文逐屋搜店的动作连写可用于逐层搜写字楼；范文对白不加引号的写法不采用，本篇对白照常加引号”。再装配：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/assemble_writer_brief.py --shortform --work-dir {work_dir} --usage "<两行>"
```

脚本同时写 `brief_meta.yaml`（各节字数、范文占比与 exemplar_short / exemplar: none / facts_over_budget 标记）和 `disclosure_state.yaml`（审阅解锁的条目）。两份只记录、不拦派发，由脚本每次重算，主控不手写。

## 首次成稿

派发 short-composer 只给简报路径和这两行：

```text
写全文。只读 pipeline/shortform/writer_brief.md，写到 story.md。
本篇可以怎样用：<两行>
```

无范文时第二行写“本篇无范文，按人物声音与示范句写”。宿主未预载 agent 时，主控读取本包 `agents/{agent-name}.md`，将正文交给子执行者或要求其先读取该绝对路径；后续审阅和修订派发同样处理。composer 一次写完整篇 `story.md`，写入后 hook 检查设计用词、与范文的连续重合与字数，问题由它在同一会话改。宿主不触发 PostToolUse hook 时（如 Codex），主控在正文落盘后运行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/shortform_story_guard.py --story {work_dir}/story.md`，exit 2 时把输出交 composer 改，改完再跑一次。回执列出读取的输入，通常只有简报；已有有效正文的恢复任务直接进入当前审阅或修订步骤。

正文、审阅与修订的子执行者默认继承主会话所选模型，注册 agent 与通用子执行者同样适用；仅按作者明确的任务指定覆盖。实际调用方落实该选择，宿主限制使其不可用时报告受影响任务。

## 检查与修订

正文落盘后运行现有全文检查；同一正文已有成功报告时复用，内容变化才刷新：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ai_filler_lint.py --story {work_dir}/story.md --work-dir {work_dir}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lexical_stats.py --story {work_dir}/story.md --work-dir {work_dir}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dialogue_lint.py --story {work_dir}/story.md --work-dir {work_dir}
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wholetext_gate.py --story {work_dir}/story.md --work-dir {work_dir}
```

前三份报告与 wholetext_gate 的定位都是线索，交审阅者结合正文判断。wholetext_gate exit 2 为工具或输入错误，停止自动修订并报告；exit 0 或 1 都进入全文审阅。

派发 short-story-review，传工作目录、本轮 N、简报路径，以及作者开启读者审阅时的报告路径（未开启明示“无”）。N 从已有报告最大轮次之后递增，避免恢复任务被更高编号的旧报告覆盖。审阅规则和 schema 归该技能：

- `PASS`：进入终验。
- `REVISE`：先用同一 `--usage` 重新装配简报，脚本据已有审阅文件附上条目；再按 findings 派发 short-manuscript-reviser。需修的 findings 只涉及“文本质量”“范文语域”时用 `de-AI` 模式，其余用 `reader` 模式；派发写明报告路径与简报路径。问题遍及全文、局部修订解决不了时，改派 short-composer 按新简报重写。修订后刷新改变正文的检查并复审。
- 修订 `failed`：停止并报告缺失输入或执行失败。`partial` 若需改变人物或大纲，回到相应设计；其余未决项交同一复审，不重复改写相同措辞。

de-AI 修订最多两轮，reader 修订与复审最多三轮，不为通过数值无限重试。读者审阅（reader-review）在作者派发时明确开启才跑，默认不跑；开启时仅传当前 `story.md` 和输出路径，报告 `input_snapshot: story.md`，交 short-story-review 判断是否构成问题。单纯审美偏好交作者。

## 终验与交付

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_shortform_review_complete.py --work-dir {work_dir}
```

终验检查当前正文、当前审阅、硬要求覆盖及既有机器资格。报告对应旧正文时更新受影响检查；输入错误修输入，实际未解决问题回其负责环节。复查仍受原轮数限制。

自动修订达到上限、工具失败或需要作者裁决时，沿用 `pipeline/shortform/review/quality_gate_failed.yaml`，记录 `reason`、`rounds: {de_ai, reader}` 和具体 `unresolved`，保留现有正文并报告待处理项。终验通过后交付 `story.md`。
