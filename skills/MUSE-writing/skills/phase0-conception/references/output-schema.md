# Phase 0 输出

文件：`pipeline/phase0_conception.yaml`。示例说明字段形状；内容与篇幅目标按本次任务填写。

```yaml
premise: 能继续推演故事的具体情境、关系或问题
core_value:
  positive: 本作看重的状态
  negative: 与之构成张力的状态
  # spectrum 按需：positive / contrary / contradictory / negation_of_negation
controlling_idea:
  value: 价值判断
  cause: 原因或成立条件
  full_statement: 本作拟表达的认识
  type: ironic       # 按实际内容选 idealistic / pessimistic / ironic
genre:
  primary: 主导类型
  conventions:       # 只写实际采用的阅读期待
    setting: 背景惯例
    characters: 人物惯例
    events: 事件惯例
    values: 价值结果惯例
primary_drive: shift  # shift / reveal / observe / mix
target_length:
  words: 8000         # 示例；采用用户目标或本次估计
  range: 6000-10000   # 按需；保留用户约束强度
originality_statement:
  unique_angle: 具体切入点；mix 时说明组成与关系
  cliches_to_avoid: []
```

`premise/core_value/controlling_idea/genre/primary_drive/target_length` 提供基本构想。价值光谱与 `originality_statement` 按需填写；既有产物缺 `primary_drive` 时按 `shift` 兼容。局部模式描述各自职责，不由全局标签自动推出人物变化或场景结构。

## 有实际输入时追加

```yaml
requirements:
  - id: R1
    text: 用户明确要求及适用条件
    target_phase: 5
reference_materials:
  summary: 素材主题与来源
  key_details: []
  applicable_phases: [phase1, phase6]
style_directives: []
craft_targets:
  dominant_carriers: []
  omission_style: []
  scale_strategy: 效果与适用条件
  characterization_method: []
  narrator_position:
    primary: 叙述者位置的描述
    permission: 可知范围、叙述时点与评述权限
    examples_in_reference_work: []
canon_reference_profile:
  desired_domains: []
  avoid_domains: []
  user_reference_materials:
    - work: 用户指定作品
      stance: prefer       # prefer / avoid
      reason: 来源用途
      intended_domains: [world_rule]
      reuse_mode: maximize_apt_reuse  # maximize_apt_reuse / style_only
```

| 内容 | 下游实际用途 |
|---|---|
| 前提、价值与主控思想 | Phase 1–5 推演世界、人物与事件；校验具体设计是否保留作者意图 |
| `genre/target_length` | 各阶段分配结构与展开深度；明确字数硬要求还需按原义保留 |
| `requirements` | Phase 5 分配实际承接，Phase 6–7 执行与复核；只记录明确要求 |
| `reference_materials` | Phase 1 取背景、Phase 2 取人物经验、Phase 6 取适用素材；可保留原词、段落及定位 |
| `style_directives` | 全文表达要求，区别于人物声音 |
| `craft_targets` | 有手艺来源时供 Phase 5/6 选择表达；各子项可省略，不随背景素材强制生成 |
| `craft_targets.narrator_position` | Phase 5 视角编排、Phase 6 叙述权限；自由描述，已有标签可继续使用 |
| `canon_reference_profile` | 参考选择、排除与领域绑定；缺省合法，不要求因此启动深度研究 |

`intended_domains` 使用既有领域 `world_rule/reveal_structure/protagonist_archetype/scene_carrier/prose_style_imitation`。`prefer + maximize_apt_reuse` 在命中领域先沿用来源已成立的机制；`style_only` 限定表达参考。没有领域的既有条目作为选材偏好，不自动成为世界事实。
