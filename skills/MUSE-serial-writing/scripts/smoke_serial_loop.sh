#!/usr/bin/env bash
# smoke_serial_loop.sh —— 连载生命周期脚本链端到端 smoke（T21，不调 LLM）
#
# 串起 init_series → materialize_chapter → publish_chapter → materialize_chapter
# → reconcile_series → serial_lint 全链路；所有 fixture（卷纲/伪 draft/伪 recap/
# escape hatch）内嵌本脚本，不依赖任何外部产物或网络。幂等：每次运行先清理固定
# 子目录 <root>/smoke-loop 再重建，可反复重跑。
#
# 用法：
#   bash skills/MUSE-serial-writing/scripts/smoke_serial_loop.sh [root_dir]
#     root_dir 默认 tmp/serial-smoke（相对当前工作目录）
#
# 退出码：0 全通过；非 0 附 [SMOKE FAIL] 步骤名。

set -euo pipefail

ROOT_ARG="${1:-tmp/serial-smoke}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SMOKE_DIR="${ROOT_ARG}/smoke-loop"
WORKS_ROOT="${SMOKE_DIR}/works"
SLUG="e2e"

CURRENT_STEP="bootstrap"
on_error() {
    echo "[SMOKE FAIL] step=${CURRENT_STEP} (line ${BASH_LINENO[0]})" >&2
    exit 1
}
trap on_error ERR

step() {
    CURRENT_STEP="$1"
    echo "=== [SMOKE] ${CURRENT_STEP} ===" >&2
}

# ---------------------------------------------------------------------------
# 0. 清理 + 重建固定子目录（幂等：不用 rm -rf，改用 python shutil.rmtree）
# ---------------------------------------------------------------------------
step "清理 smoke-loop 子目录"
python3 -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" "${SMOKE_DIR}"
mkdir -p "${SMOKE_DIR}"

# ---------------------------------------------------------------------------
# 1. init_series —— 全新工作区
# ---------------------------------------------------------------------------
step "init_series"
WORK_DIR="$(python3 "${SCRIPT_DIR}/init_series.py" \
    --slug "${SLUG}" --works-root "${WORKS_ROOT}" --title "Smoke E2E 测试系列")"
