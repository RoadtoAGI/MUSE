# 副本供材格式

为当前副本设计提取原作材料，保存到 `knowledge-base/novels/<slug>/import-packs/<pack-slug>/`。本次已选定的使用范围决定材料，不做全书接管，也不调用 import_series。

## world-card.yaml

```yaml
schema_version: 1
source_work: <作品名与版本>
source_scope: <实际提取的章范围及截止点>
fidelity: strict_canon
entry_point: <原作时间线位置与本作角色进入方式>
exit_condition: null                # 由本作设计确定，原作提取不伪造
mainline_quota: null                # 本作设计需要时填写
```

fidelity 表达作者已选定的改写范围：

| 取值 | 保留范围 |
|---|---|
| strict_canon | 保留原作事件线，新增行动须与已发生事件相容 |
| canon_flex | 保留约定的主线骨架，允许约定范围内的支线变化 |
| premise_only | 保留前提及约定设定，事件线可重新展开 |
| setting_skin | 使用约定世界素材，剧情另作设计 |
| host_shell | 只使用约定身份或外壳，世界规则按本作设计 |

这些值不自动开启机器检查器。具体保留对象写在卡片和既有卷向中；不得仅凭档名推定用户允许改变哪些事实。旧材料出现连字符拼写可按同义规范化；AU、landmark-replay、quarry 等旧标签没有一一对应关系，按已记录的具体授权范围解释，缺少时交共创确认。

## 按实际用途取材料

| 文件 | 何时需要 | 信息 |
|---|---|---|
| plot-nodes.yaml | 保留事件线或需要评估偏离后果 | 原作节点 at/event；可改变范围与改变后果属于本作设计，分开注明 |
| world-rules.yaml | 使用原作世界规则 | rule/source_anchor/scope/status；未知保持待查 |
| power-anchors.yaml | 两套力量体系确需换算 | 原作实体、已知能力、证据；换算是本作选择，原作证据不能替它授权 |
| characters.yaml | 使用原作人物 | 身份、立场、关系与来源时点；有对白证据才附 voice_line，人物未终结不补写命运 |
| opportunities.yaml | 使用原作机缘或资源 | 位置与时间窗口、原作归属、已知代价 |
| divergence-log.yaml | 本作已经产生偏离 | at/diverged_from/divergence/ripple；由创作侧追加，不在提取时填造偏离 |

生成的 YAML 带 schema_version，列表允许为空或文件按用途省略。strict_canon / canon_flex 需要确认所保留的事件节点；无法确定时指出来源缺口，不能用空表宣称已锁定原作事件线。

## 消费与回流

连载卷设计读取 world-card 及适用材料，将实际生效约束与原作定位写入已有 worldbook 副本册。原文事实、分析推断与本作设计决定分别标明。生成或审阅相关剧情时核对这些已采用约束；材料齐全和 YAML 合法不证明改写范围已获授权。

副本偏离由创作侧按既有发布与台账流程记录。需要回流知识库时处理新发布材料，不在本包另行更新创作侧事实台账。
