---
name: serial-analysis
description: 前推拆解在连或未完结小说截至指定进度的文本，产出结构分析、连载范式与按需场景/人物参考。用户要求连载分析、网文拆解或连载手艺入库时触发；完整接管交付由 takeover-distill 调用本技能的分析部分。一般读后感和已完结作品的结局回溯分析不适用。
---

# 连载文本前推分析

从已发生的事件解释人物选择、结构关系与表达作用，供本作续写或其他作品的手艺参考。麦基将结构解释为事件的选择与安排；分析既记录发生了什么，也说明这种安排如何影响读者。作者没有明示的意图写成分析判断。

## 用途、范围与交付

先确认作品来源、允许分析的截止章与本次用途。原文是事实依据；已有分析和摘要供导航，冲突时回到对应原文。未完结卷标 `open_ended: true`，未发生的高潮不补造；有依据的方向假设标为 provisional，接管时由 takeover-distill 放入可共创区域。

| 部分 | 直接消费者 | 产物与条件 |
|---|---|---|
| A：结构分析 | 接管归纳、场景检索、开卷参考 | `pipeline/phase0–5_*.yaml`；按用途提取 `serial-paradigms/` 与 `scenes/scene_index` |
| B：人物参考 | 角色研究与创作参考 | `characters/<role-slug>/` 参考包；只在本次授权包含人物蒸馏时构建 |
| C：手艺标注 | 手艺参考与相应检索 | `craft_notes/` 与条件 sidecar；按当前任务授权执行 |

A 的系统人物图不等于 B 的参考包；接管角色快照由 takeover-distill 调 character-kb-distill 的 snapshot 分支，不额外生成全部参考包。各部分用已有磁盘产物续接，不依赖前一会话记忆。已获整项任务授权时按依赖推进；仅在来源冲突、任务范围或作者方向需要裁决时提问，不逐 Phase 重复确认。

## A：按证据形成分析

### 阅读范围

先看章节标题与篇幅，选择能保留上下文的读取窗口。能单次容纳则通读允许范围；长篇按卷或章窗口分批，进入长篇路径时读取 [导航与定向阅读](references/long-novel-analysis-path.md)。`navigation.md` 与 `segments/` 记录实际读到的章序、主要事件、角色与未决线索，窗口大小随篇幅调整。摘要不能证明“未出现某事实”，也不能代替关键断言的原文。

### 分析与关系

读取 [分析框架](references/analysis-schema.md)，按已有文本提取 Phase 0–5。世界、人物和结构相互制约，已有证据可交叉修订；文件顺序不规定必须重读全部原文。每份 YAML 带 `analysis_meta` 的来源与截止范围，保存到作品目录 `pipeline/`。

- Phase 0/1：归纳已呈现的前提、价值问题与世界约束；未知上限、未来主控思想与类型猜测保持未定。
- Phase 2：系统 YAML 记录角色功能、对比与关系；个体声音、心理、经历可留在已有 `characters/<角色名>.md`，也可直接从原文供下游提取，不要求中间画像。
- Phase 3/4：已形成的 Arc 按重大变化和因果联系归纳；未收束部分记录当前开放问题。序列可以递进、并行、回旋或暂缓，说明实际作用，不把相邻章节一律连成因果。
- Phase 5：选取能说明结构、人物或表达机制的场景。保留情境、冲突、信息变化与叙事作用；场景数量取决于用途与差异，不按字数凑配额。

结构与节拍进一步分析时按需读取 [节拍分析](references/beat-analysis.md)。范式卡格式见 [连载范式](references/paradigm-cards.md)，只生成本作存在且下游需要的卡类；非升级题材可以没有力量演化卡。

### 原文切片与章序

授权包含场景入库或下游确需切片时，按 Phase 5 定位裁剪，保留原文；仅做结构分析时可以不切。片段缺上下文时扩大所选范围，勿在片段中改写原文。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_scene.py \
  --source <作品原文绝对路径> --batch <切片范围JSON> \
  --output-dir <作品目录>/scenes
```

范围 JSON 每条为 `{"scene_id":"S01","start":60,"end":85,"chapter":"第1章"}`。也支持 `--scene-id / --start / --end / --chapter` 单场模式。脚本检查行号后裁剪；失败时核对定位，不截短到文件尾并当作成功。

在作品根 `scene_index.json` 写条目列表：

```json
{
  "scene_id": "S01", "novel": "作品名", "author": "作者名",
  "genre": "题材", "lang": "zh", "tags": ["标签"],
  "characters": ["角色"], "conflict_type": "personal", "pov": "角色",
  "word_count": 800, "source_chapter": "第1章",
  "source_chapters": ["C0002"], "published_seq": 2,
  "file": "scenes/scene_S01.md", "description": "场景及其作用",
  "has_craft_notes": false
}
```

章锚三者分工：`source_chapter` 是原文标题；`source_chapters` 是实际 manifest entries 中所有覆盖章的 ID；`published_seq` 取所有覆盖章的 `manifest.entries[].published_seq` 最大值。序章也有发布序，切片编号和标题里的数字不能代替发布序。跨章切片全部内容到末章才可见。接管时使用交付根 `published/manifest.yaml`；回流时使用创作工作区对应 manifest。仅做参考分析、尚无发布册时，可保留原章标题而省略后两项；这种条目可供独立研究，不进入按发布序过滤的创作输入。不要为普通分析另造发布工作区。

## B：按角色需要构建参考

从 `cast_overview` 与关系网列候选，兼容旧顶层 protagonist / antagonist(s) / supporting_cast。复合对抗力量中只提取实际人物，组织或时代压力不当作一个角色。角色有用性来自其选择、关系、表达或叙事作用，不取决于是否已有 unconscious、voice_traits 或 character_arc 字段。

使用 `scene_index`、导航和已有画像定位原文。形成可靠身份与有用特征后，调用本包 `character-kb-distill build --novel-dir <本作KB绝对路径> --role <中文名>`，同次调用传入实际允许章节与截止点；该入口按来源目录委派参考构建。需要跨章节补证时直接定位 `full_text.md`，无需先造场景或个人档案。没有场景索引时用原文标题导航。

长篇角色聚焦的读取策略见 [角色定向阅读](references/long-novel-distill-path.md)。读取中发现新证据改变已构建结论时 rebuild；未改变时沿用。缺少声音或转变可以仍有可用参考，证据确实不足的候选在现有 `characters/build-report.md` 说明原因。以实际包及来源核对完成情况，不要求批次状态行或重复检查子技能内部格式。

## C：手艺与条件标注

节拍级标注按 [手艺笔记模板](references/craft-notes-template.md) 写 `craft_notes/scene_<id>_beats.md`，更新对应索引的 `has_craft_notes`。分析要解释原文机制与适用条件，引用片段帮助辨别作用，不要求后来的作品复刻动作或句法。

需三层标注且装有 MUSE-canon-distill 时，通过宿主支持的机制选择 **canon 包 kb-annotator**。派发作品名、annotated_by、入口与档位；其自有工具决定标注契约。本包同名 agent 只做兼容交接。目标包没有本作品或能力不可达时报告缺口，继续已具备条件的拆解；不自动复制语料。其标注块由 canon 生态检索消费，本包结构化检索不假定已消费这些块。

## 完成与反馈

按本次用途交付已有产物及覆盖范围。关键判断应可定位回源文，未发生事件保持未定，参考与接管事实分开使用。出现归纳失真时回到对应原文与分析；切片行号错误修定位，人物包错误由构建入口修，接管接口问题交 takeover-distill。结构通过和字段齐全不能判断原文解释是否成立。
