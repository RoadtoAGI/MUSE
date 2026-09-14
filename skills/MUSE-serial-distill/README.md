# MUSE-serial-distill — 连载拆解姊妹包

长篇连载拆解 plugin：前推式分析（不要求结局在场）+ 双出口——名著/成熟长篇 → 连载范式参考语料；用户在连作品 → 接管续写交付（经消费方 import gate 导入）。

## 包家族定位

| 包 | 职责 |
|---|---|
| **muse-canon-distill** | 已完结名著拆解（结局回溯式）+ 场景文风检索 |
| **muse-serial-distill（本包）** | 连载长篇拆解：未完结假设、卷为批次前推、双出口 + 新章回流 |
| **muse-serial-writing** | 连载创作循环（本包出口 B 的消费方） |

## 核心机制

- **serial-analysis**：按卷或章窗口前推分析，按消费需求选择人物蒸馏与手艺标注；未完结卷 `open_ended`、方向性结论 `provisional` 暂定持有
- **出口 A（参考语料）**：五类连载范式卡（卷结构 / 章末钩子含类型序列 / 力量体系演化 / 节奏形态含爽点间隔与伏笔开收比 / 类型坐标对标反查）+ 场景切片入本包 KB，由包内 serial-scene-reference 检索；消费协议**参考反复制**
- **出口 B（接管交付）**：`takeover-distill`——类型判定先行 → 章节切分入册（`split_chapters.py`）→ 逐批前推分析（章窗口兜底）→ story_bible 归纳 → 分域设定集提取（分册模板逆运算 + 适用问题定位缺口）→ 卷纲与三台账/角色快照回填 → `export_gate.py` 七检自验 → 交换格式交付；fast/full 双档（fast 读 segments 摘要层）
- **导入档（无限流副本供材）**：world-card + 按使用范围选择的原作材料（fidelity 五档），schema 见 `takeover-distill/references/import-pack-format.md`
- **新章回流**：接管作品续写发布后按批增量蒸馏（已授权知识库分析 / 切片；写作侧台账只读）；serial-scene-reference 对自作品切片按 `published_seq` 时序过滤防未来信息泄漏
- **schema 权威归 serial-outline**：本包 `takeover-distill/references/templates/` 遵循接口并提供接管填写说明；派生视图不随交付、由导入方重建

## 目录

- `skills/` — serial-analysis / takeover-distill / character-kb-distill / serial-scene-reference
- `scripts/` — split_chapters.py（章节切分）/ export_gate.py（交付自验）/ extract_scene.py（原文切片）/ select_references.py（描述读取前按发布序筛选）
- `knowledge-base/` — 生成态语料库（骨架见其 README）
- 交换格式契约：`skills/takeover-distill/references/exchange-format.md`

知识库角色参考包由 canon 包 character-kb-distill 经明确 novel-dir 构建，工具来自 canon、数据保留原目录；依赖不可用时报告该参考功能缺口。接管快照、原文切分和本作检索由本包提供。源码入口不等于宿主已注册；独立安装缓存需在明确部署任务中更新。

各入口先解析本包实际安装根与当前作品路径；文档中的 `CLAUDE_PLUGIN_ROOT` 是 Claude 插件可用的定位方式，其他宿主从已加载技能位置取得包根。参考检索继续先按 `published_seq` 筛选可见范围再读描述；接管状态沿交换格式进入写作侧，参考语料沿对应参考协议使用。
