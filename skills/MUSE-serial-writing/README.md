# MUSE-serial-writing — 连载与衍生小说

连载与衍生小说创作 plugin：human-in-the-loop 剧情共创（卷级 ↔ 章级弹性档位）+ 章为发布单位的增量循环 + 跨 session 持久系列工作区。

## 包家族定位

| 包 | 职责 |
|---|---|
| **muse-writing** | 纯从零原创 pipeline（构想→整合八阶段）+ 原创写作入口，完全托管 |
| **muse-serial-writing（本包）** | 连载与衍生小说：同人、续写、番外、跨文风改编；卷章循环、台账与系列状态 |
| **muse-serial-distill** | 长篇连载拆解（参考语料 / 在连作品接管交付） |

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
