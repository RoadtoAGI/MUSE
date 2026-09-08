# 补丁可追溯协议

修订者只在当前正文的明确片段内施工。单句用 `anchor_quote`；rewrite_span 用完整 `old_span` 和 `anchor_quote_start/end`。锚点非空、精确匹配；重复文本须用有效 `location.line_range` 区分，不能靠最先匹配猜位置。

`check-reviser-patch` 在受支持宿主的 reviser 派发前调用现有 schema 与 traceability 脚本。文件加载宿主未执行该 hook 时，调用方显式运行同一校验，不重复新增检查。失败先回补丁生产者补正；正文不按无法定位的指令修改。

C 报告明确记录的 `user_accepted_as_known_issue`、`next_round_only` 或 `escalation_decision.user_accepted_findings` 保护相应 finding，不进入本次补丁。裸 `status=persists` 只表示尚未解决，不代表作者接受。

校验权威为本包 `verify_patch_directive_traceability.py` 和 `verify_rewrite_patch_schema.py`；脚本只能证明格式、定位及显式保护关系，问题是否成立仍需 scene-review 判断。输入/工具错误由调用方写既有 ESCALATED，恢复后重新派发。
