---
name: scene-reference
description: 按当前写作问题检索名著场景原文，提供来源可追溯的文风与叙事候选；由创作主控按需调用，也可独立查找场景参考。
---

# 场景参考

取得 work_dir、本次 scene_id、人物处境、待解决的叙事问题、来源范围与输出位置。主控决定是否需要参考；已取得且仍适用的材料可直接复用。原文帮助观察表达，设计标注帮助理解作用，二者都须与当前人物、情境和叙述权限相容。理论依据见[研究名著](references/mckee-masterwork-study.md)。

## 检索与选择

用自然语言说明需要怎样的场景及表达方式，不设句数。genre 在确有题材范围时过滤；style-hint 写实际需要的语态与节奏，function-hint 写需要解决的叙事作用，缺失时不补造。用户选定作品用 --novel 限定，不能无匹配后静默换书。

通过当前安装位置执行本包脚本；Claude plugin 可使用 CLAUDE_PLUGIN_ROOT：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/kb_query.py   --query "人物处境与需要解决的表达问题"   --genre "当前题材" --source-medium novel   --output-dir "{work_dir}/pipeline/references" --scene-id S01
```

输出 `{work_dir}/pipeline/references/{scene_id}_ref.md`。可选 --lang、--style-hint、--function-hint 按实际输入传入；小说正文默认 novel，舞台、影视、广播或唱段参考按实际媒介传 --source-medium，跨媒介机制研究可显式扩展范围。题材相同不能保证文风适配，分数仅帮助排列候选。

候选差异会影响决定时，可先 --list 查看，再 --select "作品:scene_id,..." 物化已选场景；手选仍受媒介过滤。两步查询不因“高潮”或角色人数自动触发。top_k、pool、threshold 是检索参数，不是创作配额或语义合格判据。

短篇需正文参考包时，输出目录改为 `{work_dir}/pipeline/shortform` 并传 --shortform-pack，得到 reference_pack.md。包保留原文及表达所需标注；设计阶段已采用的机制由大纲与 inspiration_ledger 传递。显式采用来源世界时另传 --worldview "作品"，lore 与原文候选分别判断；缺 lore 不意味着当前已采用世界规则失效。

## 内容消费与交接

读取本次结果，核对来源、原文范围与当前用途，交主控实际有效路径；无适用结果或失败时交“无”。目录中的旧 ref 不因存在而继续生效。原文不要只用摘要替代；截断使关键反应、条件或结果缺失时读取返回的原文路径，或以 --max-chars 0 取得完整场景。

ref 内的 usage_protocol 与条目 tier 描述可参考的范围。full 可在实际适配时使用结构与句段，material 关注当前已采用的来源事实/专名，style 关注表达；分数、手选与同书来源均不能证明功能同构。当前作者要求、人物事实、世界条件及已采用设计决定实际范围，原文候选不自动改写这些条件。明确要求复用时，贴切材料按现有复用契约使用。

KB 未随插件提供、依赖缺失或命令失败时报告具体原因，由主控按无参考继续。需要配置时运行 kb_setup_check.py；常用 key 为 MUSE_KB_API_KEY，端点为 MUSE_KB_BASE_URL，兼容既有旧变量。无需每次检索前重新诊断。仅索引/候选存在不证明原文已进入 writer 上下文。
