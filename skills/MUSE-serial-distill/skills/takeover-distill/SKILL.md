---
name: takeover-distill
description: 将用户在连作品的已发布文本提炼为可导入连载创作侧的续写基线：保留原文，回填既有事实、卷结构、台账和角色快照。用户要求接管连载、拆成续写基线时触发；只做手艺参考用 serial-analysis。也支持按指定改编范围提取无限流副本材料。
---

# 在连作品接管提炼

接管要让创作侧取得“已经发生什么、人物此刻是谁、哪些问题仍未定”。事实、解释和作者未来决定分别表达；事实连同生效时点、适用条件和完成状态一起提取。“约定核对”只确立约定，核对结果须有后续证据。产物是交换目录，由 MUSE-serial-writing 导入后成为工作区。

## 用途与输入

- **接管续写**：输入原文、实际卷序和截止章；执行下述接管链路。
- **手艺参考**：调用 serial-analysis，按用途生成范式或切片；不建立接管目录。
- **副本供材**：按 [副本材料格式](references/import-pack-format.md) 提取指定范围，不执行全书接管链路。

已有源作品、知识库、发布册和其他独立版本保持原状。生成到本次指定的交付目录；读取已有分析可以减少重复劳动，原文仍决定事实。字段接口见 [交换格式](references/exchange-format.md)。生成各项产物前按下文链接读取对应本包模板，已读且仍在上下文中的内容直接复用；需要完整字段解释时，在 MUSE-serial-writing 包中定位 `skills/serial-outline/references/workspace-schema.md` 的对应小节。

## 章节与分析

先查看输入目录文件顺序与章标题族。目录按文件名自然序读取；目录名不能表达实际卷序时，先在交付临时区按确认顺序拼接输入。默认识别第×章/回、Chapter、序章等标题，章内普通 Markdown 小标题不分章；作品另用标题形式时指定 `--pattern`。

输入已给出的卷界须转换为 `--volume-breaks`：填写各后续卷首章的 `chapter_id`。章 ID 尚未确定时，先取得切分映射再带卷界重切；工具未收到该参数时的默认卷号不代表原文卷序。此转换沿用下述切分命令与发布册。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/split_chapters.py \
  --input <原文文件或目录> --out <交付根> [--volume-breaks C####,C####]
```

输出 `published/*.md` 与 `published/manifest.yaml`。查看匹配到的章数和首尾标题是否对应实际原文，再据该发布册回填；成功退出只证明完成切分。原文标题号、chapter_id 和 manifest 位置可以不同，后续统一以实际 manifest 章锚关联。

按 serial-analysis 的 A 部分逐卷或章窗口分析，沿当前授权推进，不额外生成其人物参考包与手艺资产。接管仅需其分析结论时，可直接使用交付发布册作来源；可复用已存在的 pipeline/navigation/segments，不要求为交换目录复制整套知识库。未完结卷记录开放问题，未发生的终局保持未定。

**读取深度**：默认 fast，摘要用于定位，实际断章状态、活跃角色、仍有后果的关系和悬线回读原文。近期续写涉及某支线时扩大该范围；用户要求全量时 full 逐章扫描。覆盖由续写需求与持续后果决定，不按角色出场占卷数筛选。所用范围和未覆盖内容记入现有交付说明。

## 从分析回填续写基线

### 总纲与类型

生成前读取 [总纲模板](references/templates/story_bible.yaml) 与 [类型模板](references/templates/genre_profile.yaml)，按所需字段回填。

类型 profile 根据已读文本记录；无法确定的字段留待定，pacing_contract 等涉及未来运营方式的选择由作者决定。缺 profile 的旧包仍按消费侧通用缺省解释。

`story_bible.frozen` 写文本已确立的事实和作者明确冻结的创作决定，保留条件句的适用范围；“停运时启用备用方案”不能概括为已经停运。已出现最高层级只说明已知范围，自觉目标可以独立成立；未确定字段可为 null。

`intent.current_thrust` 承接作者已给定的续写方向，没有授权方向时留空。分析所得的方向候选、主控思想假设、未知天花板及会影响续写的缺口进入 `intent.open_questions`，标明待确认；问题应带相关章锚，说明已知什么、下一次决定缺什么。交付报告只作人类摘要；需要后续执行者使用的内容必须随 story_bible 一起进入导入目录。

### 世界与卷结构

生成世界册前读取 [世界册索引模板](references/templates/worldbook_index.yaml)，按 profile 选择已有 genre-pack 适用分册并读取对应模板。世界册硬约束记原文支持的规则、适用范围和章锚，氛围与质感归素材部分。模板问题帮助发现遗漏；原文没涉及的维度可以不启用，不为填表创造设定。已启用但未知的值写“原文未揭示”，必要未知同时进入 intent。原文矛盾并列来源，交由后续需要该事实时裁决。

回填前读取 [卷纲模板](references/templates/volume.yaml)。每卷实际章节、logline、opened/closed 与已发生转折按发布册登记，转折条目使用 `beat/value_shift/anchor`；实际章锚来自 manifest，`unresolved` 仅用于尚未定位的创作规划。已结束卷为 closed；当前未完结卷保留已发生部分，不补足预期高潮。人物变化可以是关系、处境或认识的变化，不必性格矫正；没有适用转折时 `tentpoles` 可为空。已发生的世界揭示入事实台账；没有原作者计划资料时 world_reveal_plan 留空，不按事后事实虚构计划。

### 台账与角色

按 [台账回填](references/ledger-backfill.md) 处理持续事实、未决线索、经历与关系；生成相应台账前读取 [悬线模板](references/templates/threads.yaml)、[世界事实模板](references/templates/world_facts.yaml) 或 [人物经历模板](references/templates/biography.yaml)。只把正文已建立的状态入账；未知代价照实写未知，计划、期待和猜测留在 intent 或卷设计的计划区。

涉及人物的事实，所有 `kind` 的 `entity` 都用角色目录的 `char_id`；关系对方及 `known_by[].char_id` 使用同一标识。地点、物件、组织等非人物实体用作品内稳定名字，并与后续章卡 `recap_inputs.locations/items` 对齐。显示名留在人物资料与叙述中。

调用本包 character-kb-distill 的 snapshot 分支，以发布册、目标角色、卷及截止章生成 persona 基线和快照。按时间前推，保留继承关系与条件；不把全书角色参考直接复制成每卷快照。

## 组装与交接

生成前读取 [连载状态模板](references/templates/series_state.yaml)：cursor.volume 指当前衔接卷，working_chapter 为 null，stage 为 breaking，buffer.drafted_unpublished 为空，active_session 为 null。接管后的第一动作沿现有开卷共创核对当前卷剩余方向或下一卷方向。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/export_gate.py --work-dir <交付根>
```

按错误修复对应接口；exit 0 表示本包交付检查通过，消费侧还会执行其导入检查。台账来源、人物解释与创作方向需要依据原文判断。不要修改原文迎合格式，也不要填造事实以清除缺项。

交付目录及简要说明：章/卷覆盖、主要台账与角色范围、fast/full、未解决问题及导出 WARN。提示使用 MUSE-serial-writing 的接管入口导入；其 pending 与作者共创权限继续生效。

已发布新章回流按 [增量回流](references/incremental-reingest.md) 执行。回流只更新获准的知识库分析资产，创作工作区的发布事务与事实台账仍由连载写作侧拥有。
