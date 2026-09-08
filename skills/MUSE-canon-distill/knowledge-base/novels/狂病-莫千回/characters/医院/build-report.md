# 《医院》篇 单篇人物蒸馏 build-report

> 篇 = 医院 / scene 前缀 PREFIX = YY / 模式 = reference（参考包）
> 本轮为【收尾模式】：补建 4 个空目录角色；3 个既存包未改动。

## 本轮蒸馏（新建 4 个）

| slug | display_name | desc（人设类型原型标签） | has_canon_ending | verify exit 0 |
|------|------|------|:---:|:---:|
| zhao-shixuan | 赵士轩 | 丧亲创伤的机场幸存者·末日见证口述者（赵士轩·狂病-莫千回·医院） | true | ✅ |
| zhang-hua | 张华 | 反智抬杠的内讧催化剂·末日里的人形挑衅源（张华·狂病-莫千回·医院） | true | ✅ |
| sun-duizhang | 孙队长 | 舍身殿后的军人·感染后回来索债的悲剧闭环（孙队长·狂病-莫千回·医院） | true | ✅ |
| wang-xingzi | 王幸子 | 并肩等死的女医生·末日里的照护者与洞察者（王幸子·狂病-莫千回·医院） | true | ✅ |

locator_count（去重后，= verify 通过值）：zhao-shixuan=10 / zhang-hua=11 / sun-duizhang=6 / wang-xingzi=6。

### has_canon_ending 判定（均已回 scene 原文核对）

- **zhao-shixuan**：S10 被二楼铁门夹断手臂（L5）+ 被感染者撕脸虐杀致死（L13），不可逆物理死亡 → true。内在弧光在 S09 倒戈定罪已收束，死亡属被动遭遇的剧情终局，隔离到 canon-ending.md。
- **zhang-hua**：S10 抢枪打空仅剩三发子弹后被孙队长扯下下巴、咬舌惨死（L21-L23），不可逆物理死亡 → true。黑色幽默式终局（遗言仍在抱怨子弹数），隔离到 canon-ending.md。
- **sun-duizhang**：感染前舍身把感染者顶回二楼（S03），感染后破门屠杀、最终被石浩洋汽油焚烧致死（S10:L41），感染异化 + 物理死亡双重不可逆终局 → true。弧光仅描感染前内在转变，感染后状态隔离到 canon-ending.md。
- **wang-xingzi**：【医院单篇人物，非跨篇】。任务要求重点核对其"留在医院等死"是否构成不可逆终局——回原文核对结论：S08:L53"像盲女一样，已经累了"是**内在弧光终点**（放下求生意愿），本身不是物理终局；其不可逆物理终局是 S10 被铁门撞飞昏迷（L7）后被"我"用近 2000 毫克吗啡安乐死（L27-L29，石浩洋查看摇头确认死亡 L43）。死亡发生在昏迷无法自主状态、由"我"代为执行 → has_canon_ending: true，物理死亡隔离到 canon-ending.md，"等死"的内在选择留在弧光本体。

## 既存包（本轮未动，一并列入；3 个）

| slug | display_name | has_canon_ending | verify exit 0（本轮复核） | 备注 |
|------|------|:---:|:---:|------|
| liu-yisheng | 刘医生「我」 | true | ✅ | 第一人称不可靠医生 POV，自感染收笔，本轮未动 |
| cai-dama | 蔡大妈 | true | ✅ | 好心办坏事的多嘴泄密者，本轮未动 |
| shi-haoyang | 石浩洋 | false | ✅ | **已含 identity_link: wu-xiansheng**（同一虚构人物：石浩洋＝吴先生＝伪装"罗允"者）。本包作为【医院篇特化原型】保留——供二创单独取用医院"诈死导演型·游戏导演"facet，与跨篇主包 wu-xiansheng 构成 two-package + identity_link 关系（同 李鸾/陶亦仁 模式）。下游取跨篇全人格用 wu-xiansheng，只要医院篇"诈死布局"切面用本包。**本轮未动。** |

## per-part map 状态

`character_map.json` build 前 3 条（刘医生/石浩洋/蔡大妈）→ build 后 7 条（追加 赵士轩/张华/孙队长/王幸子）。
读-改-写【追加】方式，build 前后各 cat 确认旧条目仍在、未被覆盖。未传 --novel-dir（避免写根级跨篇 map）。

```
{
  "刘医生": "liu-yisheng",
  "石浩洋": "shi-haoyang",
  "蔡大妈": "cai-dama",
  "赵士轩": "zhao-shixuan",
  "张华": "zhang-hua",
  "孙队长": "sun-duizhang",
  "王幸子": "wang-xingzi"
}
```

## 跳过的角色（_candidates.md 标"可做但非必需 / 不蒸馏" 且本轮范围外）

本轮收尾模式只补建指定的 4 个空目录角色，下列在 _candidates.md 中的其余角色不在本轮 build 范围（无空目录、未指派 slug），按候选池建议处置：

- **侯楚霖**（厨师/投毒感染受害者）：_candidates.md 标"不蒸馏（信息不足，主要承担投毒连锁的功能性受害者 + 痛觉缺失 lore 载体）"。无原型独立价值，跳过。
- **盲女**（无名全盲女性）：_candidates.md 标"可做但需先跨篇核对身份"（与《燃烧》盲女疑似不同人 / 同源母题）。属跨篇仲裁项，本轮收尾范围外，不在医院篇单独建。
- **李教授**（从未出场，仅经"我"转述）：_candidates.md 标"不蒸馏（从未实际出场，是 lore 载体而非可扮演角色）"。跳过；"北方高原研究所"作为世界观钩点已在 phase3/phase0 登记。
- **吴志强**（机场退伍保安）：_candidates.md 标"本轮只识别、不分配 slug"，与跨篇 wu-xiansheng（吴**先生**）名字相近但应为不同角色，留待 coordinator 仲裁是否新建 wu-zhiqiang。本轮收尾范围外。

## 跨篇人物（绝不重建，仅本篇 sighting）

罗允 luo-yun / 林东青 lin-dongqing / 陈雨琪 chen-yuqi / 陆小虎 lu-xiaohu —— 本篇有戏但归跨篇统一蒸馏，本目录不建。

## 遗留问题

- **石浩洋 reconciliation**（open_questions #1）：石浩洋＝吴先生 是否同一人/化名/同型不同人，跨篇保留 wu-xiansheng / shi-haoyang two-package，待《恶》《狂人日志》交叉仲裁。本轮 shi-haoyang 既存包未动。
- **林东青师父归属张力**（reconciliation #2）：本篇明确师从石浩洋（"精神延续/天选之人"），phase0 登记为"吴先生徒弟"，待跨篇仲裁。本轮不改 phase0。
- **既存包微瑕（不在本轮收尾范围，未改动）**：cai-dama 的 build-meta `has_canon_ending: true` 但其 references/ 下缺 canon-ending.md（仅 key-dialogues.md）；本轮按"绝对不要改动 3 个既存包"约束未触碰，仅在此登记供后续轮处理参考。
- **吴志强 slug 待定**：见上"跳过的角色"，留待 coordinator 仲裁。
