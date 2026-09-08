# 出口 B 交换格式契约

接管交付的产物形态与交付纪律。本包产出交换目录，由 muse-serial-writing 的接管导入命令校验迁移后落位为可写工作区。

## 交付目录形态（works/<slug>/ 全树同构）

```
<交付根>/
├── series/
│   ├── story_bible.yaml            # frozen 从文本可证事实归纳 + intent 留共创占位
│   ├── series_state.yaml           # cursor 指向续写点，stage: breaking
│   ├── genre_profile.yaml          # 类型档案：拆解前对原作跑类型判定的结果（substrate/engine/pacing/benchmark）
│   ├── worldbook/                  # 分域设定集：index.yaml + 一册一 .md（分册清单按 genre-pack 实例化）
│   ├── volumes/V0N.yaml            # 卷纲回填：tentpole 逆标，已完结卷 status: closed
│   ├── digests/                    # 逐卷 digest（有产出才交付，可空目录）
│   ├── decisions/                  # 空目录（共创决策由接管后产生）
│   └── ledgers/
│       ├── threads.yaml            # 伏笔台账按所选范围回填
│       ├── world_facts.yaml        # 世界事实台账按所选范围回填
│       └── characters/<char_id>/   # persona.md + snapshots/V##.yaml 序列 + biography.yaml
├── chapters/                       # 空目录（章 workspace 由接管后物化）
└── published/
    ├── V0NC####.md                 # 原文逐章入册
    └── manifest.yaml               # entries 按文本序 published_seq 登记
```

字段级契约的权威位于 MUSE-serial-writing 包内 `skills/serial-outline/references/workspace-schema.md`；通过当前宿主定位该包，再按产物名读取对应小节。本包模板遵循该接口，提供从已发布文本填写的字段形状。生成前读取对应模板：

| 产物 | 本包填写入口 | 直接用途 |
|---|---|---|
| 总纲、类型与世界册 | [story_bible](templates/story_bible.yaml)、[genre_profile](templates/genre_profile.yaml)、[worldbook_index](templates/worldbook_index.yaml) 及所选分册 | 续写约束、作者待决事项和按需世界设定 |
| 卷纲 | [volume](templates/volume.yaml) | 实际章序、卷转折及接管后的章上下文 |
| 悬线与世界事实 | [threads](templates/threads.yaml)、[world_facts](templates/world_facts.yaml) | 未决线索生命周期、按实体选入的持续状态 |
| 人物经历 | [biography](templates/biography.yaml) | 当前章之前已发生的经历变化 |
| 衔接状态 | [series_state](templates/series_state.yaml) | 导入后的卷游标与共创入口 |

`genre_profile.yaml` 与 `worldbook/` 为可选交付件：既有包缺此二者时消费方按通用缺省或无分域设定集解释；新接管按已读文本填写类型并建立适用分册。已经取得的模板内容直接复用。

人物实体采用角色目录 `char_id`，适用于世界事实的全部 `kind`，以及 `relation:<对方 char_id>`、`known_by[].char_id`。非人物实体采用作品内稳定名字，供章卡 `recap_inputs.locations/items` 原样选取；名称展示与身份连接分别承担职责。`biography.milestones` 和卷纲 `tentpoles` 可以是空列表，有实际条目时保留模板中的完整字段。

## 交付纪律

1. **交付树内全部 YAML 带 `schema_version: 1`**：本包 export gate 检查版本戳；消费方 import gate 对带版本戳的 YAML 校验支持窗口，窗口外明确拒收。
2. **`series_state.cursor` 指向续写点**：`volume` = 当前衔接卷、`working_chapter: null`、`stage: breaking`；接管后先沿现有共创核对当前卷剩余方向或下一卷方向。`buffer.drafted_unpublished` 空列表、`active_session: null`。
3. **交付前自验**：export gate 通过（exit 0）才交付；报缺项时补齐重跑，结构缺口先修正；语义未知可明确保留，勿填造事实。
4. **类型判定与设定集缺口显式化**：`genre_profile.yaml` 记录已读文本的类型判断，存疑字段列入交付报告；`worldbook/` 已启用分册中涉及续写的未知同步写入 `story_bible.intent.open_questions`。该区域随目录导入，旁置报告仅供用户阅读。
5. **派生视图不随交付**：`facts_current.yaml` 等派生视图由导入方从台账重建——本包不携带重建算法、交付树内不产该文件。

## 交付报告随附

交付根旁产一份交付报告（章数 / 卷数 / 台账条目数 / "待共创补全"清单 / fast 或 full 档）——接管方与用户对齐拆解质量的入口。
