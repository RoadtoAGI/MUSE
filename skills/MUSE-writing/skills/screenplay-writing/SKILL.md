---
name: screenplay-writing
description: 为原创或改编创作剧本，包括影视、舞台剧、戏曲、音乐剧、歌剧与广播剧。用户要求剧本形态时优先于小说改编入口；复用 Phase 0–4 设计，内联完成场次规划、剧本写作、审阅与 script.md 整合。
---

# 剧本创作

## 执行关系

```text
需求与媒介 → 初始化 run → 按需原型调研
                              ↓
           Phase 0 → 1 → 2 → 3 → 4
                              ↓
            场次规划 → 设计检查 → 作者大纲裁决
                              ↓
               按列表顺序写场次、局部审阅
                              ↓
                    整合为 script.md
```

通过宿主支持的 skill 入口加载下游；没有 Skill 工具时，读取安装位置的对应 SKILL.md 及当前阶段需要的 reference。`${CLAUDE_PLUGIN_ROOT}` 指本 writing 包。跨包检索使用已安装包的入口，返回本 run 的参考文件。

## 初始化与恢复

新 run 调用现有初始化脚本，普通交付用 `release`，明确的实验或冒烟任务才选 `evaluation` / `smoke`：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_run.py --run-intent release --results-dir results/ --query "<本次剧本需求>"
# 已给完整目录时使用：
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_run.py --run-intent release --run-dir <work_dir>
```

stdout 为 `work_dir`。恢复已有 run 时读取既有产物与 `pipeline/run_state.yaml`，从实际缺失或受修改影响的阶段继续；保留其他状态字段。

## 来源与设计

改编范围、目标媒介、受众、篇幅和制作条件在 Phase 0 `requirements` 中记录。已有资料足够时直接使用；来源、版本或表演形态有缺口时调用 `Skill prototype-research`，传 `work_dir`、原型和具体问题，使用 `reference_only`。调研输出是候选，作者指定保留的事实与创作范围仍有约束力。

**promotion 时点**：Phase 0–4 采用候选时，在对应设计定稿前按 [card 映射](../prototype-research/references/prototype-card-schema.md) 写入 `pipeline/inspiration_ledger.yaml`，补齐适用条件、`abstraction / fit_signal / project_encoding`，设 `status: accepted`。Phase 5 用 `inspiration_refs` 绑定本场采用项并更新为 `bound`。只有实际分阶段揭示的 pattern 才补 `disclosure_ladder`；普通事实直接进入相应设计字段。

依次加载 `phase0-conception`、`phase1-world-building`、`phase2-character`、`phase3-spine`、`phase4-structure`。每次传入当前媒介、已有设计与相关来源。Phase 2 在本链只完成人物设计；Phase 3 从人物设计的经历、初始状态与知识边界构思选择。剧本执行者直接消费这些依据，无需构建小说 actor 资产。

## 场次规划与大纲裁决

读取 Phase 4 的 `arc_expansions` 与因果、呈现顺序，结合 Phase 0–3 将序列展开为剧本场次。按 [场次契约](references/phase5-sequence-list-schema.md) 写 `pipeline/screenplay/sequence_list.yaml`。这里的 `seq_id` 是剧本场次文件键；它与 Phase 4 的序列尺度不同，无需一一对应。

检查人物何时知道什么、世界条件、场次依赖和必要结果是否衔接，再运行格式与引用校验：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_screenplay_phase5.py <work_dir>/pipeline/screenplay/sequence_list.yaml
```

失败按具体错误修复。读取 `run_state.yaml.outline_gate`：缺失视为 `pending`；`passed` / `waived` 沿用。待裁决时展示场次骨架、关键设计与路径，由作者通过、修改或中止；明确免审记 `waived`。更新时保留兄弟字段；已通过的大纲发生实质修改时回到本闸，免审授权按其范围沿用。

## 写作与反馈

按列表呈现顺序，加载 [writer 规则](references/screenplay-writer-rules.md)，逐场写 `pipeline/screenplay/scenes/{seq_id}.md`。写作前取得作者要求、人物与世界依据、该场必要结果及已采用的 ledger 内容；场次摘要不足以替代这些信息。

每场完成后依 [剧本审阅](references/screenplay-review.md) 检查。局部表达问题原位修订；设计矛盾回到造成问题的 Phase 并更新受影响场次；可成立的审美选择交作者裁决。此链由剧本执行者内联完成写作和审阅。

## 整合与输出

按 [整合规则](references/phase7-assembly.md)，依 `sequences` 列表顺序读取明确的场次文件，整合到 `<work_dir>/script.md`。输出形式随目标媒介：影视可用 Fountain 风格，舞台、戏曲与音乐剧采用相应的舞台指示、角色对白及唱段标记。

保留 Phase 0–4 设计、场次表、场次正文和最终 `script.md`；来源候选及采用记录在本 run 的 references / ledger 中维护。
