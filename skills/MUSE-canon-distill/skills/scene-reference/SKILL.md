---
name: scene-reference
description: 按当前创作问题检索名著场景原文，提供有来源的文风与叙事参考。由创作主控按需调用，也支持独立场景取材。
---

# 场景参考

取得 work_dir、本次 scene_id、人物处境、待解决的叙事问题、来源范围与输出位置。主控决定是否需要参考；已取得且仍适用的材料可直接复用。原文帮助观察表达，设计标注帮助理解作用，二者都须与当前人物、情境和叙述权限相容。理论依据见[研究名著](references/mckee-masterwork-study.md)。

## 检索与选择

用自然语言说明人物处境、表达需要及复合题材，作为 --query；作者明确限定“仅某题材”时才传 --genre，它是硬过滤；题材只是描述性线索时放进 --query，不传 --genre。过滤为空时脚本返回 `results: 0` 并提示改放线索，不自动放宽作者限定。style-hint 写实际需要的语态与节奏，function-hint 写待解决的叙事作用，缺失时省略；function-hint 同时成为每条参考顶部“本场表达问题”一行。用户选定作品用 --novel 限定；无匹配时保留该来源缺口。

通过当前安装位置执行本包脚本；Claude plugin 可使用 CLAUDE_PLUGIN_ROOT：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/kb_query.py   --query "人物处境、复合题材与需要解决的表达问题"   --source-medium novel   --output-dir "{work_dir}/pipeline/references" --scene-id S01
```

输出 `{work_dir}/pipeline/references/{scene_id}_ref.md`。每条参考先给 `<exemplar_excerpt>`：本场表达问题、范文怎样做、迁移条件，以及围绕手艺原句锚截取的一段原文（默认不超过 600 字，`--exemplar-chars` 调整，0 关闭）；完整原文与分析块在其后，供 full / material 档复用。可选 --lang、--style-hint、--function-hint 按实际输入传入；小说正文默认 novel，舞台、影视、广播或唱段参考按实际媒介传 --source-medium，跨媒介机制研究可显式扩展范围。题材相同不能保证文风适配，分数仅帮助排列候选。

输出不在 `{work_dir}/pipeline/...` 下时，显式传 `--work-dir "{work_dir}"` 绑定作品。任务已给出必要条件时，可逐条传 `--must '<一个条件>'`；条件沿本次用途，不额外生成检查清单。

沿当前作者决定传 --reuse-mode maximize_apt_reuse 或 style_only，已明确采用领域时传 --intended-domains 后接既有领域列表：world_rule、reveal_structure、protagonist_archetype、scene_carrier、prose_style_imitation。style_only 始终限定表达；仅 prose_style_imitation 输出 style，仅 world_rule 或 world_rule 加 prose_style_imitation 至多输出 material；其他组合保留具体领域，由采用方约束使用范围。脚本把用途与候选档位取交集写入 ref 的 reuse_tier / reuse_mandate，并保留显式 mode 与 domains；省略时沿用既有复用契约。不同来源用途分别保留，不能以最高档覆盖较窄用途。

已有 Phase 0 时传 --canon-reference-profile 后接当前 YAML 的绝对路径。脚本读取 canon_reference_profile.user_reference_materials，以 work 与实际作品名精确匹配，把逐作品 reuse_mode / intended_domains 写入各条 reference_scope；stance: avoid 的来源跳过。两个全局参数仅用于本次共同限制，不能覆盖较窄的逐来源范围。无法精确匹配时由主控绑定明确来源；不凭相似书名猜测。独立 --worldview 来源也按同一 profile 判断用途。

候选差异会影响决定时，可先 --list 查看，再 --select "作品:scene_id,..." 物化已选场景；手选仍受媒介过滤。两步查询不因“高潮”或角色人数自动触发。top_k、pool、threshold 是检索参数，不是创作配额或语义合格判据。

短篇需正文参考包时，输出目录改为 `{work_dir}/pipeline/shortform` 并传 --shortform-pack，得到 reference_pack.md。包保留原文及表达所需标注；设计阶段已采用的机制由大纲与 inspiration_ledger 传递。显式采用来源世界时另传 --worldview "作品"，lore 与原文候选分别判断；缺 lore 不意味着当前已采用世界规则失效。

## 写作用范文窗口

写正文或修订前取范文时传 `--render exemplar`。范文窗口是从检索到的名著场景正文里连续截取的段落，不带分析文字，供写作者学口吻，不提供情节。审阅者和设计阶段仍用默认的 `--render full`。

选范文分两段。先选作品：过滤后按 `--style-hint` 与各作品 style 向量的相似度（权重 0.7）和情节相近程度（0.3）给作品排序，取前三部；`--novel` 点名时只用点名的作品。再在每部作品里取与 `--query` 情节最近的场景截窗口，合计达到 `--budget-chars`（默认 4000，英文按 1 汉字约 0.6 词折算）即停，收尾最多超到 1.5 倍。两部以上时任一作品先取到预算的 60% 为止，不够再补；同一段原文收在两部作品里时只取一处。传了 `--person` 时窗口从第一段人称相符的叙述段落起截。style_card 标 `exemplar_pool: on_request` 的作品（如口播转写）不进默认范文池，`--novel` 点名才用。

文件头依次是 query、过滤条件、池的构成（场数、作品数、最大一部占比）、style hint、来源作品与场景、字数，再每个窗口一行描述：人称、语域、对白占比、该作品的口吻与对白写法。“本场可以怎样用”由主控写进派发，不写进文件。文风相似度在作品之间的差距不大，排序只是初选：主控先看描述行，判断某部作品的写法不合本篇时，用 `--exclude-novel <作品>` 排除它重查，其他条件不变，并在派发记录里写明；找不到合用的范文就按“无范文”派发。

参数从场景卡和 Phase 0 生成，不只按情节写一句话：

| 参数 | 取值 |
|---|---|
| `--lang` | 交付语言 |
| `--original-only` | 默认传，只取原作语言与交付语言相同的作品；库里该语言原作不够时由主控去掉，并在派发记录里写明放宽 |
| `--person` | 场景卡的叙述方式：紧贴人物的第三人称传 third，第一人称传 first |
| `--register` | Phase 0 `style_directives` 或人物声音框架里的口语/书面判断：口语传 colloquial，书面传 literary；没有这类判断就不传。英文语域阈值尚未标定，传了也不过滤，头部会写明 |
| `--style-hint` | 本篇要的口吻，用文风卡的说法写：叙述人称与距离、用词、对白写法、节奏，一两句；由 Phase 0 `style_directives`、叙述方式和视角人物的声音写成。它决定选哪几部作品 |
| `--query` | 人物处境和场景动作，一句话；它决定在选中的作品里取哪几场 |
| `--genre` | 只在作者限定题材时传 |
| `--novel` | 同人、续写、改编这类点名原作的任务传原作名，窗口全部取自它；可重复传多部 |
| `--exclude-novel` | 看过描述行判断某部作品不合用时传，排除后重查；可重复 |

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/kb_query.py   --query "人物处境与场景动作" --style-hint "第一人称口语独白，句子短，对白少"   --lang zh --original-only --person first --register colloquial   --budget-chars 4000 --render exemplar   --output-dir "{work_dir}/pipeline/references" --scene-id S01
```

