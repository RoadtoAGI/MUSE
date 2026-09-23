# MUSE-serial-writing — 连载与衍生小说

连载与衍生小说创作 plugin：human-in-the-loop 剧情共创（卷级 ↔ 章级弹性档位）+ 章为发布单位的增量循环 + 跨 session 持久系列工作区。

## 包家族定位

| 包 | 职责 |
|---|---|
| **muse-writing** | 纯从零原创 pipeline（构想→整合八阶段）+ 原创写作入口，完全托管 |
| **muse-serial-writing（本包）** | 连载与衍生小说：同人、续写、番外、跨文风改编；卷章循环、台账与系列状态 |
| **muse-serial-distill** | 长篇连载拆解（参考语料 / 在连作品接管交付） |

## 可选 JEV 辅助构思

2026-09-23 发布：技能包 **v0.8.0**，配套 **muse-runtime v0.1.0**。运行包可从 [GitHub Release](https://github.com/RoadtoAGI/MUSE/releases/tag/muse-runtime-v0.1.0) 下载，也可在选定的 Python 环境安装：

```bash
python3 -m pip install "git+https://github.com/RoadtoAGI/MUSE.git@muse-runtime-v0.1.0"
```

卷级或章级共创形成实质候选后，可用 JEV 评价辅助补强、重构与推荐。模型说明候选的依据和取舍，作者采纳与决策回写继续按现有[共创协议](skills/serial-outline/references/collaboration-protocol.md)执行。

在执行命令的同一 Python 环境安装 `muse-runtime`：源码环境可运行 `python3 -m pip install /path/to/MUSE`，独立插件安装可使用由 MUSE 项目构建的 `muse_runtime-<version>-py3-none-any.whl`。执行环境通过 `MUSE_JEV_API_KEY` 提供官方密钥、`MUSE_JEV_TUZI_API_KEY` 提供 Tuzi 备用密钥，再显式指定系列根启用：

```bash
python3 -m muse_runtime mode set jev --work-dir /absolute/path/to/series-root
python3 -m muse_runtime brainstorm guide
```

安装插件不会自动启用 JEV。共创评价只读取指定系列根的 `.muse/runtime.yaml`，无配置时为 `standard`，不从全局、父目录或章目录继承。切回标准模式使用 `mode set standard`；标准流程无需安装运行包。公共指南说明候选输入与结果消费；指南和模式命令不发评价请求。

启用评价后，本轮问题、作者提供的上下文和候选优先发送到 TypeSafe；官方额度不足或限流时自动改用 Tuzi，可能包含未发表内容。无法取得评价时，本轮按未评价处理并继续原共创流程；作者明确要求必须取得评价时，保留该依赖并继续其他已授权工作。

## 核心机制

- **共创而非托管**：剧情走向由用户拍板，模型出候选与执行；`collaboration_mode: volume | chapter` 弹性档位
- **四技能入口**：`serial-outline`（立项、开卷和设计修订，组织世界、人物、主线及卷结构）/ `serial-chapter-writing`（章循环）/ `serial-aigc-guard`（AIGC 防治）/ `serial-reader-review`（读者审阅）；各入口自带前置自检
- **三级可追加大纲**：story_bible 总纲冻结 / 卷纲滚动追加 / 章纲只物化当前卷（lazy expansion）
- **三台账**：伏笔、世界事实和角色传记保留事实来源；章候选由 `ledger_tools.py` 转正，人物快照、导入和纠错使用对应已有工具
- **章为发布单位**：`publish_chapter.py` 四步事务保留已发布事实，文字勘误沿 manifest revision，连续性纠错按既有台账通道处理
- **章收束回灌**：`chapter-summarizer` 两段式 recap（summary 注入 + deltas 台账候选）+ 单元/卷 digest
- **series 持久状态机**：`series_state.yaml` + 入会恢复矩阵对账（`reconcile_series.py`），跨 session 多次进出同一部作品

## 包级能力流（维护者视图）

下图只说明入口、主要能力链与持久状态回流。运行时 gate、输入输出和失败语义由对应 `SKILL.md` 拥有；技能文本结构遵循 [MUSE 技能文本规则层架构](../../docs/Level_2_architecture/rule-layer-architecture.md)。

```text
用户需求 / 已有 series 工作区
│
├─ 建立或扩展连载设计
│  └─ serial-outline ──→ story bible / 卷纲 / 系列状态
│
├─ 创作下一章
│  └─ serial-chapter-writing
│     └─ 章规划 → 正文生成 → 审阅与有界修订 → 章收束 → 发布
│                                               │
│                                               └─→ 三台账 / recap / series_state
│
├─ AIGC 专项检查与修订
│  └─ serial-aigc-guard ──→ 放行结果或有界修订
│
└─ 读者反馈处理
   └─ serial-reader-review ──→ 分诊、修订或后续创作输入
```

## 目录

- `skills/` — 四技能入口 + 子件家族（大纲侧 world-bible-design / character-system-design / volume-outline / inspiration-research；章循环侧 writer / 编排 / 审阅 / 修订 / chapter-summarizer / continuity-check）
- `agents/` — 人物派生、可选 actor、writer、审阅、修订与章收束的包内元配置
- `scripts/` — 工作区生命周期脚本（init / import / materialize / publish / reconcile / ledger / lint 等）
- `hooks/` — 章 workspace 校验与 frozen/published 写保护
- 工作区字段契约权威：`skills/serial-outline/references/workspace-schema.md`
