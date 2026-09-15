<div align="center">

# MUSE

**以故事理论组织创作的 AI 写作系统**

**简体中文** | [English](README.en.md)

描述你想写的故事，从构思开始，逐步完成正文。

[![arXiv](https://img.shields.io/badge/arXiv-2609.15188-b31b1b.svg)](https://arxiv.org/abs/2609.15188)

[论文](https://arxiv.org/abs/2609.15188) · [PDF](https://arxiv.org/pdf/2609.15188) · [引用](#引用)

[理论基础](#麦基理论如何指导创作) · [名著知识库](#从名著中学习写法) · [工作原理](#工作原理) · [技能包](#技能包) · [快速开始](#快速开始) · [仓库结构](#仓库结构)

</div>

MUSE 是一个 AI 写作系统，支持**原创小说、剧本、连载和衍生小说**。它用罗伯特·麦基的故事理论指导设计，从名著知识库中检索相关范例，再安排人物表演、场景写作和修订。

你可以用自然语言描述设定、人物关系、关键事件、氛围和文风。这些需求逐步形成世界设定、人物动机、大纲和场景计划，保存在工作区中，供后续写作读取；最终交付故事正文及设计、修订材料。我们将从写作需求发展出完整故事的任务称为 **Vibe Narrativizing**。

仓库还提供文学作品拆解、人物资料蒸馏和参考检索工具。技能说明和知识库标注以中文为主，语料语言及英文原文入口见[技能合集说明](skills/README.md)。

## 论文

**[MUSE: A Theory-Harnessed Story Engine for Vibe Narrativizing](https://arxiv.org/abs/2609.15188)**

Jianxiang Ma, Xiaocui Yang, Daling Wang, Yuesong Hou, Mingfu Zhang, Yichen Gao, Junzhao Huang · arXiv, 2026

论文介绍了故事知识如何形成创作指导，以及智能体框架与上下文工程如何将指导和已有决定用于设计、表演、写作与修订，并通过四个基础模型上的实验、组件消融和案例分析展示效果。

## 麦基理论如何指导创作

罗伯特·麦基的《故事》讨论事件、人物与结构如何共同产生叙事意义，《对白》进一步分析人物如何通过言语采取行动。MUSE 从中提炼出与创作决定直接相关的指导，并将其用于故事设计、人物表演和正文修订。

| 理论原则 | 在 MUSE 中的应用 |
|---|---|
| **压力下的选择** | 人物设计明确追求、顾忌和关系；场景表演通过人物愿意付出的代价、退缩或坚持表现性格 |
| **预期落空** | 人物采取行动，得到出乎预期的回应，因而改变办法。情节设计据此连接行动、后果和下一次选择 |
| **场景中的价值变化** | 场景计划写明信任、自由、安全或亲密等处境如何变化，正文通过事件和反应完成转折 |
| **对白作为行动** | 人物通过言语试探、安抚、索取或回避；对白结合动作和处境，让读者理解未明说的意图，即潜台词 |
| **主控思想** | 构想提出故事的表达方向，结构设计通过高潮中的选择及其后果，发展故事对人物经验的认识 |

例如，一名记者想替父亲洗清污名，却查到父亲参与造假。新的证据改变了她的处境，也迫使她在公开真相与保护家人之间作出选择。公开真相会使她失去原先追求的结果，这个代价使最终选择具有分量。

MUSE 据此编写分阶段技能、角色材料和审阅方法，并为小说和连载设计文件结构及调用流程。相关技能参考：[故事构想](skills/MUSE-writing/skills/phase0-conception/references/mckee-premise.md)、[人物设计](skills/MUSE-writing/skills/phase2-character/references/mckee-character.md)、[场景设计](skills/MUSE-writing/skills/phase5-scene-arrangement/references/mckee-scenes.md)和[潜台词](skills/MUSE-writing/skills/dialogue-craft/references/subtext-theory.md)。

## 从名著中学习写法

名著知识库保存小说、戏剧及长篇连载的分析材料：全篇和分阶段设计、人物档案、场景原文、文风画像、逐节拍手法分析，以及归纳叙事机制的灵感卡。对白事件记录连续回合中的关系、压力和言语行动。

创作时，系统选取少量相关范例，把原文和分析交给模型参考，这就是 **few-shot**。不同任务需要不同材料：

| 创作环节 | 使用的知识库材料 | 辅助的创作决定 |
|---|---|---|
| **构思** | 原作构想、灵感卡、相关原文与机制解释 | 哪种人物关系、处境或形象能承载想表达的经验 |
| **大纲设计** | 世界规则、情节主线、序列与场景分析 | 如何建立因果条件、组织冲突、安排揭示与高潮 |
| **人物塑造** | 人物档案、行为依据、连续对白事件 | 人物在当前关系和压力下如何选择、回应与表达 |
| **正文写作** | 场景原文、文风卡、节拍与手法标注 | 如何安排动作、转折、叙述距离、句子节奏和留白 |
| **修稿** | 已采用的参考、设计决定及对应正文 | 怎样修复正文问题，保留已确定的文风和场景意图 |

检索时，大纲设计者查找原作怎样组织情节、这些写法需要什么条件；场景写作者按人物处境和所需文风选择原文；人物排练则查找相近关系和压力下的对白。选中的材料连同使用说明写入工作区。设计阶段采纳的灵感随大纲交给写作者，修稿时继续按已确定的用途参考。

例如，要写一则“在监视下传递秘密”的童话，可以从[双层语义灵感卡](skills/MUSE-canon-distill/knowledge-base/inspiration/double-layer-code-speech.yaml)理解表层故事与隐藏信息的关系，再通过[《三体Ⅲ》相应场景的手法分析](skills/MUSE-canon-distill/knowledge-base/novels/三体Ⅲ-死神永生/craft_notes/scene_S26_beats.yaml)观察重复、道具和省略如何组织信息，最后结合[场景原文](skills/MUSE-canon-distill/knowledge-base/novels/三体Ⅲ-死神永生/scenes/scene_S26.md)查看信息在何处出现、句子如何重复、结尾怎样落下。写作者再按新作的人物、世界和作者指定用途采用这些材料。

相关入口：[设计参考](skills/MUSE-canon-distill/skills/design-doc-reference/SKILL.md) · [人物对白参考](skills/MUSE-canon-distill/skills/dialogue-reference/SKILL.md) · [场景参考](skills/MUSE-canon-distill/skills/scene-reference/SKILL.md) · [语料说明](skills/README.md#knowledge-base)。

## 工作原理

MUSE 用智能体运行框架组织创作：主控安排任务，专门角色负责设计、表演、写作或审阅，工具读写工作区中的材料。当前阶段读取相关技能和前序结果，后续阶段接着发展已作出的决定。

下图展示完整故事工作流中的任务顺序、参考来源和修订去向。

[![MUSE 论文方法图：设计、人物表演、正文创作、名著参考与审阅修订](assets/muse-method.png)](assets/muse-method.png)

设计阶段依次建立构想、世界、人物、主线、序列结构和场景计划。高潮需要什么条件，决定前面的冲突如何铺设。进入正文创作后，人物按自己所知的处境提出可能的动作、反应和对白，写作者结合场景计划、人物材料和当前参考，安排视角、节奏与细节。

审阅者对照设计检查正文，把问题交回写作者或相应设计阶段。连载还会在章末保存摘要、世界事实、人物经历和未解决的伏笔，供下一章使用。各阶段从共享工作区读取本次任务所需的内容。

## 技能包

| 技能包 | 适用任务 | 主要产物 |
|---|---|---|
| [MUSE-writing](skills/MUSE-writing/README.md) | 原创短篇、中篇小说；原创或改编剧本 | 故事设计、人物材料、草稿、审阅结果与终稿 |
| [MUSE-canon-distill](skills/MUSE-canon-distill/README.md) | 小说与戏剧拆解；结构、人物、对白和文风参考检索 | 场景分析、人物参考包、灵感卡与检索资产 |
| [MUSE-serial-writing](skills/MUSE-serial-writing/README.md) | 连载、同人、续写、番外与跨文风改编 | 系列与卷章大纲、章节正文、连续性记录与系列状态 |
| [MUSE-serial-distill](skills/MUSE-serial-distill/README.md) | 长篇及在连作品分析；已有作品的接管续写准备 | 连载范式参考与结构化接管材料 |

`MUSE-canon-distill` 为两个写作包提供文学参考；`MUSE-serial-distill` 为 `MUSE-serial-writing` 提供连载参考与续写材料。

## 快速开始

### 在智能体工作区中使用技能

将仓库克隆到智能体可以访问的工作区：

```bash
git clone https://github.com/RoadtoAGI/MUSE.git
cd MUSE
```

通过当前宿主的技能加载方式使用对应入口，或让智能体读取下表中的 `SKILL.md` 并按其说明执行。保留完整的包目录，让技能可以访问配套脚本、参考材料与角色定义。各包的依赖和配置见对应 README。

| 你想完成的任务 | 技能入口 |
|---|---|
| 写一篇完整的原创短篇 | [short-story-writing](skills/MUSE-writing/skills/short-story-writing/SKILL.md) |
| 写原创中篇，或尚未确定篇幅的完整小说 | [story-writing](skills/MUSE-writing/skills/story-writing/SKILL.md) |
| 创作或改编影视、戏剧、戏曲剧本 | [screenplay-writing](skills/MUSE-writing/skills/screenplay-writing/SKILL.md) |
| 规划连载、续作或番外 | [serial-outline](skills/MUSE-serial-writing/skills/serial-outline/SKILL.md) |
| 为已有系列创作下一章 | [serial-chapter-writing](skills/MUSE-serial-writing/skills/serial-chapter-writing/SKILL.md) |

例如，可以向智能体发送：

```text
读取 skills/MUSE-writing/skills/short-story-writing/SKILL.md，按其中流程创作。

写一篇发生在旧天文台的完整悬疑短篇。主角是一位退休的仪器师，
四十年后回来修理自己制作的钟。人物数量少，语言克制，
结尾要改变读者对开场事件的理解。用中文写作，
将工作文件与正文保存到 results/observatory-mystery/。
```

原创短篇采用“构想 → 人物 → 大纲 → 成稿与审阅”的四阶段路径；完整小说采用八阶段路径。连载小说按卷、章逐步推进，由作者裁决剧情方向，工作区保存跨章连续性。

### 使用 Python 八阶段运行器

独立 Python 运行器通过模型 API，依次执行 `MUSE-writing` 的 `phase0` 至 `phase7`。它提供技能与参考加载、前序产物读取、阶段产物写入等工具。

需要 **Python 3.10+**，以及**支持工具调用的 OpenAI 兼容接口**。在仓库根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，设置 `providers.compatible.base_url` 和 `routing.default_model`。通过环境变量 `MUSE_API_KEY` 提供密钥；示例配置中的 `api_key_ref: "env:MUSE_API_KEY"` 已对应这一变量，也支持在本地 `.env` 中设置。

```bash
export MUSE_API_KEY='your-api-key'

PYTHONPATH=src python3 -m open_muse.main \
  --config config.yaml \
  "写一个发生在旧天文台的悬疑故事，语言克制，人物数量少。"
```

运行器按顺序执行以下阶段：

| 阶段 | 创作任务 |
|---|---|
| 0 · 构想 | 确立故事前提与控制思想，即故事最终表达的核心判断 |
| 1 · 世界 | 建立故事环境与世界事实 |
| 2 · 人物 | 发展人物欲望、关系与变化轨迹 |
| 3 · 主线 | 组织核心冲突与情节推进 |
| 4 · 结构 | 编排序列及其因果关系 |
| 5 · 场景编排 | 规划场景与预期变化 |
| 6 · 正文展开 | 撰写故事正文 |
| 7 · 整合 | 审阅与整合文稿 |

产物保存在以下目录中：

```text
results/<benchmark>/open-muse/<model>/<timestamp>/<query-id>/
├── story.md       # 从正文展开或整合产物中选取的最终故事
└── pipeline/      # 各阶段产物：YAML 设计与 Markdown 正文、审阅材料
```

运行日志也保存在产物目录附近。可用 `--model` 覆盖配置中的模型，用 `--benchmark`、`--query-id` 和 `--timestamp` 标记本次运行；完整参数见 `PYTHONPATH=src python3 -m open_muse.main --help`。生成过程会调用所配置的服务，并产生相应 API 费用。

Python 运行器负责顺序执行八阶段。使用知识库检索、人物排练和角色分工时，在智能体工作区加载对应技能包。

### 配置文学参考检索

[知识库配置说明](skills/MUSE-canon-distill/README.md)介绍了检索依赖，以及 `MUSE_KB_API_KEY`、`MUSE_KB_BASE_URL` 和 `MUSE_KB_EMBEDDING_MODEL` 的设置。使用时在目标环境中重新合并场景索引并构建向量，索引和查询使用同一个 embedding 模型。

语料组织、语言覆盖与来源说明见[技能合集的知识库介绍](skills/README.md#knowledge-base)。

## 仓库结构

```text
MUSE/
├── README.md               # 中文首页
├── README.en.md            # English overview
├── skills/                 # 四个写作与文学分析技能包
│   ├── MUSE-writing/
│   ├── MUSE-canon-distill/
│   ├── MUSE-serial-writing/
│   └── MUSE-serial-distill/
├── src/open_muse/          # Python 智能体循环、工具与阶段运行器
├── tests/                  # 运行器与写作脚本测试
├── config.example.yaml    # 模型服务配置示例
├── requirements.txt       # 运行依赖
└── requirements-dev.txt   # 测试依赖
```

每个技能包的 `skills/` 保存任务说明，各技能下的 `references/` 保存配套材料，`agents/` 定义专门角色，`scripts/` 与 `hooks/` 支持执行和校验。

## 运行测试

安装测试依赖，运行已配置的运行器与写作脚本测试：

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

这些测试使用本地样例与模拟调用，无需 API 密钥。

## 引用

如果本项目对你的研究有帮助，请引用：

```bibtex
@misc{ma2026muse,
  title         = {{MUSE}: A Theory-Harnessed Story Engine for Vibe Narrativizing},
  author        = {Jianxiang Ma and Xiaocui Yang and Daling Wang and Yuesong Hou and Mingfu Zhang and Yichen Gao and Junzhao Huang},
  year          = {2026},
  eprint        = {2609.15188},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CL},
  url           = {https://arxiv.org/abs/2609.15188}
}
```