[ -n "${WORK_DIR}" ] || { echo "[SMOKE FAIL] init_series 未输出工作区路径" >&2; exit 1; }
[ -d "${WORK_DIR}" ] || { echo "[SMOKE FAIL] 工作区目录不存在: ${WORK_DIR}" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1b. worldbook fixture（index + 公理册 + 机制册，两段式）——验证装配③段：
#     地图恒注 / 公理册硬约束恒注 / 声明分册素材库全文 / 未声明素材库不注入
# ---------------------------------------------------------------------------
step "放置 worldbook fixture"
cat > "${WORK_DIR}/series/worldbook/index.yaml" <<'EOF'
schema_version: 1
sections:
  - section_id: power-system
    file: power-system.md
    title: 力量体系公理
    mutability: axiom
    summary_line: 三系并立，天花板渡劫飞升
  - section_id: factions
    file: factions.md
    title: 势力版图
    mutability: append
    summary_line: 九州四大宗门两朝廷
EOF
cat > "${WORK_DIR}/series/worldbook/power-system.md" <<'EOF'
# 力量体系公理

## 硬约束表

- 剑修-丹修-阵修三系并立，跨系兼修必付神识代价
- SMOKE-HARD-AXIOM-MARKER

## 素材库

- 剑修出剑时剑鸣如龙吟（氛围素材）
EOF
cat > "${WORK_DIR}/series/worldbook/factions.md" <<'EOF'
# 势力版图

## 硬约束表

- 黑石城属青云宗辖地，城主由宗门外门长老兼任

## 素材库

- SMOKE-SOFT-FACTIONS-MARKER：黑石城坊市每逢初一有鬼市
EOF

# ---------------------------------------------------------------------------
# 2. 手工放置卷纲 fixture（V01，C0001 + C0002，同单元 U01，opened/closed 留空
#    避免 thread-closure 检查引入额外 threads.yaml 条目依赖；world_reveal_plan
#    带一条 planned + planned_at 远章锚，验证装配的防提前兑现禁令标注）
# ---------------------------------------------------------------------------
step "放置卷纲 fixture V01"
mkdir -p "${WORK_DIR}/series/volumes"
mkdir -p "${WORK_DIR}/pipeline"
cat > "${WORK_DIR}/pipeline/inspiration_ledger.yaml" <<'EOF'
schema_version: 1
references: []
EOF
cat > "${WORK_DIR}/series/volumes/V01.yaml" <<'EOF'
schema_version: 1
volume_id: V01
status: active
protagonist_delta:
  from: 隐忍蛰伏，只求自保
  to: 主动出击，愿为盟友冒险
volume_question: 主角能否在黑石城站稳脚跟并查出灭门线索
tentpoles: []
narrative_lines:
  - line_id: investigation
    description: 主角追查灭门线索
    active_at: [U01]
  - line_id: frontier-war
    description: 边境战事延续扩大
    active_at: [U02]
world_reveal_plan:
  - reveal_id: W-V01-01
    reveal: 黑石城地底藏有前朝阵法遗迹
    from_ceiling: 阵修一系的阵法体系锚点
    status: planned
    planned_at: C0009
chapters:
  - chapter_id: C0001
    unit: U01
    logline: 主角在寿宴上以一手剑术震慑全场，引来旧仇人的注意
    hook_type: 悬念
    opened: []
    closed: []
    status: outline
  - chapter_id: C0002
    unit: U01
    logline: 密信曝光，昔日恩怨浮出水面
    hook_type: 反转
    opened: []
    closed: []
    status: outline
EOF

# ---------------------------------------------------------------------------
# 辅助函数：给章卡回填 hook.design（materialize 只预填 hook.type，design 留 null
# 待编排展开；serial_lint hook-fields 检查要求两者皆非空，smoke 用占位值回填，
# 模拟 phase6 编排产出）
# ---------------------------------------------------------------------------
patch_hook_design() {
    local card_path="$1"
    local design_text="$2"
    python3 - "${card_path}" "${design_text}" <<'PYEOF'
import sys
import yaml

card_path, design_text = sys.argv[1], sys.argv[2]
with open(card_path, encoding="utf-8") as f:
    data = yaml.safe_load(f)
data.setdefault("hook", {})
data["hook"]["design"] = design_text
with open(card_path, "w", encoding="utf-8") as f:
    yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
PYEOF
}

# ---------------------------------------------------------------------------
# 3. materialize C0001（卷内首章，prev_chapter 应为 null——全作品第一章）
# ---------------------------------------------------------------------------
step "materialize C0001"
C1_DIR="$(python3 "${SCRIPT_DIR}/materialize_chapter.py" \
    --work-dir "${WORK_DIR}" --volume V01 --chapter C0001)"
[ -d "${C1_DIR}" ] || { echo "[SMOKE FAIL] C0001 workspace 不存在: ${C1_DIR}" >&2; exit 1; }
grep -q "^prev_chapter: null$" "${C1_DIR}/chapter_card.yaml" \
    || { echo "[SMOKE FAIL] C0001 chapter_card.prev_chapter 应为 null" >&2; exit 1; }

patch_hook_design "${C1_DIR}/chapter_card.yaml" "主角当众亮剑震慑全场，全场哗然（smoke 占位设计）"

# ---------------------------------------------------------------------------
# 4. 伪 draft + 伪 recap + skip_review escape hatch（发布 gate 硬性下限二选一：
#    phase6_development.yaml 或有效 skip_review.yaml；smoke 用后者跳过整条
#    §1.5 场景审阅链路；verify_review_complete.py 显式核对有效 skip_review，
#    未提供有效许可时缺失 phase6_development.yaml 会阻断）
# ---------------------------------------------------------------------------
step "构造 C0001 伪 draft/recap/skip_review"

C1_DRAFT_TAIL_MARKER="旧仇人在人群中冷冷一笑，转身离去。"
cat > "${C1_DIR}/draft.md" <<EOF
# C0001 smoke 占位正文

这是 smoke 测试用的伪造章节正文，仅用于验证发布事务脚本链的完整性，不代表真实
创作内容。主角在寿宴上以一手剑术震慑全场，引来旧仇人的注意。${C1_DRAFT_TAIL_MARKER}
EOF

C1_SUMMARY="主角在寿宴上以剑术震慑全场，引来旧仇人的注意，此为 smoke fixture 占位摘要"
{
    echo "schema_version: 1"
    echo "chapter_id: C0001"
    echo "summary: ${C1_SUMMARY}"
    echo "deltas:"
    echo "  causal_edges: []"
    echo "  character_deltas: []"
    echo "  fact_deltas: []"
    echo "  thread_events: []"
} > "${C1_DIR}/recap.yaml"

mkdir -p "${C1_DIR}/pipeline/audit"
cat > "${C1_DIR}/pipeline/audit/skip_review.yaml" <<'EOF'
reason: "smoke 测试跳过审阅链路，仅验证发布事务脚本链完整性"
risk_acknowledged: true
EOF

# ---------------------------------------------------------------------------
# 4b. AIGC 放行凭据：hash 不一致必须阻断发布（负测）→ 签发正确 hash（正测，
#     step 5 的 publish 用它通过 gate 凭据核验）
# ---------------------------------------------------------------------------
step "AIGC 凭据负测：hash 不一致阻断发布"
cat > "${C1_DIR}/pipeline/aigc_clearance.yaml" <<'EOF'
schema_version: 1
chapter_id: C0001
draft_sha256: deadbeef0000000000000000000000000000000000000000000000000000dead
verdict: pass
mode: full
cleared_at: "2026-07-18T00:00:00"
EOF
if python3 "${SCRIPT_DIR}/publish_chapter.py" --work-dir "${WORK_DIR}" --chapter C0001 >/dev/null 2>&1; then
    echo "[SMOKE FAIL] 凭据 hash 不一致时 publish 未阻断" >&2
    exit 1
fi

step "签发正确 hash 的 AIGC 放行凭据"
python3 - "${C1_DIR}" <<'PYEOF'
import hashlib
import sys
from pathlib import Path

c1 = Path(sys.argv[1])
digest = hashlib.sha256((c1 / "draft.md").read_bytes()).hexdigest()
(c1 / "pipeline" / "aigc_clearance.yaml").write_text(
    "schema_version: 1\n"
    "chapter_id: C0001\n"
    f"draft_sha256: {digest}\n"
    "verdict: pass\n"
    "mode: full\n"
    'cleared_at: "2026-07-18T00:00:00"\n',
    encoding="utf-8",
)
PYEOF

# ---------------------------------------------------------------------------
# 5. publish C0001（四步事务）
# ---------------------------------------------------------------------------
step "publish C0001"
python3 "${SCRIPT_DIR}/publish_chapter.py" --work-dir "${WORK_DIR}" --chapter C0001
[ -f "${WORK_DIR}/published/V01C0001.md" ] \
    || { echo "[SMOKE FAIL] published/V01C0001.md 未产出" >&2; exit 1; }
grep -q "chapter_id: C0001" "${WORK_DIR}/published/manifest.yaml" \
    || { echo "[SMOKE FAIL] manifest.yaml 未登记 C0001" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 6. materialize C0002（prev_chapter=C0001；验证 recap gate 通过 +
#    prev_chapter_tail 存在 + serial_context 含 C0001 summary）
# ---------------------------------------------------------------------------
step "materialize C0002"
C2_DIR="$(python3 "${SCRIPT_DIR}/materialize_chapter.py" \
    --work-dir "${WORK_DIR}" --volume V01 --chapter C0002)"
[ -d "${C2_DIR}" ] || { echo "[SMOKE FAIL] C0002 workspace 不存在: ${C2_DIR}" >&2; exit 1; }

step "断言 C0002 recap gate 已通过（prev_chapter 链）"
grep -q "^prev_chapter: C0001$" "${C2_DIR}/chapter_card.yaml" \
    || { echo "[SMOKE FAIL] C0002 chapter_card.prev_chapter 应为 C0001" >&2; exit 1; }

step "断言系列灵感账本链接已建且可解析"
[ -L "${C2_DIR}/pipeline/inspiration_ledger.yaml" ] \
    || { echo "[SMOKE FAIL] pipeline/inspiration_ledger.yaml 符号链接未创建" >&2; exit 1; }
[ -f "${C2_DIR}/pipeline/inspiration_ledger.yaml" ] \
    || { echo "[SMOKE FAIL] inspiration ledger 链接指向的文件不可解析" >&2; exit 1; }

step "断言 prev_chapter_tail.md 存在且内容来自 C0001 draft"
[ -f "${C2_DIR}/pipeline/prev_chapter_tail.md" ] \
    || { echo "[SMOKE FAIL] prev_chapter_tail.md 未产出" >&2; exit 1; }
grep -qF "${C1_DRAFT_TAIL_MARKER}" "${C2_DIR}/pipeline/prev_chapter_tail.md" \
    || { echo "[SMOKE FAIL] prev_chapter_tail.md 未包含 C0001 draft 尾句" >&2; exit 1; }

step "断言 serial_context.md 含 C0001 summary"
[ -f "${C2_DIR}/pipeline/serial_context.md" ] \
    || { echo "[SMOKE FAIL] serial_context.md 未产出" >&2; exit 1; }
grep -qF "C0001" "${C2_DIR}/pipeline/serial_context.md" \
    || { echo "[SMOKE FAIL] serial_context.md 未提及 C0001" >&2; exit 1; }
grep -qF "${C1_SUMMARY}" "${C2_DIR}/pipeline/serial_context.md" \
    || { echo "[SMOKE FAIL] serial_context.md 未包含 C0001 recap summary 全文" >&2; exit 1; }
grep -qF "investigation：主角追查灭门线索" "${C2_DIR}/pipeline/serial_context.md" \
    || { echo "[SMOKE FAIL] serial_context.md 未注入本单元活跃叙事线" >&2; exit 1; }
if grep -qF "frontier-war" "${C2_DIR}/pipeline/serial_context.md"; then
    echo "[SMOKE FAIL] serial_context.md 注入了未活跃叙事线" >&2
    exit 1
fi

patch_hook_design "${C2_DIR}/chapter_card.yaml" "密信曝光，昔日恩怨浮出水面（smoke 占位设计）"

# ---------------------------------------------------------------------------
# 6b. 角色包符号链接 + 编排补全→重装配序列 + ③段注入断言
# ---------------------------------------------------------------------------
step "断言角色包符号链接已建且可解析"
[ -L "${C2_DIR}/pipeline/story-character-skills" ] \
    || { echo "[SMOKE FAIL] pipeline/story-character-skills 符号链接未创建" >&2; exit 1; }
[ -d "${C2_DIR}/pipeline/story-character-skills" ] \
    || { echo "[SMOKE FAIL] story-character-skills 链接指向的目录不可解析" >&2; exit 1; }

step "模拟编排补全章卡（pov/实体/分册声明）"
python3 - "${C2_DIR}/chapter_card.yaml" <<'PYEOF'
import sys
import yaml

p = sys.argv[1]
with open(p, encoding="utf-8") as f:
    card = yaml.safe_load(f)
card["pov"] = "hero"
ri = card.setdefault("recap_inputs", {})
ri["characters"] = ["hero"]
ri["worldbook_sections"] = ["factions"]
with open(p, "w", encoding="utf-8") as f:
    yaml.safe_dump(card, f, allow_unicode=True, sort_keys=False)
PYEOF

step "编排后重装配（重跑 assemble_serial_context）"
python3 "${SCRIPT_DIR}/assemble_serial_context.py" --work-dir "${WORK_DIR}" --chapter C0002

step "断言 ③段注入：地图/公理册硬约束恒注/声明分册素材库/防提前兑现禁令"
CTX="${C2_DIR}/pipeline/serial_context.md"
grep -qF "设定集地图" "${CTX}" \
    || { echo "[SMOKE FAIL] serial_context 缺设定集地图" >&2; exit 1; }
grep -qF "SMOKE-HARD-AXIOM-MARKER" "${CTX}" \
    || { echo "[SMOKE FAIL] 公理册硬约束表未恒注（未声明也应在）" >&2; exit 1; }
grep -qF "SMOKE-SOFT-FACTIONS-MARKER" "${CTX}" \
    || { echo "[SMOKE FAIL] 声明分册 factions 素材库未全文注入" >&2; exit 1; }
if grep -qF "剑鸣如龙吟" "${CTX}"; then
    echo "[SMOKE FAIL] 未声明公理册 power-system 的素材库不应注入" >&2
    exit 1
fi
grep -qF "禁止提前兑现" "${CTX}" \
    || { echo "[SMOKE FAIL] planned reveal（planned_at=C0009）未标注防提前兑现禁令" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 7. reconcile_series 全绿（C0001 已完整发布 / C0002 在写常态，均不 hard_fail）
# ---------------------------------------------------------------------------
step "reconcile_series 全绿"
RECON_OUT="$(python3 "${SCRIPT_DIR}/reconcile_series.py" --work-dir "${WORK_DIR}")"
echo "${RECON_OUT}" >&2
echo "${RECON_OUT}" | grep -q "^hard_fail: false$" \
    || { echo "[SMOKE FAIL] reconcile_series hard_fail 非 false" >&2; exit 1; }
echo "${RECON_OUT}" | grep -q "state: published$" \
    || { echo "[SMOKE FAIL] reconcile_series 未将 C0001 判定为 published" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 8. serial_lint 全绿（默认 --check all）
# ---------------------------------------------------------------------------
step "serial_lint 全绿"
LINT_OUT="$(python3 "${SCRIPT_DIR}/serial_lint.py" --work-dir "${WORK_DIR}")"
echo "${LINT_OUT}" >&2
echo "${LINT_OUT}" | grep -q "^status: PASS$" \
    || { echo "[SMOKE FAIL] serial_lint status 非 PASS" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 9. 人为删 manifest 条目重放 reconcile —— 验证恢复矩阵判定"只补④"
#    （manifest 缺席 + recap/台账转正(vacuous)/published 文件均齐全 →
#    pending_manifest_registration，语义"只补 manifest.yaml 登记"）
# ---------------------------------------------------------------------------
step "删 manifest 条目模拟恢复场景"
python3 - "${WORK_DIR}" <<'PYEOF'
import sys
import yaml
from pathlib import Path

work_dir = Path(sys.argv[1])
manifest_path = work_dir / "published" / "manifest.yaml"
data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
entries = data.get("entries") or []
before = len(entries)
data["entries"] = [e for e in entries if e.get("chapter_id") != "C0001"]
after = len(data["entries"])
assert after == before - 1, f"预期恰好删除一条 C0001 manifest 条目，实际 {before} -> {after}"
manifest_path.write_text(
    yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
)
print(f"[smoke] manifest entries: {before} -> {after}", file=sys.stderr)
PYEOF

step "重放 reconcile_series 验证恢复矩阵判定"
RECON_OUT2="$(python3 "${SCRIPT_DIR}/reconcile_series.py" --work-dir "${WORK_DIR}")"
echo "${RECON_OUT2}" >&2
echo "${RECON_OUT2}" | grep -q "^hard_fail: false$" \
    || { echo "[SMOKE FAIL] 删 manifest 条目后 hard_fail 非 false" >&2; exit 1; }
echo "${RECON_OUT2}" | grep -q "state: pending_manifest_registration$" \
    || { echo "[SMOKE FAIL] 恢复矩阵未判定 C0001 为 pending_manifest_registration" >&2; exit 1; }
echo "${RECON_OUT2}" | grep -qF "只补 manifest.yaml 登记" \
    || { echo "[SMOKE FAIL] 恢复矩阵 action 措辞未匹配预期的\"只补 manifest.yaml 登记\"" >&2; exit 1; }

echo "[SMOKE PASS] init_series → materialize C0001 → publish C0001 → materialize C0002" >&2
echo "[SMOKE PASS] → reconcile 全绿 → serial_lint 全绿 → 删 manifest 重放恢复矩阵判定\"只补④\"" >&2
echo "[SMOKE PASS] 全链路 smoke 通过：${WORK_DIR}" >&2
