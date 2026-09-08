# 设计校验报告

输出固定为 `<work_dir>/pipeline/review/design_validation.yaml`。系列/卷范围的 work_dir 是作品根，章范围是当前章工作区。报告保留本次明确范围内的确定不符与尚缺输入。

```yaml
review_findings:
  - dimension: temporal_math
    scene_id: null
    location: 'series/ledgers/characters/qing/persona.md: "2040 年，实际年龄 30 岁"'
    contradiction_pair: '同人物 biography.yaml milestones[0].after: "2015 年满 18 岁入职"'
    source: pipeline
    issue: "两项真实年龄不能共存；由前项推得 2015 年最多约 6 岁，来源无年龄变化机制。"
    suggestion: "交 serial-outline 路由人物资料负责人，核对原文中的年龄或入职时间；同步受影响经历及派生资料。"

summary:
  total_issues: 1
  by_dimension:
    temporal_math: 1
  input_gaps: []
```

| 字段 | 判据 |
|---|---|
| dimension | temporal_math：时间关系不能共存；world_rule_violation：违反适用的世界事实或作者设计约束；reference_integrity：明确引用不闭合或接口不符 |
| scene_id | 本章关联场景 ID；系列/卷或非单场问题填 null。跨章问题在 location 明确章路径 |
| location / contradiction_pair | 两端文件、字段或原文位置及关键措辞。接口错误的另一端可引对应 schema 约束；不伪造不存在的原文 |
| source | 固定为 pipeline，表示对设计输入进行校验；实际 series、published 或章路径写在 location 中 |
| issue | 哪些断言为何不能共存，保留精度、条件与必要推导；不填写审美优劣或通用写作建议 |
| suggestion | 负责修复的技能/来源、受影响字段与处理方向。无需预填具体剧情、替换正文或擅自改变作者决定 |
| summary.total_issues / by_dimension | 仅计 review_findings 中的确定不符，两处计数一致 |
| summary.input_gaps | 当前判断所缺的必要资料及其负责来源，字符串列表；无缺口填 []。疑点涉及的输入未齐时不能宣布该项通过 |

输入缺口示例：`"C0012/S02 需要林青在入场前得知密信内容；当前来源仅有寄出时间，交章内编排/人物派生者定位其实际获知渠道。"` 如果现有材料已经明确林青当时尚未收到、设计又要求她知道，则应写确定 finding，不能继续列作缺口。

无确定不符时写 `review_findings: []`、`total_issues: 0`、`by_dimension: {}`；input_gaps 仍按实际填写。读取缺此字段的既有报告时，结合其检查范围与完成回执判断，不把缺字段当成“输入已齐”。

写入后返回实际检查范围、所读来源与报告路径，注明是否仍有缺口。调用方据本次回执读取报告，恢复受影响设计后只复核相关矛盾和引用。
