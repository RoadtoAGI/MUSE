# 角色事实核对

当本次任务遇到具体来源冲突，或用户要求核对角色事实时，使用已有 claims.yaml 记录有关断言及处理结果。目标版本原文是小说事实的首要依据；人物自述、分析推断、历史现实和改编版本分别核对。canonical 标签不要求全角色抽表，也不以角色知名度决定证据标准。

## 范围与来源

只抽取当前需要核对、能具体判断的事实，一条 claim 对应一个判断。师承、血缘、身份、出处与死亡原因是常见对象，原有 type 值继续可用；它们不构成排他的白名单。声音概括、人格解释与叙事作用须以原文语境分析，网站多数不能证明这些解释。

回读 claim 的 source_locators，核对主体、对象、时间、因果与目标版本。已有原文足以解释时就地记录；确需确认版本或现实资料时再查外部可靠来源，保存实际摘录。来源互相转载或跨域并不增加独立依据，来源数和域名数不作通过门槛。

例如两件事先后发生不能证明师承；原文的传授过程或明确回忆才支持联系。原文支持某个冷门细节而网页找不到，不影响该版本事实；外部改编与原著不同时，记录版本差异，不能投票替换原文。

## 既有数据格式

```yaml
role_slug: role-slug
claims:
  - id: C001
    text: 当前需要核对的具体断言
    type: lineage
    source_locators: [full_text.md:L20-L22]
    confidence: high              # 可选分析估计，不决定核对结果
    verification_required: true   # 本次仍需处理的断言
    verification_status: verified
    verification_sources:
      - source_locator: full_text.md:L20-L22
        quote: 已回读且确实位于该窗口的原文
      # 外部来源沿用 {url: https://..., quote: 实际摘录}，说明版本和适用对象。
    resolution_note: 如何由来源支持该断言，或冲突发生在哪里
```

本地 source_locator 须列在本 claim 的 source_locators 内，路径相对作品目录。对当前角色包，作品目录默认为其 characters/ 的父目录；显式工具 `--source-root` 可覆盖定位根。保留来源中的必要上下文，不能只摘一个名字当作证明因果。

| 状态 | 含义与消费 |
|---|---|
| verified | 执行者已按目标版本核对，来源支持具体断言；只在该范围内使用 |
| disputed | 来源或解释存在分歧，记录实际来源和 resolution_note；使用者按当前问题阅读并决定 |
| unresolved | 尚缺必要来源或判断，保留缺口；不能以已核事实交付 |

`verification_required: false` 表示本次核对范围已撤销，说明原因；不把它用作规避真实冲突的出口。无法核实时保留 unresolved，不改 type 或删除有原文依据的参考来消除告警。原有 claims_exempt 字段可保留为历史说明，当前构建不要求新增豁免。

## 工具与反馈

已有脚本只做本地检查：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/verify_claims_factual.py \
  --role-dir ${NOVEL_DIR}/characters/{role-slug} --check
```

本地来源检查 locator 可解析、范围有效和 quote 确实在所指原文内；外部 URL 与摘录只检查其结构，实际网页与断言的关系由本次执行者核对。`--check` 对本次 required 且 unresolved 的断言返回未完成；可交付其余参考并报告缺口，不以该状态封锁整个角色包。

需整理尚未处理的 claims 时可用 `--emit-batch`，结果 pending_verification.json 为该次工具输出；不要求每次核对都先生成清单。`verify_character_skills.py --check-claims` 检查已有 claims 的同一契约，缺 claims 文件是合法的未启用状态，不运行全角色覆盖门槛。

来源引用存在与语义判断正确分别成立。消费方直接读取已有状态、来源与说明即可；本协议不新增状态分流产物或要求额外审核层。
