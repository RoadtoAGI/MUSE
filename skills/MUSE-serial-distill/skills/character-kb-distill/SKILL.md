---
name: character-kb-distill
description: 提炼连载接管人物的 persona 与卷级快照。知识库角色参考包委派 canon 蒸馏器，并保留本作目录与已读截止点；角色扮演使用创作侧入口。
user-invocable: true
argument-hint: "snapshot --work-dir <交付根> --role <角色ID> --volume <V##> | build (--novel <书名> | --novel-dir <目录>) --role <中文名> | rebuild <role-slug> (--novel <书名> | --novel-dir <目录>)"
allowed-tools: Read Write Edit Bash Glob
---

# 连载人物蒸馏

两类产物服务不同消费者。接管快照供连载上下文按时点读取；知识库参考包供人物研究与创作参考。先按调用用途选分支，不串行生成两套资产。

## 接管快照

由 takeover-distill 回填角色时调用。输入为交付根、char_id、目标卷，以及 published/manifest.yaml 已登记的原文章节；已有系统 YAML、个人分析和 segments 只作导航。先确认本卷已发布的截止章，再按角色出场定位原文。跨卷沿用上一快照，新的变化来自本卷证据；全书人物总结不能充当早期卷的事实。

欲望、性格与压力选择的依据见 [人物提炼判据](references/mckee-voice-principles.md)。形成判断时保留说话对象、压力、角色知识与时间范围；自觉目标可以独立成立，稳定人物无需补造缺陷或成长。

产物位于 `series/ledgers/characters/<char_id>/`：

- `persona.md`：先选角色最初的出场窗口及截止章，从发布册取得对应原文片段，据此写身份、表达习惯与判断倾向，再处理后续快照。基线章锚取自这份片段；证据少时写短，未呈现的声音或倾向可省略。后续身份、关系、知识与人格变化按发生卷入快照。
- `snapshots/V##.yaml`：首份记录当时基线，`extends: null`；后续 `extends` 指已有的前一份快照，记录本卷变化。角色晚出场时从实际出场卷起链，不补造 V01 经历。没有变化时不制造变化。
- `biography.yaml`：由 takeover-distill 的台账回填步骤写经历节点；此处读取其章锚，不重复另建传记。

`persona.md` 开头记录显示名和本基线实际使用的来源截止章；章序以发布册为准。显示名供阅读，人物目录名 `char_id` 供台账及章卡连接。

```markdown
---
name: <中文显示名>
through_chapter: C0003
---
# <中文显示名>

<该截止点内有证据的人格基线；实质判断附章锚>
```

`through_chapter` 限定整份 persona 的供给时点，包含用作性格依据的行为。例如初见时已任值班员，可保留职责；次章才独立处理故障，这次行动及由此推断的压力表现属于次章。既有职责允许概括当时的能力，具体后续行动须留在发生窗口，不能借早期身份提前写入。截止章不晚于首份快照；早期已成立的关系照实保留。

消费方在当前可见时点达到截止章后才加载正文；尚无整卷快照时也可加载合时的基线。存量 persona 未标截止章时仅在最新续写上下文中兼容读取，历史时点略过并提示补证。接管 persona 不用 `null` 截止章；该值留给有 `V00` 快照的新作开工设计。

卷快照沿用以下结构：

```yaml
schema_version: 1
char_id: <稳定角色ID>
volume_id: V02
extends: V01                       # 首份为 null
through_chapter: C0018              # 本次实际覆盖到的已发布章，部分卷同样填写
state: <当时状态；未变化可省略>
relationships: []                   # 有变化时写明对象、变化方向和生效章
capabilities: []                    # 有变化时写取得/失去及边界
voice_shift: null                   # 无变化或无证据时为空
```

`state / relationships / capabilities / voice_shift` 可放在既有 `delta` 映射中，消费方兼容两种存量结构。`extensions.<substrate>` 只承载原文支持的类型信息；无该维度时不填。`through_chapter` 是覆盖边界，旧包缺该字段时消费方从对应卷的已发布章推定，无法确定时不注入该快照。快照链由消费方从早到晚读取，未被后续改变的信息继续有效。

每项实质判断就地附 `C####` 或 `C####S##` 章锚及必要原文定位。原文明示、角色自述、分析者推断分别表述。推断可跨场景，但事件先后不足以证明因果；角色说自己无所畏惧也不足以证明所有压力下均如此。

落盘时核对：目标角色与卷一致；extends 可回到既有基线；来源不晚于 through_chapter；变化和稳定部分均可解释后续决策。未来身份误入早期快照时修正本次派生物，保留原文。接口检查由接管导出与导入承担，源文是否支持人物判断由本次蒸馏负责。

## 知识库参考包

serial-analysis Phase B 或用户 build/rebuild 请求使用此分支。`--novel` 在本 serial 包解析为 `knowledge-base/novels/<书名>`；`--novel-dir` 使用显式目录。解析后只把绝对 `--novel-dir` 交给 canon，不能原样转发 `--novel`。装有 MUSE-canon-distill 时，通过宿主支持的技能加载方式明确选择 **canon 包**的 `character-kb-distill`，传入：

- `--novel-dir <本作知识库目录的已解析绝对路径>` 与 build 的 `--role`，或 rebuild 的既有 role-slug；
- 本次允许使用的章节范围与截止点；保留所有已确认的来源版本约束。

canon 蒸馏器拥有参考包的模板、原文切片、character_map、结构检查与条件 claims 协议。它在传入的本作目录内构建，工具来自 canon 包，语料不搬入 canon 库。参考中的轨迹按截至目前的证据表达，不把连载进度称为全书终局。

先核实该技能与其脚本可用。依赖不可用时报告参考包构建缺少 canon 扩展；已完成分析和本包接管快照仍可交付。不改为调用本包同名入口，也不运行不存在的本地知识库脚本。
