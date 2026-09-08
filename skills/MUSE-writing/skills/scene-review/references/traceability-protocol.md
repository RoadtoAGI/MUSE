# 修订定位与接受范围

单句 patch 使用精确 anchor_quote；rewrite_span 使用 old_span 及 anchor_quote_start/end。原文须存在于当前正文并能唯一定位；重复文本用 location.line_range 消歧，首尾锚须与 old_span 边界相合。定位能力决定锚长，不设字符配额。

verify_patch_directive_traceability.py 在 reviser 派发前检查当前原文、范围与已接受项；verify_rewrite_patch_schema.py 检查 rewrite 字段。缺锚、原文已失效、范围矛盾或重复仍无法消歧时，由生产者补正再派发。

issue_id / issue 不引用 C 组显式 user_accepted_as_known_issue、next_round_only 或 escalation_decision.user_accepted_findings 中的条目。裸 status=persists 仍可代表当前待修问题，不因此排除。

校验失败由主控停止本次施工，按原 input_gate 报错。scene-reviewer 负责可追溯指令，主控负责 hook 与恢复，不新增评审步骤。
