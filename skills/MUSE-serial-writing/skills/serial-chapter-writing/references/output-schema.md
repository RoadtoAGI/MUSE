# Phase 6 输出 Schema

## 正文文件

每个场景写入独立的 markdown 文件：`pipeline/scenes/scene_{id}.md`

场景文件是纯正文（含对白），不含执行字段或元数据。装配前它们是当前正文；章稿经防治或读者反馈修订后，以本次接受的 `draft.md` 为准，不能再由旧场景覆盖。

## 索引文件

交付物文件：`pipeline/phase6_development.yaml`

```yaml
total_word_count: 8500
scenes:
  - scene_id: S01
    file_path: pipeline/scenes/scene_S01.md
    approximate_words: 850
    summary: ""           # 兼容字段，已有有效内容可保留
```

由 `generate_phase6_index.py` 按当前 phase5 呈现顺序生成；尚未写出的场景仍在索引中，字数暂为 0。旧 `summary`、`beats`、`value_change` 等内容兼容保留，不要求 writer 为索引补写另一份叙事分析。

## 字段说明

| 字段 | 必需 | 下游使用 |
|------|------|---------|
| `scenes[].file_path` | 是 | assemble_story 与审阅完整性检查定位同一场景正文 |
| `scenes[].scene_id` | 是 | 关联 phase5 的完整有序场景集合 |
| `scenes[].approximate_words` | 生成值 | 当前正文规模；旧 word_count 存在时同步更新，不阻断 |
| `total_word_count` | 是 | 报告字段（用户感知全文规模），不与 `target_length` 做硬比较；**不触发 second writer pass** |

## 文件分工规则

- 场景顺序取 phase5；phase6 是可重建的路径索引，不成为另一份设计权威。
- 索引不保存完整正文，也不证明语义审阅完成。章级修订、装配和恢复沿主入口的当前稿约定执行。
