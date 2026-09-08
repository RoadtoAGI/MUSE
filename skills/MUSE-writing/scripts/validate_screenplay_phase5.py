"""screenplay Phase 5 sequence_list.yaml 必填字段校验。

被 screenplay-writing 在 Phase 5 写完后自动调用。失败退出 1，全通过退出 0。
"""
import re
import sys
import yaml
from pathlib import Path

TEXT_FIELDS = ("location", "time", "dramatic_purpose")
FILE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
REFERENCEABLE_STATUSES = {"accepted", "bound"}


def _validate_inspiration_refs(
    path: Path,
    seqs: list[dict],
    ledger_path: Path,
) -> list[str]:
    errors: list[str] = []
    refs: list[tuple[int, str]] = []
    for i, seq in enumerate(seqs):
        if not isinstance(seq, dict) or "inspiration_refs" not in seq:
            continue
        raw_refs = seq.get("inspiration_refs")
        if raw_refs in (None, []):
            continue
        if not isinstance(raw_refs, list):
            errors.append(f"{path}: sequences[{i}].inspiration_refs 须为列表")
            continue
        for ref in raw_refs:
            if not isinstance(ref, str) or not ref.strip():
                errors.append(f"{path}: sequences[{i}].inspiration_refs 含非法 ID {ref!r}")
                continue
            refs.append((i, ref))

    if not refs:
        return errors
    if not ledger_path.exists():
        errors.append(f"{path}: 存在 inspiration_refs，但 {ledger_path} 不存在")
        return errors

    try:
        ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{ledger_path}: 无法读取 ledger: {exc}")
        return errors
    cards = (
        ledger.get("inspirations") or ledger.get("inspiration_ledger") or []
        if isinstance(ledger, dict)
        else []
    )
    if not isinstance(cards, list):
        errors.append(f"{ledger_path}: inspirations 须为列表")
        return errors

    ledger_index: dict[str, dict] = {}
    duplicate_ids: set[str] = set()
    for card in cards:
        if not isinstance(card, dict) or not card.get("id"):
            continue
        card_id = card["id"]
        if not isinstance(card_id, str):
            errors.append(f"{ledger_path}: inspiration id 须为字符串")
            continue
        if card_id in ledger_index:
            duplicate_ids.add(card_id)
        ledger_index[card_id] = card
    for card_id in sorted(duplicate_ids):
        errors.append(f"{ledger_path}: 重复 inspiration id {card_id}")

    for i, ref in refs:
        card = ledger_index.get(ref)
        if card is None:
            errors.append(f"{path}: sequences[{i}].inspiration_refs 的 {ref} 在 ledger 中不存在")
            continue
        status = card.get("status")
        if not isinstance(status, str) or status not in REFERENCEABLE_STATUSES:
            errors.append(
                f"{path}: sequences[{i}].inspiration_refs 的 {ref} status={status!r}，"
                "须为 accepted 或 bound"
            )
    return errors


def validate(path: Path, ledger_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"{path}: 无法读取场次表: {exc}"]
    seqs = data.get("sequences") if isinstance(data, dict) else None
    if not isinstance(seqs, list) or not seqs:
        return [f"{path}: sequences 须为非空列表"]
    seen_ids: set[str] = set()
    for i, seq in enumerate(seqs):
        prefix = f"{path}: sequences[{i}]"
        if not isinstance(seq, dict):
            errors.append(f"{prefix} 不是 mapping")
            continue
        sid = seq.get("seq_id")
        if not isinstance(sid, str) or not FILE_ID.fullmatch(sid):
            errors.append(f"{prefix}.seq_id 须为仅含字母、数字、连字符、下划线的文件键")
        elif sid in seen_ids:
            errors.append(f"{path}: 重复 seq_id {sid}")
        else:
            seen_ids.add(sid)
        for field in TEXT_FIELDS:
            value = seq.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} 须为非空文字")
        characters = seq.get("characters_in_scene")
        if not isinstance(characters, list) or any(
            not isinstance(name, str) or not name.strip() for name in characters
        ):
            errors.append(f"{prefix}.characters_in_scene 须为角色名列表，可为空")
        for field in ("act", "scene"):
            if field in seq:
                value = seq[field]
                if type(value) is not int and not (isinstance(value, str) and value.strip()):
                    errors.append(f"{prefix}.{field} 须为整数或非空标签")
        if "arc_position" in seq and not (
            isinstance(seq["arc_position"], str) and seq["arc_position"].strip()
        ):
            errors.append(f"{prefix}.arc_position 须为非空文字，未使用时省略")
    resolved_ledger = ledger_path or path.parent.parent / "inspiration_ledger.yaml"
    errors.extend(_validate_inspiration_refs(path, seqs, resolved_ledger))
    return errors


def main() -> None:
    args = sys.argv[1:] or ["pipeline/screenplay/sequence_list.yaml"]
    all_errors: list[str] = []
    for arg in args:
        p = Path(arg)
        if not p.exists():
            all_errors.append(f"{p}: 文件不存在")
            continue
        all_errors.extend(validate(p))
    if all_errors:
        for e in all_errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    print(f"PASS: {len(args)} 个 sequence_list.yaml 全部必填字段合规")


if __name__ == "__main__":
    main()
