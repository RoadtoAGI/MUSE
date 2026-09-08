# 出口 A：连载范式卡 schema

五类范式卡从被拆解作品中抽取**连载手艺机制**，落 `knowledge-base/novels/<slug>/serial-paradigms/`，供连载创作侧开卷 breaking 时检索参照。其他作品参考抽取机制与适用条件；同作前文允许延续已发生事实与名称，并遵守截止点。范式描述不自动成为创作配额。

## 1. volume-structure.yaml —— 卷结构样本

```yaml
schema_version: 1
source_scope: "本卡实际覆盖的原文章范围及截止点"
volumes:
  - volume: 1                       # 被拆解作品的卷序
    span_chapters: [C0001, C0042]   # 卷界（裸章号）
    three_act:                      # 卷内三幕分析适用时的落点；不适用可省略
      setup_until: C0009
      midpoint: C0021
      climax_at: C0040
    tentpoles:                      # 逆标：本卷实际发生的转折
      - at: C0021
        beat: <一句转折描述>
        value_shift: <价值方向变化>
    open_ended: false               # 未完结卷 true
```

## 2. hook-samples.yaml —— 章末钩子采样

按已有类型（悬念 / 反转 / 情绪炸弹 / 信息投放）标注适用条目；没有钩子时记 null，复合或不同机制保留说明。采样条目保留原文定位、解释机制所需的片段与适用条件：

```yaml
schema_version: 1
source_scope: "本卡实际覆盖的原文章范围及截止点"
hook_sequence:                      # 逐章 hook 类型序列（同型连击/强弱交替的分析原料）
  - {at: C0016, hook_type: 信息投放}
  - {at: C0017, hook_type: 悬念}
samples:
  - hook_type: 悬念
    at: C0017
    quote: <支持机制解释的章末原文片段>
    mechanism: <为什么钩得住——信息缺口设在哪、指向哪个未答问题>
```

`hook_sequence` 覆盖分析批次内全部章（类型标注即可，不引原句）；`samples` 只采代表性条目。

## 3. power-system-evolution.yaml —— 力量体系演化时间线

extends delta 卡时间线：每次体系揭示/升级一张卡，`extends` 上一张、只记增量——使用时按 extends 读取已允许范围内的前序卡，单读末卡不等于体系全貌：

```yaml
schema_version: 1
source_scope: "本卡实际覆盖的原文章范围及截止点"
cards:
  - card_id: PS-01
    at: C0003                       # 首次揭示章
    extends: null
    delta: <本次揭示的层级/规则增量>
    limitation: <该层级的代价/边界（原文可证）>
  - card_id: PS-02
    at: C0045
    extends: PS-01
    delta: <新增层级或规则细化>
    limitation: <同上>
```

## 4. pacing-profile.yaml —— 节奏形态

描述原作实际节奏；按研究问题选择有关观察，不要求填满所有统计维度：

```yaml
schema_version: 1
source_scope: "本卡实际覆盖的原文章范围及截止点"
profile:
  unit_shape: <单元（按原作实际边界）内事件与信息怎样组织，一段描述>
  mainline_drip: <主线信息在支线单元里的滴灌方式，一段描述>
  breath_pattern: <实际强弱分布与重复（大战后如何回气），一段描述>
  payoff_spacing: <爽点间隔曲线——相邻兑现点的章距形态与随卷变化趋势，一段描述（可附代表性章锚序列）>
  thread_economy: <未决问题怎样被推进、并存或回收；需要比较距离时附实际章锚>
```

## 5. benchmark-coords.yaml —— 类型坐标（对标反查数据源）

写作侧 S1 类型判定"像 X 那样"按本卡反查坐标预填；值域与 genre-profile 同（genre-packs 词表）：

```yaml
schema_version: 1
source_scope: "本卡实际覆盖的原文章范围及截止点"
coords:
  substrate: <history | xianxia | infinite | generic>
  engine: {primary: <爽点引擎>, secondary: <或 null>}
  mainline_type: <事业线 | 关系线 | 双线>
  pacing_contract: <免费快节奏 | 付费标准 | 慢热精品>
  evidence: <判定依据一段——开篇形态/更新节奏/兑现密度的原文观察>
```

## 场景切片（与范式卡并行产出）

场景切片沿 scene_index 同构落本包 `knowledge-base/novels/<slug>/`（`scenes/*.md` + `scene_index.json`），由**本包** serial-scene-reference 检索——无跨包数据流。切片的 source_chapters 与 published_seq 生成方式见入口“原文切片与章序”；跨章片段取覆盖末章。尚无 manifest 的分析不伪造发布序。

## 提取纪律

- 卡类按原作机制与参考用途选择，无力量演化时不生成对应卡；每项判断锚回原文章号，未知不补造。
- 引用范围以解释机制为准，必要上下文通过来源章锚可达；单句不足时保留连续反应。
- 未完结卷的卡照常产出并标 `open_ended: true`；不为"等结局"推迟出口 A 交付。
