# Build Report — 射雕英雄传（Phase B 完整蒸馏）

构建时间：2026-04-14 首批，2026-04-15 修订
模式：reference
来源：pipeline/phase2_character.yaml + 27 个 union 场景切片

## Phase B 执行摘要

- **候选 pool**（Step B0 自动判定）：12 个角色
- **实际蒸馏**：12 个角色全部蒸馏
- **Step B2 路径**：union 预算约 27 场景 ≤ 50 万字 → 走 **B2-short**（union 流式）
- **Step B3 升级读 full_text.md**：0 次——所有佐证从场景切片取得
- **Step B4 未蒸馏**：0 个（候选 pool 全部入选）
- **Step B5 程序化验证**：12/12 通过（所有硬约束）
- **canon-ending.md**（V2 终局产物）：4 个角色具有"不可逆终局事件"——已产出

## 已构建（12 个角色）

| 中文名 | role-slug | 类型 | SKILL locator 数 | canon-ending |
|--------|-----------|------|:---:|:---:|
| 郭靖 | guo-jing | protagonist | 16 | — |
| 黄蓉 | huang-rong | supporting（第二主角级） | 8 | — |
| 欧阳锋 | ouyang-feng | antagonist.primary | 4 | ✓ 疯癫 |
| 洪七公 | hong-qigong | supporting | 5 | — |
| 黄药师 | huang-yaoshi | supporting | 6 | — |
| 周伯通 | zhou-botong | supporting | 6 | — |
| 一灯大师 | yideng-dashi | supporting | 10 | — |
| 杨康 | yang-kang | antagonist.mirror | 11 | ✓ 毒死 |
| 柯镇恶 | ke-zhene | supporting | 7 | — |
| 完颜洪烈 | wanyan-honglie | antagonist.political | 6 | — |
| 成吉思汗 | genghis-khan | antagonist.existential | 11 | ✓ 病崩 |
| 李萍 | li-ping | supporting（边界入选） | 6 | ✓ 自刎 |

总计 **96 条原文引用定位**，每条都从 scenes/*.md 切出对应片段进入 references/key-dialogues.md。

## 未构建（0 个）

所有 12 个候选角色都在流式阅读过程中积累到了足够的原文佐证，无一遗漏。

### 边界入选说明

- **李萍**：Phase 2 YAML 中仅有单条"精神遗产"功能描述，按严格启发式可能不入 pool；但 S01+S13 两场景对比形成强 character_arc，且临终独白提供了定性对白"无愧于心"——信号达标故入选。
- **完颜洪烈**：作为 antagonist 字段全体入选；虽然他在全书声音显露较少（大量行为由下属外包），但 S01 柴房定情+S04 殉情反应+S08 密谋揭穿三场景形成完整的"骗婚者"人格链条，信号充分。

## canon-ending.md 说明

根据 V2 Phase B Step B2-short（3）"不可逆终局事件"约定，本次为以下 4 个角色补产 `references/canon-ending.md`：

| 角色 | 终局类型 | 场景定位 |
|------|---------|---------|
| 李萍 | 死亡（自刎） | scenes/scene_13.md:L10-L11 |
| 成吉思汗 | 病崩（临终未能回答英雄论） | scenes/scene_15.md:L8-L8 |
| 杨康 | 毒发扭曲而死 | scenes/scene_12.md:L36-L44 |
| 欧阳锋 | 发疯（逆练九阴+假梵语+天灵盖一棒） | scenes/scene_31.md:L4-L4 |

其余 8 个角色在《射雕英雄传》时间线内**无不可逆终局**：
- 郭靖、黄蓉、洪七公、黄药师、周伯通、一灯大师、柯镇恶——南归襄阳/华山论剑后各有去处，未死未疯未封印
- 完颜洪烈——金国侵宋阴谋失败，但身为赵王仍存活
- （均将在《神雕侠侣》续写中再次出现）

## 补充输入

本次蒸馏未读取 phase0_conception.yaml 和 phase1_world.yaml——所有角色的人格维度都能从 phase2_character.yaml 的对比轴/张力 + 场景切片中充分刻画。

## 修订记录

- **2026-04-14** 首次蒸馏 12 角色
- **2026-04-15** 响应 verify_character_skills.py 硬约束校验：
  - 修正所有"单行号 `:LN`"格式为 `:LN-LN`
  - 补齐 ke-zhene 边界第 2 条+wanyan-honglie 声音框架段的缺失 locator
  - 同步所有 build-meta.yaml 的 locator_count
  - 新增 4 个角色的 canon-ending.md

## Step B5 硬约束验证结果（2026-04-15）

```
$ python3 verify_character_skills.py --novel-dir novels/射雕英雄传
✅ genghis-khan     ✅ guo-jing          ✅ hong-qigong
✅ huang-rong       ✅ huang-yaoshi      ✅ ke-zhene
✅ li-ping          ✅ ouyang-feng       ✅ wanyan-honglie
✅ yang-kang        ✅ yideng-dashi      ✅ zhou-botong
```

四项硬约束全部通过：
1. `parse_locators(SKILL.md)` == `count(key-dialogues.md sections)` == `build-meta.yaml.locator_count`（12/12）
2. 6 个必备章节（身份/核心欲望/性格真相/声音框架/边界/弧光）每个至少 1 条 locator（12/12）
3. 边界段每条 bullet 都有 locator（12/12）
4. character_map.json 含 `{display_name: role_slug}` 条目（12/12）
