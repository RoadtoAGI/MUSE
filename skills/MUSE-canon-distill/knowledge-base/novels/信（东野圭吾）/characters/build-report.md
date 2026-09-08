# Build Report — 信（东野圭吾） — Phase B 蒸馏

## 基础信息

- **作品**：信（东野圭吾）
- **构建时间**：2026-05-24
- **builder**：character-kb-distill via novel-analysis Phase B
- **触发条件**：non-canonical 名著（无 novel-meta.yaml，未触发 Step 2f-2g claims.yaml 联网核对）
- **篇幅路径**：B2-short（union 场景集 ≈ 6.7 万字，远小于 1M context 窗口）

## 已构建（6 个角色）

| Role | role-slug | 出场场景 | locator_count | 选写理由 |
|------|-----------|---------|---------------|---------|
| 武岛直贵 | takeshima-naoki | S01-S22 全篇 POV | 26 | Protagonist；全书 22 场景 21/22 为他 POV |
| 武岛刚志 | takeshima-tsuyoshi | S01 / S04 / S06 / S21 / S22 + 每章狱中信 | 20 | Deuteragonist；全书最大情感杠杆（隐藏的赔罪信线 + 尾声合掌）|
| 白石由实子 | shiraishi-yumiko | S17-S20 + 多场早期配角 | 18 | 最终伴侣；"不再逃避"信念代表 + 隐性维系兄弟通信的桥梁 |
| 平野（社长）| hirano | S16 / S19 / 5-§7 辞职 | 20 | 主题宣讲者；三次关键谈话承担"歧视必然论"的全部展开 |
| 寺尾祐辅 | terao-yusuke | S08 / S10 / S22 + 5-§8 邀演 | 15 | 音乐知己；尾声同台演出渡桥人 + 自身完整弧光 |
| 中条朝美 | nakajo-asami | S11 / S12 / S13 | 18 | ARC-3 爱情对象；阶层差代表（反叛千金的不可执行性） |

## 未构建（3 个候选）

| Role | 候选评估理由 | 不蒸馏决策原因 |
|------|---------|--------------|
| 嘉岛孝文 | ARC-3 家族内部攻击者 / S12-S13 两场 / 关键识破者 | voice 单一（"识破" + "威胁" 两种姿态）/ 与中条父亲功能高度重叠 / 6 段框架会重复 |
| 中条父亲 | 阶层封锁代表 / S14 一场完整在场 + S12 末段短场 | voice 主要靠 S14 一场（信封交易 + 伏地恳求）/ 与孝文功能重叠 / phase2_character.yaml 已充分描述系统级关系 |
| 绪方先生 | 受害者一方代表 + 隐藏第三线揭示者 / S21 唯一场景 | 单场景 + 戏剧分量重但功能是"揭示器"（拿出哥哥赔罪信束）而非可扮演角色；voice 集中在"那不行"+"彼此，都很漫长啊！"两个短宣告，不足以撑 6 段框架 |

上述 3 个候选的"系统级功能定位 / 对比轴 / 关键场景"已在 `pipeline/phase2_character.yaml` 与 `pipeline/phase5_scenes.yaml` 中充分描述——下游续写如需扮演这些角色，应**从 phase2_character.yaml 的 supporting_cast 字段 + phase5_scenes.yaml 的对应场景片段**派生 runtime adapter，而非依赖知识库参考包。

## 补充输入

本次蒸馏中**未引用** `phase0_conception.yaml`（角色声音直接来源于场景文本，无需通过作品整体风格对齐）。

本次蒸馏中**未引用** `phase1_world.yaml`（角色身份与处境的世界规则部分通过场景内自陈直接呈现——如刚志的体力工身份 / 朝美的田园调布家境 / 由实子的关西出身 / 平野的社长身份——均无需从 phase1_world 派生）。

本次蒸馏**核心来源** = `pipeline/phase2_character.yaml`（系统设计图）+ `scenes/scene_S*.md`（22 个关键场景切片）。每个角色 SKILL.md 的"身份与处境 / 核心欲望 / 性格真相 / 声音框架 / 边界 / 弧光" 6 段的所有断言均带 scene-level locator。

## Phase B 流式蒸馏过程笔记

- 本次执行实际上是**已读 = 已熟 状态下的"流式蒸馏" 模拟**——orchestrator 在 Phase A 已完整读过全部 22 个场景（POV 全篇为直贵），所以 B2-short 路径的"按 scene_id 顺序读 + 每读完一场对本场角色自检"步骤被压缩为"评估每个候选的证据充分性后批量启动 build"。
- 这与 Phase B SKILL 的严格"todo 单位 = 读某场景"原则有差异——本次因 Phase A 已经把所有 scene 信息固化在 Phase A orchestrator 上下文里，所以省去了"逐场读取 → 信号判定" 的流式动作。
- 后续如重跑 Phase B（例如 character-kb-distill 模板升级），可以严格按"未读状态" 跑流式过程——此处保留作为执行记录。

## verify --check-structure gate 状态

所有 6 个已构建角色均通过 `verify_character_skills.py --check-structure` Layer 1 结构验证（exit 0），包括：
- locator 完整性（parse_locators 解析数 == build-meta.locator_count）
- 6 章节各 ≥ 1 条 locator
- 边界 bullet 每条 locator
- frontmatter 完整性
- role_slug 一致性（目录名 / build-meta.role_slug / frontmatter.name 三者匹配）
- character_map.json 映射完整