这些过滤都在向量打分之前执行。过滤后没有候选时，文件写 `results: 0` 并写明清空候选的条件，如“register=colloquial 清空候选”；脚本不自动放宽，主控按“无范文”派发，或显式去掉一个条件重查并记录。合计不足预算时 `chars` 行写明不足。

## 内容消费与交接

读取本次结果，核对来源、原文范围与当前用途，交主控实际有效路径；无适用结果或失败时交“无”。头部 `results: 0` 的文件只是检索记录，不是有效 ref，不得作为路径交给 writer。目录中的旧 ref 不因存在而继续生效。原文不要只用摘要替代；截断使关键反应、条件或结果缺失时读取返回的原文路径，或以 --max-chars 0 取得完整场景。

ref 内的 usage_protocol 与条目 tier 描述可参考的范围。full 可在实际适配时使用结构与句段，material 关注当前已采用的来源事实/专名，style 关注表达；分数、手选与同书来源均不能证明功能同构。当前作者要求、人物事实、世界条件及已采用设计决定实际范围，原文候选不自动改写这些条件。明确要求复用时，贴切材料按现有复用契约使用。

KB 未随插件提供、依赖缺失或命令失败时报告具体原因，由主控按无参考继续。需要配置时运行 kb_setup_check.py；常用 key 为 MUSE_KB_API_KEY，端点为 MUSE_KB_BASE_URL，兼容既有旧变量。无需每次检索前重新诊断。仅索引/候选存在不证明原文已进入 writer 上下文。
