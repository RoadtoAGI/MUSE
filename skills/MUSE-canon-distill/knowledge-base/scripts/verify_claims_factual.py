"""按需角色事实核对：生成待处理清单，或检查已有来源记录；不主动联网。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml


def _load_claims(role_dir: Path) -> list[dict]:
    path = role_dir / "claims.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise ValueError("claims.yaml 须为含 claims 列表的映射")
    if any(not isinstance(claim, dict) for claim in data["claims"]):
        raise ValueError("claims 条目须为映射")
    return data["claims"]


def build_pending_batch(role_dir: Path) -> list[dict]:
    return [
        {key: claim.get(key) for key in ("id", "text", "type", "source_locators", "confidence")}
        for claim in _load_claims(role_dir)
        if claim.get("verification_required")
        and claim.get("verification_status", "unresolved") == "unresolved"
    ]


def _check_sources(cid: str, claim: dict, source_root: Path) -> list[str]:
    sources = claim.get("verification_sources")
    if not isinstance(sources, list) or not sources:
        return [f"claim {cid}：缺 verification_sources（须为非空 list）"]
    issues = []
    for index, source in enumerate(sources):
        label = f"claim {cid}：verification_sources[{index}]"
        if not isinstance(source, dict):
            issues.append(f"{label} 须为映射")
            continue
        quote = source.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            issues.append(f"{label} 缺实际 quote")
            continue
        locator = source.get("source_locator")
        if locator is not None:
            match = re.fullmatch(r"(.+):L([0-9]+)(?:-L([0-9]+))?", str(locator))
            if not match or locator not in (claim.get("source_locators") or []):
                issues.append(f"{label} source_locator 无效或未列在 claim.source_locators")
                continue
            raw_path, start, end = match.groups()
            root = source_root.resolve()
            path = (root / raw_path).resolve()
            try:
                path.relative_to(root)
                lines = path.read_text(encoding="utf-8").splitlines()
                start, end = int(start), int(end or start)
                if not 1 <= start <= end <= len(lines):
                    raise ValueError("行号越界")
                window = "\n".join(lines[start - 1:end])
                if "".join(quote.split()) not in "".join(window.split()):
                    raise ValueError("quote 不在所指原文窗口内")
            except (OSError, ValueError) as exc:
                issues.append(f"{label} 原文核对失败: {exc}")
        else:
            url = source.get("url")
            parsed = urlparse(url) if isinstance(url, str) else None
            if not parsed or parsed.scheme not in {"http", "https"} or not parsed.hostname:
                issues.append(f"{label} 须有原文 source_locator 或有效 http(s) url")
    return issues


def check_claims_writeback(role_dir: Path, *, source_root: Path | None = None) -> list[str]:
    """检查已有核对记录；本地引文回查原文，外部来源仅检查 URL 与摘录结构。

    字段或引文匹配不能证明原文支持解释；该语义判断由当前执行者负责。
    """
    try:
        claims = _load_claims(role_dir)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"claims.yaml 读取失败: {exc}"]
    issues = []
    root = source_root if source_root is not None else role_dir.parent.parent
    for claim in claims:
        cid = claim.get("id", "?")
        if not claim.get("verification_required"):
            continue
        if not isinstance(claim.get("text"), str) or not claim["text"].strip():
            issues.append(f"claim {cid}：缺 text")
        status = claim.get("verification_status", "unresolved")
        if status == "unresolved":
            issues.append(f"claim {cid}：verification_required 但 status=unresolved（核对未完成）")
        elif status in {"verified", "disputed"}:
            issues.extend(_check_sources(cid, claim, root))
            if status == "disputed" and not str(claim.get("resolution_note") or "").strip():
                issues.append(f"claim {cid}：status=disputed 但缺 resolution_note")
        else:
            issues.append(f"claim {cid}：未知 verification_status={status!r}")
    return issues


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, help="原文 locator 的根；默认角色目录所属作品根")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit-batch", action="store_true", help="写本次 required/unresolved 清单")
    mode.add_argument("--check", action="store_true", help="核对已有来源记录；不联网")
    args = parser.parse_args(argv)
    if not args.role_dir.is_dir():
        parser.exit(1, f"ERROR: --role-dir 不是有效目录: {args.role_dir}\n")
    if args.emit_batch:
        try:
            batch = build_pending_batch(args.role_dir)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            parser.exit(1, f"claims.yaml 读取失败: {exc}\n")
        # 空清单覆盖旧结果，避免把上次 pending 误作当前任务。
        output = args.role_dir / "pending_verification.json"
        output.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"待核对 {len(batch)} 条: {output}")
        print("先回读目标版本原文，具体来源冲突再补查外部资料；回写实际来源与状态。")
        parser.exit(0)
    issues = check_claims_writeback(args.role_dir, source_root=args.source_root)
    if issues:
        parser.exit(1, "\n".join(issues) + "\n")
    print(f"{args.role_dir.name}: 已有 claims 来源记录检查通过（未启用时可为空）")
    parser.exit(0)


if __name__ == "__main__":
    main()
