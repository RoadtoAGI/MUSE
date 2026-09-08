# 读者观察格式

```yaml
input_path: chapters/V01/C0002/draft.md
reading_context: 本章与实际前章 recap.summary；未读取未来计划。
reader_findings:
  - location: 中段：“她把钥匙递回桌上。”
    feeling: 我无法确定她把钥匙还给了谁。
    expectation: 想知道这次交接由谁接收。
    absence: 这一段出现两位可能接收的人，后文仍未明确对象。
```

`reader_findings` 无问题时为空。每条保留 location / feeling / expectation / absence；location 给当前精确引文及足够上下文。feeling 为本次阅读观察，expectation 为其依据，absence 描述文本实际缺口或不相容的信息；重复、过密等问题也说明其实际表现，不编造缺失。

input_path 和 reading_context 标明受审范围。调用方将本次选中报告和待处置范围交修订者，不能凭相同文件名认定旧报告适用。修订者会回当前文本核实引用与问题，主观观察不自动构成删改授权。
