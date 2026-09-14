---
name: aigc-wholetext-revision
description: 连载当前章稿的表达修订。由 serial-aigc-guard 交付已确认问题，修改 draft 或指定的发布修订候选，保留人物声音、事实和章末作用。
---

# 章稿表达修订

读取 dispatch 的 `target_path`；未发布章缺省为章目录 `draft.md`，已发布修订须由调用方指定已有工作副本或 scratch。同时取得已确认问题、位置和受保护条件；`pipeline/review/wholetext_gate.yaml` 的统计线索帮助定位，需要结合正文判断，不能只按数值施工。问题依据不足时先明确实际作用，无法成立的修改要求回交调用方。

按需读取相关 scene card、serial_context 与本场 role_view 的 character_basis/known_now，取得人物声音、事实和章末承诺。遵循[上下文协议](../serial-chapter-writing/references/context-contract.md)，通过宿主可用的技能调用或文件读取取得本包 prose-craft 的相关判据；必要依据缺失交原供给环节。

修订范围随实际问题决定：局部重复可以删并，跨段叙述形态需要重组信息关系。保留事实、人物动机、知识、因果、关系变化和章末功能；可以改变句段组织与措辞。新的同义套式若继续承担原来的无效解释，原问题仍在；有叙述作用的新表达可以使用，不能仅因属于另一统计 family 而禁用。

只就地修改本次指定正文，不反向重写场景源文件，不重新装配覆盖章稿。已发布原件保持不变；发布修订只写明确候选路径。事实与设计变更回相应负责人。

修改后检查受影响段落及其衔接，保持人物声音和已接受的内容保护。写 `pipeline/revision_summary.md`：顶部 `status: complete | partial | failed`，简要对应本次问题记录改动、保留理由或未完成原因；该摘要描述本次修订，不复用旧反馈作为新指令。回复：

```text
done wholetext revision for {chapter_id}; status={complete|partial|failed} ({n} issues)
```

调用方根据当前正文判定完成；统计尚有命中并不要求重试。尚有明确问题、输入冲突或需要作者选择时，具体交接。
