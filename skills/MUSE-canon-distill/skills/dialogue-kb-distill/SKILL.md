---
name: dialogue-kb-distill
description: 将指定小说或戏剧的场景建成有来源的连续对白事件，更新该作品覆盖与检索索引。用于对白建库及作品分析后的对白蒸馏。
allowed-tools: Read Write Edit Bash Glob
---

# 对白知识蒸馏

命令中的 `${CLAUDE_PLUGIN_ROOT}` 以本技能所属包的实际安装根替换；Claude 插件可用宿主提供的该变量。其他宿主从当前技能位置定位包根。

一次处理明确指定的作品目录，位于本包 knowledge-base/novels 或 dramas。读取实际场景和当前场景索引；完整人物由 character-kb-distill 负责，本技能记录可观察互动与来源。缺场景/索引时报告缺口，保持 unresolved。

按[事件契约](references/dialogue-event-schema.md)写作品内 `dialogue/events/scene_{scene_id}.yaml`。保留足以解释回应的连续原文，单句金句不替代事件，转述作为 context。每个 turn 的说话者、接收者和前序回应引用可解析，原文能在 locator 窗口找到。独白、群体交锋与戏剧独语使用适用 event_type。

行动、合作姿态、关系和语言能力必须由当前原文支持；未获证实的心理解释不写为事实。长句、合作、自省或仪式性发言按实际功能标注。译文句法归当前 edition。低置信度事件保留 candidate；source_checked/reviewed 需要实际回查原文。

确无直接对白的场景在 coverage 标 no_dialogue，归属或解析未确定时保留 unresolved，范围外场景可 excluded 并说明原因。完成本作品标注后刷新该作品索引：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/dialogue_kb.py   --work-dir "实际作品目录" refresh --write
```

命令先核对该作品事件，再替换共享索引中的该作品条目，维护本作品 coverage 与登记信息；保留其他作品和人工版本/权利元数据，不隐式创建人物 profile。失败回对应事件修复。共享索引只反映实际已建部分；场景覆盖完整和事件内容正确分别判断。

完成时回报事件路径、覆盖状态和未解决的具体来源缺口。unresolved 不宣称完成；已有 verify 可单独用于复核，无需紧接成功 refresh 再运行一次。
