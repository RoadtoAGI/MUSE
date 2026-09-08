---
name: character-persona
description: 按需构建或重建连载人物的兼容参考包。将指定时点的人物设计与合时账本编译为角色 SKILL、初始状态及 adapter，供明确需要该接口的消费者使用；本包逐章创作通过 role_view 取得人物上下文。
user-invocable: true
argument-hint: "build | rebuild <role-slug>"
allowed-tools: Read Write Edit Bash Glob
version: 1
---

# 人物参考包构建

本技能负责指定角色的参考包编译。人物设计、已发生经历和当前场景认知的职责见 [上下文协议](../serial-chapter-writing/references/context-contract.md)。构建包不触发扮演或新增创作阶段；包文件存在也不证明 actor 已读取。

## 明确构建范围和来源

调用方提供工作目录、本次角色集合、使用者及目标时点。`build` 生成尚缺的指定角色包；`rebuild <role-slug>` 更新一个既有包。沿用已有 `char_id`、显示名和 role_slug 映射；新角色由已确认人物记录建立映射，不靠显示名猜测既有目录。

- 新作入口：读取已确认的 `phase2_character.yaml` 和当前人物相关的世界、创作锚；只提取开场前已经成立的信息。
- 续作或接管：从人物 persona、截至目标时点的快照 extends 链、传记及必要正文取材。最新续写使用已确认的最新来源；历史时点不能读取后来的能力、关系或声音变化。没有 Phase 2 时直接使用这些来源。
- `rebuild` 保留现有 `state.md`。它可能有独立运行记忆或与包不同的时间范围，不能当成本场真值覆盖台账；发现冲突具体交回调用方。

仅在当前角色缺少所需事实或表达依据时补读。未来弧光终点、作者的不自觉欲望诊断、采收用途与他人秘密不进入角色自觉材料。原始设计继续在其权威来源保留。

## 产物与路径

以表中路径一次确定布局，后续读写与校验沿用同一根：

| 项目 | 系列工作区 | 已有单篇工作区 |
|---|---|---|
| 包根 `skills_home` | `series/character-skills/` | `pipeline/story-character-skills/` |
| 人物包 | `<skills_home>/.claude/skills/<role-slug>/` | 同左 |
| adapter | `<skills_home>/characters/<显示名>.md` | `pipeline/characters/<显示名>.md` |
| 设计（如有） | `<skills_home>/phase2_character.yaml` | `pipeline/phase2_character.yaml` |
| 构建清单 | `<skills_home>/build-report.md` | 同左 |

每个已建人物保留 `SKILL.md`、`state.md`、`build-meta.yaml` 和 adapter 四件。已有包不因本次未选中而删除、覆盖或重建。

1. 按 [skill-template](references/skill-template.md) 生成参考 SKILL。声音、经历、追求和判断方式保留源材料的条件与强度；字段不是新增禁令、心理或行为配额。按需使用 [编译指南](references/runtime-writing-guide.md)，理论转化见 [人物与声音依据](references/mckee-voice-principles.md)。
2. 新包初始化 `state.md`，只记录目标时点已经成立的情绪、认知、关系感知与经历。资料未给出时保持未知或为空；未来 `end_state` 不参与初始化。跨场自动更新不能由本构建器承诺。
3. adapter 从本次 SKILL 单向派生，保留有内容的同名章节与来源；它只提供同一人物材料的兼容入口。修订源 SKILL 后同步派生，不手改 adapter。`rebuild` 同步递增 SKILL 与元数据的 version。
4. 记录实际来源和明确映射。元数据示例中的路径替换为当前工作区相对路径：

```yaml
generated_by: character-persona
character_slug: li-an
character_display_name: 黎安
character_id: li-an
version: 1
through_chapter: null           # 新作开场；续作填实际来源截止章
input_sources:
  - series/ledgers/characters/li-an/persona.md
  - series/ledgers/characters/li-an/snapshots/V00.yaml
adapter_path: series/character-skills/characters/黎安.md
```

`through_chapter` 描述来源窗口，倒叙时仍按故事时间筛选；来源不能确定时不伪填截止章。旧包缺该字段时依据实际来源核对，不能推定其代表任何历史时点。`character_id` 供派生器将包映射回人物台账；旧包的 slug 与 char_id 不同且无明确映射时，由来源确认。保留既有元数据中的未知字段，新包不要求内容哈希。

较长的个人往事可放到 `references/backstory.md` 并从 SKILL 按需链接；仅放人物已知事件、信念及影响，作者的后续叙事用途留在设计源。

## 构建清单与校验

`build-report.md` 是包的构建清单，记录实际来源、目标时点、使用者及 name → slug 映射。已有记录按实际修改更新；本次未选中的已建包保留。模板只含消费者使用的列：

```markdown
# 角色包构建

来源与目标时点：{实际来源及截止范围}
使用者：{需要此兼容接口的调用方}

## 已构建

| name | slug |
|---|---|
| 黎安 | li-an |

## 未构建

| name | skip_reason |
|---|---|
| {本次考虑但无需构建的人物} | {实际原因} |
```

只记录实际作过的构建判断，不扫描全部配角来制造跳过清单。旧报告的其他列可以保留。构建完成后由调用方执行本包现有校验：

```bash
# 系列布局传包根；单篇布局传包含 pipeline/ 的工作目录
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_phase2_assets.py <skills_home-or-work_dir>
```

该校验检查清单映射、四件完整性、元数据和模板必要章节；有原型引用时检查来源闭合。非零返回时按具体错误修复受影响资产，不交付该次构建；它不要求全系列角色有包，也不为普通章写作建立额外 gate。

交付前直接判断：角色材料是否合时；经历、信念与事实是否保持区别；声音能否支持当前人物的回应判断；边界是否有来源与条件；是否夹带作者诊断、未来结果或通用表演命令。修改来源才重建受影响包，既有有效内容直接复用。

## 消费与交接

向调用方给出已建人物、包路径、来源范围和未解决缺口。派生器按明确路径只读取当前需要的部分，再产生该场 role_view；actor 与 writer 接收 role_view，不加载共享最新包或 state 覆盖切片。其他兼容消费者按其宿主的文件读取/挂载方式加载，并自行尊重包的来源时点。

章节模板中保留的兼容名称仅允许读取已有资料；新构建以当前模板表达。包结构通过不证明台词自然或人物成立，审美由作者裁决。
