# MUSE-writing

基于罗伯特·麦基《故事》理论的 AI 创意写作 plugin。从一句创意构想到完成稿的 8 阶段 pipeline：

```
Phase 0 构想 → 1 世界 → 2 人物 → 3 脊椎 → 4 结构 → 5 编排 → 6 展开 → 7 整合
```

聚焦中短篇小说，单次会话可完成从立意到成稿的全流程。

## 装上即用

```bash
pip install -r requirements.txt
```

用自然语言触发，Claude Code matcher 按 query 性质自动命中对应入口 skill。例如：

| 你说 | 命中 |
|---|---|
| "帮我写一个完整的 8000 字悬疑短篇" | `short-story-writing` |
| "写一个完整的中篇小说" / 篇幅未明的原创成稿 | `story-writing` |
| "把《X》改编成京剧" | `screenplay-writing` |

如需显式触发，可直接写 `Skill <skill-name>`。单独设计任务可在用户 prompt 中指定阶段调用与交付要求。

## 写作入口与内部能力

| Skill | 职责 |
|---|---|
| `screenplay-writing` | 原创或改编的戏剧、戏曲、影视剧本 |
| `short-story-writing` | 原创短篇：短链 Phase 0→3，单次直写成稿 |
| `story-writing` | 原创中篇或篇幅未明的完整小说：Phase 0→7 |
| `prototype-research` | 由 screenplay-writing 在改编、历史或戏曲题材下内部调用的 reference_only 调研层 |
| `phase0-conception` … `phase7-integration` | 完整小说的八个阶段 |
| `short-phase0-conception` … `short-phase3-composition` | 短篇的四个阶段 |
| `character-persona` | 将已有人物设计构建为角色 Skill 包 |
| `writer` / `reviser` / `scene-reviewer` | 分场写作、修订与审阅的 subagent |
| `short-composer` / `short-story-review` / `short-manuscript-revision` | 短篇成稿、全文审阅与修订的 subagent |

衍生小说（同人、续写、番外、跨文风改编）与连载创作使用 `MUSE-serial-writing`。各入口的触发条件以 frontmatter description 为准。

完整 skill 清单见 [`skills/`](skills/)；subagent 元配置见 [`agents/`](agents/)。

## 目录结构

```
MUSE-writing/
├── skills/             # 原创小说与剧本入口（3 个）+ 全链 phase skill（8 个）+ 短链 phase skill（4 个）+ 辅助 skill
├── agents/             # subagent 元配置
├── scripts/            # Phase 间机械脚本（脚手架 / 验收 / 抽取）
├── hooks/              # 非阻塞 hook（阶段注入 / 保护 / 验证）
├── requirements.txt    # Python 依赖（pyyaml + jieba）
└── README.md
```

## 边界与扩展

- 本包提供原创短篇、中篇成稿与剧本创作。内部阶段可按用户指定任务组合，沿用各阶段的输入输出契约。
- `MUSE-canon-distill` 提供名著语料、设计参考、场景检索与人物资料蒸馏；`prototype-research` 由 screenplay-writing 调用，取得原型资料。
- `MUSE-serial-writing` 负责连载与衍生小说，使用系列工作区、卷章设计和逐章创作。

## 环境变量

| 变量 | 作用 |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}` | plugin 资源引用前缀，由 Claude Code 运行时注入 |

## 理论根基

McKee, Robert. *Story: Substance, Structure, Style, and the Principles of Screenwriting*. ReganBooks, 1997.

skill 内引用的核心概念（节拍 / 场景 / 序列 / 幕 / 控制思想 / 价值轴 / 转折点等）均锚定原著。
