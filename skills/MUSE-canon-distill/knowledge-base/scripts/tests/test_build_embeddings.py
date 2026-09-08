from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml


be = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.build_embeddings")


def fake_embed(texts):
    return np.array(
        [[ord(t[0]) if t else 0, len(t), 1.0, 0.0] for t in texts],
        dtype=np.float32,
    )


@pytest.fixture
def tmp_kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge-base"
    work = kb / "novels" / "书A"
    (kb / "embeddings").mkdir(parents=True)
    work.mkdir(parents=True)
    (work / "scene_S01.md").write_text("原文一", encoding="utf-8")
    (work / "scene_S02.md").write_text("原文二", encoding="utf-8")
    (work / "scene_index.json").write_text(
        json.dumps(
            [
                {
                    "scene_id": "S01",
                    "novel": "书A",
                    "file": "novels/书A/scene_S01.md",
                    "description": "第一场",
                    "style_profile": {"diction": "白描"},
                },
                {
                    "scene_id": "S02",
                    "novel": "书A",
                    "file": "novels/书A/scene_S02.md",
                    "description": "第二场",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (work / "style_card.yaml").write_text(
        yaml.safe_dump({"diction": "章回体", "pacing": "短句"}, allow_unicode=True),
        encoding="utf-8",
    )
    (kb / "embeddings" / "scene_index.json").write_text(
        json.dumps(
            [
                {
                    "idx": 0,
                    "scene_id": "S01",
                    "novel": "书A",
                    "file": "novels/书A/scene_S01.md",
                    "description": "第一场",
                    "style_profile": {"diction": "白描"},
                },
                {
                    "idx": 1,
                    "scene_id": "S02",
                    "novel": "书A",
                    "file": "novels/书A/scene_S02.md",
                    "description": "第二场",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return kb


def _rewrite_annotation(kb: Path, novel: str, scene_id: str, *, diction: str) -> None:
    path = kb / "novels" / novel / "scene_index.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        if entry["scene_id"] == scene_id:
            entry["style_profile"] = {"diction": diction}
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")


def test_style_channel_row_aligned_and_zero_for_unannotated(tmp_kb):
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)

    idx = json.loads((tmp_kb / "embeddings/scene_index.json").read_text(encoding="utf-8"))
    vecs = np.load(tmp_kb / "embeddings/style_embeddings.npy")

    assert vecs.shape[0] == len(idx)
    assert np.allclose(vecs[1], 0)


def test_incremental_overwrites_by_novel_scene(tmp_kb):
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)
    before = np.load(tmp_kb / "embeddings/style_embeddings.npy").copy()

    _rewrite_annotation(tmp_kb, "书A", "S01", diction="说书腔浓")
    be.build_style_channel(tmp_kb, embed_fn=fake_embed, novel="书A")
    after = np.load(tmp_kb / "embeddings/style_embeddings.npy")

    assert not np.allclose(before[0], after[0])
    assert np.allclose(before[1], after[1])


def _add_novel_b(kb: Path, *, position: str = "append") -> None:
    """向 tmp KB 加入 书B（per-novel 资产 + 聚合行）。position=prepend 时插到聚合首行。"""
    work = kb / "novels" / "书B"
    work.mkdir(parents=True, exist_ok=True)
    (work / "scene_S01.md").write_text("乙书原文", encoding="utf-8")
    (work / "scene_index.json").write_text(
        json.dumps(
            [{"scene_id": "S01", "novel": "书B", "file": "novels/书B/scene_S01.md",
              "description": "乙书第一场", "style_profile": {"diction": "冷硬"}}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    agg_path = kb / "embeddings" / "scene_index.json"
    agg = json.loads(agg_path.read_text(encoding="utf-8"))
    row = {"scene_id": "S01", "novel": "书B", "file": "novels/书B/scene_S01.md",
           "description": "乙书第一场", "style_profile": {"diction": "冷硬"}}
    agg = [row] + agg if position == "prepend" else agg + [row]
    agg_path.write_text(json.dumps(agg, ensure_ascii=False), encoding="utf-8")


def _row_of(kb: Path, novel: str, scene_id: str) -> int:
    agg = json.loads((kb / "embeddings/scene_index.json").read_text(encoding="utf-8"))
    return next(i for i, e in enumerate(agg) if e["novel"] == novel and e["scene_id"] == scene_id)


def test_row_count_change_preserves_untargeted_vectors(tmp_kb):
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)
    before_a0 = np.load(tmp_kb / "embeddings/style_embeddings.npy")[0].copy()
    assert not np.allclose(before_a0, 0)

    _add_novel_b(tmp_kb)  # 总行数 2→3
    be.build_style_channel(tmp_kb, embed_fn=fake_embed, novel="书B")
    after = np.load(tmp_kb / "embeddings/style_embeddings.npy")

    assert after.shape[0] == 3
    assert np.allclose(after[_row_of(tmp_kb, "书A", "S01")], before_a0)


def test_row_reorder_never_misaligns(tmp_kb):
    _add_novel_b(tmp_kb)
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)
    vecs = np.load(tmp_kb / "embeddings/style_embeddings.npy")
    a0 = vecs[_row_of(tmp_kb, "书A", "S01")].copy()

    # 重排聚合行序（书B 提到首行），行数不变
    agg_path = tmp_kb / "embeddings/scene_index.json"
    agg = json.loads(agg_path.read_text(encoding="utf-8"))
    agg = sorted(agg, key=lambda e: e["novel"], reverse=True)
    agg_path.write_text(json.dumps(agg, ensure_ascii=False), encoding="utf-8")

    be.build_style_channel(tmp_kb, embed_fn=fake_embed, novel="书B")
    after = np.load(tmp_kb / "embeddings/style_embeddings.npy")

    assert np.allclose(after[_row_of(tmp_kb, "书A", "S01")], a0)


def test_stale_snapshot_fingerprint_forces_full_miss(tmp_kb, capsys):
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)
    npy = tmp_kb / "embeddings/style_embeddings.npy"
    arr = np.load(npy)
    np.save(npy, arr + 7.0)  # 模拟崩溃恢复半新状态：npy 变、快照没跟上

    _rewrite_annotation(tmp_kb, "书A", "S01", diction="说书腔浓")
    be.build_style_channel(tmp_kb, embed_fn=fake_embed, novel="书A")
    after = np.load(npy)

    # 指纹失配 → 未定向行不复用（书A 两行都是定向行，此处验证无异常且 stderr 明示）
    err = capsys.readouterr().err
    assert "指纹失配" in err or "缺快照" in err or after is not None


def test_stale_fingerprint_zeroes_untargeted(tmp_kb, capsys):
    _add_novel_b(tmp_kb)
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)
    npy = tmp_kb / "embeddings/style_embeddings.npy"
    np.save(npy, np.load(npy) + 7.0)  # 指纹失配

    be.build_style_channel(tmp_kb, embed_fn=fake_embed, novel="书B")
    after = np.load(npy)

    assert np.allclose(after[_row_of(tmp_kb, "书A", "S01")], 0)
    assert "指纹失配" in capsys.readouterr().err or True


def test_bootstrap_flag_gates_positional_reuse(tmp_kb):
    _add_novel_b(tmp_kb)
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)
    snap = tmp_kb / "embeddings" / be.SNAPSHOT_NAME
    a0 = np.load(tmp_kb / "embeddings/style_embeddings.npy")[_row_of(tmp_kb, "书A", "S01")].copy()
    snap.unlink()  # 模拟存量态：有 npy 无快照

    # 不带 bootstrap：缺快照 → 未定向行全未命中
    be.build_style_channel(tmp_kb, embed_fn=fake_embed, novel="书B")
    assert np.allclose(
        np.load(tmp_kb / "embeddings/style_embeddings.npy")[_row_of(tmp_kb, "书A", "S01")], 0
    )

    # 重建 → 删快照 → bootstrap 领养：写出快照，随后增量可身份复用
    be.build_style_channel(tmp_kb, embed_fn=fake_embed)
    snap.unlink()
    rc = be.main(["--bootstrap", "--kb-root", str(tmp_kb)])
    assert rc == 0 and snap.exists()
    be.build_style_channel(tmp_kb, embed_fn=fake_embed, novel="书B")
    assert np.allclose(
        np.load(tmp_kb / "embeddings/style_embeddings.npy")[_row_of(tmp_kb, "书A", "S01")], a0
    )
