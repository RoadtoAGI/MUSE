# 全库灵感聚类全量重建报告

- `annotated_by`: `gpt-5`
- 任务包：`full-rebuild.tasks.json`
- 任务包 SHA-256：`62804f8ccd1d9d8c72522fb863b860949d5cd5742245ae7a0bd63e4f333656a5`
- 输入：31 部作品，169 条合法提名
- 输出：132 张公共灵感卡，其中跨书佐证卡 25 张、单书孤证卡 107 张
- 写回：`cards=132 rejected=0 cross_book=25`

## 输入分布

`2666` 5；`I Am Legend` 5；`Macbeth` 6；`三体Ⅰ-地球往事` 5；`三体Ⅱ-黑暗森林` 5；`三体Ⅲ-死神永生` 6；`你好，旧时光` 5；`信（东野圭吾）` 5；`冰与火之歌Ⅰ-权力的游戏` 5；`冰与火之歌Ⅱ-列王的纷争` 5；`冰与火之歌Ⅲ-冰雨的风暴` 4；`冰与火之歌Ⅳ-群鸦的盛宴` 5；`冰与火之歌Ⅴ-魔龙的狂舞` 5；`哈姆雷特` 6；`大唐李白` 5；`射雕英雄传` 6；`指环王` 9；`挪威的森林` 5；`斯通纳` 4；`日耳曼涅槃` 6；`月亮与六便士` 5；`流浪地球` 5；`海的女儿` 5；`狂病-莫千回` 10；`现实一种` 5；`白鹿原` 5；`神雕侠侣` 6；`绍宋` 5；`长路` 5；`阿Q正传` 5；`雷雨` 6。

## 聚类统计

- 保留原公共卡 ID：126
- 新增卡：6
  - `battle-phase-breathing`
  - `capability-debut-delayed-validation`
  - `covert-cause-emotional-collateral`
  - `foreknowledge-through-bureaucracy`
  - `treasured-object-terminal-expenditure`
  - `trusted-symbol-hijack`
- 退役卡：2
  - `grassroots-regime-grounding`
  - `humiliation-site-recrowned`
  - 两者均已失去当前 nominations 佐证，`--replace` 后退出公共索引。
- 25 张卡合并了 62 条同质提名，减少 37 个重复范式。
- 三项新增提名并入既有同质机制：
  - `误读证据翻面战局` → `token-turned-evidence`
  - `魔法外化为后果` → `unshown-core-witness-mirror`
  - `战役海拔分层` → `ground-pov-warscape`
- 两处旧聚类过宽已拆开：
  - `先知入体制` 从 `righteous-cause-dirty-means` 分离为 `foreknowledge-through-bureaucracy`。
  - `珍物弧光·终局耗尽` 从 `short-lived-solution-chain` 分离为 `treasured-object-terminal-expenditure`。

## 验证

- 新鲜度：重跑 `cluster --prepare` 后任务包逐字节一致，SHA-256 相同。
- 官方 ingest：132 接受，0 拒收；全部 `source_scenes` 通过作品目录与 `scene_id` exact join。
- 语义覆盖：169/169 提名各归入一张卡；每条提名的 evidence、`reuse_candidates`、tags、`phase_affinity` 均被目标卡完整吸收。
- 公共写回等价：132/132 YAML 与 ingest 输入的规范化对象一致。
- 索引：132 行；`_backlinks.json` 340 个场景键、389 条卡片反链；从卡片重算后完全一致。
- 消费者 smoke：Phase 4 查询 `战斗编排/节奏/相位/喘息` 成功将新增 `battle-phase-breathing` 排为首位。
- 相关测试：`test_build_inspiration_cards.py`、`test_inspiration_query.py`、`test_kb_query_ref.py` 共 82 项全通过；coordinator 清理陈旧的固定卡数断言后，加入 reuse contract 文件共 89 项全通过。
- 静态检查：重建辅助脚本 `ruff check` 通过。

## 输出

- 公共卡：`MUSE-canon-distill/knowledge-base/inspiration/*.yaml`
- 人读索引：`MUSE-canon-distill/knowledge-base/inspiration/index.md`
- 机器反查：`MUSE-canon-distill/knowledge-base/inspiration/_backlinks.json`
- 聚类输出：`tmp/annotation-tasks/inspiration-cluster/full-rebuild.output.json`
- 逐提名归并审计：`tmp/annotation-tasks/inspiration-cluster/full-rebuild.semantic-audit.json`
- 消费者 smoke：`tmp/annotation-tasks/inspiration-cluster/query-smoke/inspiration/phase4_cards.md`

## Open

- 107 张单书卡的跨作品验证仍开放；每张 `applicability` 已显式写入「单书孤证，验证面窄」。
- 各作品 `_nominations/*.json` 未修改。
