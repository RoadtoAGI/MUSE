---
name: serial-aigc-guard
description: 连载当前章稿的表达审查与修订调度。处理冗余、模板化和表达衔接，保护叙事可读性与人物声音，签发当前稿凭据；情节连续性和整体读者反馈由对应审阅负责。
---

# 连载章表达审查

改善当前章稿的阅读连续性、人物声音与表达效果，检查妨碍这些目标的冗余、模板化和叙述失真，把可定位的问题交给修订者。频数、词表与密度提供检索线索；是否需要改文由正文中的作用、人物条件与既定表达形式决定。合法短句、停顿、直接表达、文书体或有意重复可以保留。

## 取得当前稿

调用方提供系列根、章目录、chapter_id、本次范围及 `target_path`；未发布章缺省为 `draft.md`。沿系列既有的 reconcile、会话认领和 pending 规则取得写入资格；调用方已完成且仍有效时复用。无可用章稿时回交成稿环节。

会话 marker 由最外层入口拥有。嵌套调用使用外层传入的 session ID，不重新认领，也不在本技能返回时释放；独立调用自行认领时，在整个事务结束或保存 pending 离会后，由本次外层运行 `reconcile_series.py --work-dir <series_root> --release-session <session_id>`。同 ID 可复用，其他 ID 不得释放。

- 未发布章的当前正文为 `draft.md`。本技能及章级修订只操作它；场景级 distribution 已在装配前完成。不得再用旧 `pipeline/scenes/` 覆盖经过修订的章稿。
- 已发布章按 manifest 定位当前版，由调用方传已有工作副本或 scratch 的 `target_path`，沿现有 revision 通道修订；原 published 文件保持不变。涉及已发布事实、人物所知或事件结果的改变交 errata / 原设计负责人。
- 读取当前正文、相关作者要求及已有语义反馈；场景 lint 报告仅在仍对应当前文字时复用。人物或章末功能需要核实时，按[上下文协议](../serial-chapter-writing/references/context-contract.md)读取相关 scene card、serial_context 与合时 role_view，不通读全部设计。

## 判断与修订

1. 运行 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wholetext_gate.py --story <当前正文> --lang <auto|zh|en> --work-dir <章目录>`。脚本报告 `REVIEW` 表示有统计线索，`PASS` 表示未触发线索，exit 2 表示输入或运行错误；两种正常结果均不能替代本次正文判断。读取报告的 `observations` 与定位，取得本包 [prose-craft 的阅读连续性与修订判据](../prose-craft/SKILL.md#组织场景与段落)；其他症状按需加载对应判据。
2. 在现有审阅中结合上下文确认：问题片段重复了什么、遮蔽了什么，或与哪些人物/叙述条件冲突。只改确认的问题；角色对白中的有意重复、正常回指与具有声音或节奏作用的表达，不因命中模式而自动改写。已有审阅充分时复用结论。
3. 有问题时，通过宿主可用执行者加载本包 [aigc-wholetext-revision](../aigc-wholetext-revision/SKILL.md)，传相同 `target_path`、问题定位、受保护事实及必要人物依据。先完成一次修订，再按原阅读顺序对照修前后受影响段落及前后依赖，确认原问题改善、指称与解释顺序顺畅、事实和声音保留；不并发修改同一正文或其不同来源副本。
4. 修改后必要时重算受影响的统计，检查新线索的实际语境。只有原问题仍存在或产生具体新问题才继续修订。无法在授权内解决时报告冲突及责任方；不靠反复降频或替换近义句追求清零。一次调用最多自动修订两轮；到限仍有明确问题，交回调用方说明原因与所需决策。

跨章开场、收尾或句式相似需要证据时，沿 manifest 读取相关已发布原文的必要窗口。recap 用于理解事件连续性，不能证明原文句式和词语频数；不固定扫描前 k 章。

## 改文后复检

已有凭据后章稿发生改动，按 `verify_only` 复检：有可靠改动范围时读改动处及前后依赖；没有时读当前全文。需要修订即返回上面的修订动作。事实、知情或章末承诺发生变化时，回交相应连续性审阅并更新受影响摘要。

## 完成与凭据

完成条件是已确认的表达问题得到处理，改动后的承接、指称、解释顺序与声音经正文对照仍成立；剩余审美取舍按作者裁决处理。尚有阻断问题时不签凭据。未发布章沿既有 [workspace-schema](../serial-outline/references/workspace-schema.md) 写 `pipeline/aigc_clearance.yaml`：chapter_id、当前 draft_sha256、verdict、mode、cleared_at；保留合理表达或未决审美选择时可用 `pass_with_notes` 说明。

```bash
python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <章目录>/draft.md
```

凭据绑定当前 `draft.md`；改文后重签。`publish_chapter.py` 核验存在凭据的章号、放行值与正文绑定；缺凭据沿其既有兼容策略告警。发布仍由已获授权的发布环节执行。已发布修订候选的审查结论交 revision 通道，不把旧 draft 的凭据当成候选通过的依据。
