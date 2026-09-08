"""
知识库检索：基于 embedding 相似度查询最相关的场景切片

用法（供 Phase 6 Skill 通过 Bash 调用）：

    # 基本检索（返回元数据 + 文件路径）
    python ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/kb_query.py \
        --query "紧张对峙，父子冲突，传统与现代的碰撞"

    # 按题材过滤 + 包含原文 + 保存到文件（推荐用法）
    python ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/kb_query.py \
        --query "武林高手对决" --genre 武侠 --top_k 2 \
        --threshold 0.4 --include-text \
        --output-dir pipeline/references --scene-id S01

    # 按语言过滤
    python ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/kb_query.py \
        --query "tense confrontation" --lang en
"""

import argparse
import math
import re
import json
import os
import sys
import time
import unicodedata
import numpy as np
import yaml
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# 相对导入同目录模块（支持脚本直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paragraph_density import analyze_file as _pd_analyze_file  # noqa: E402
from stylometry import analyze_file as _sm_analyze_file  # noqa: E402
import kb_index  # noqa: E402
from rhetoric_retrieval import (  # noqa: E402
    render_rhetoric_cards,
    select_rhetoric_cards,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Config — env 变量解析（语义化新名 + 旧名 fallback）
# ---------------------------------------------------------------------------
# 推荐：MUSE_KB_API_KEY / MUSE_KB_BASE_URL（语义化）
# 向后兼容：API_BASE_URL（旧装机不报错）
# 首次配置流程见 ../../.env.example + scene-reference/SKILL.md §配置
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-small"
STYLE_HINT_WEIGHT = 0.12  # 语态对齐加权：score + weight × hint 字符二元组覆盖率
STYLE_VEC_WEIGHT = 0.15
STYLE_MODE_DEFAULT = "vector"  # 评测 gate 定值:hybrid+stylevec 过 gate 且 style_match 最高(tmp/rag-eval-r1*.json)
FIT_TIER_TAU = 0.05  # reuse_tier 档位阈值——T9 抽查定值（10 query 人工核档，含 5 条命中元数据
# 贫乏池：射雕英雄传/神雕侠侣/三体Ⅱ）：贫乏池候选 fit 恒 0.0 稳定落 material（方向安全）；
# 有标注候选命中时 fit 普遍 ≥0.14 清晰过阈值落 full；0.05 未观察到误判，维持不改。
# fit 进 rank 权重——T9 gate 定值（design §7）：`+function` 配置对比 `full`，22-query 矩阵
# recall@5 未回退（0.7273=0.7273）、MRR（0.6856→0.6909）与 nDCG@2（0.6067→0.6117）均提升，
# 达标默认启用进 rank_score；与 FIT_TIER_TAU（档位判定阈值）是两个独立参数。
FIT_RANK_WEIGHT = 0.03
BASE_URL = (
    os.getenv("MUSE_KB_BASE_URL")
    or os.getenv("API_BASE_URL")
    or "https://your-compatible-endpoint.example/v1"
)
API_KEY = os.getenv("MUSE_KB_API_KEY") or ""

KB_ROOT = Path(__file__).resolve().parent.parent  # knowledge-base/
EMBEDDINGS_DIR = KB_ROOT / "embeddings"
INDEX_PATH = EMBEDDINGS_DIR / "scene_index.json"
EMBEDDINGS_PATH = EMBEDDINGS_DIR / "scene_embeddings.npy"
STYLE_EMBEDDINGS_PATH = EMBEDDINGS_DIR / "style_embeddings.npy"


# ---------------------------------------------------------------------------
# Failure classes — 让 main 处分类 exit + 写明确 stderr
# ---------------------------------------------------------------------------
class KBConfigError(Exception):
    """API key / base url 未配置（用户可修）"""


class KBInfraError(Exception):
    """embedding 计算失败：401 / 网络 / 上游服务故障（基础设施层）"""


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------
def retry_call(fn, *, max_retries=3, delay=5, label=""):
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            tag = f"[{label}] " if label else ""
            print(f"    {tag}attempt {attempt}/{max_retries} ERROR: {e}",
                  file=sys.stderr)
            if attempt < max_retries:
                time.sleep(delay)
    return None


# ---------------------------------------------------------------------------
# Genre 别名表：Phase 0 输出 → 知识库 genre 值的映射
# 子串匹配处理前缀关系（"青春" ↔ "青春成长"），别名表处理同义异形
# ---------------------------------------------------------------------------
GENRE_ALIASES = {
    # 末世
    "末世": "后末日文学",
    "后末日": "后末日文学",
    "末日": "后末日文学",
    "post-apocalyptic": "后末日文学",
    # 奇幻
    "奇幻": "史诗奇幻",
    "玄幻": "史诗奇幻",
    "fantasy": "史诗奇幻",
    "高奇幻": "高奇幻",
    # 穿越/历史
    "穿越": "历史穿越",
    "历史": "历史小说",
    # 现实主义（Phase 0 常见的模糊输出）
    "文学小说": "现实主义",
    "文学": "现实主义",
    "literary fiction": "现实主义",
    "literary": "现实主义",
    "realism": "现实主义",
    # 武侠/科幻
    "wuxia": "武侠",
    "sci-fi": "科幻",
    "science fiction": "科幻",
}


def _normalize_filter_text(value: str) -> str:
    """统一全半角、大小写与分隔符周边空白，不维护作品特例。"""
    text = unicodedata.normalize("NFKC", value or "").casefold().strip()
    text = re.sub(r"\s*[/|]\s*", "/", text)
    return re.sub(r"\s+", "", text)


def _normalized_contains(needle: str, haystack: str) -> bool:
    normalized_needle = _normalize_filter_text(needle)
    normalized_haystack = _normalize_filter_text(haystack)
    return bool(normalized_needle) and normalized_needle in normalized_haystack


def _genre_matches(query_genre: str, entry_genre: str) -> bool:
    """genre 匹配：子串包含 + 别名表"""
    if not query_genre or not entry_genre:
        return not query_genre  # 无过滤条件时通过
    # 子串匹配
    if _normalized_contains(query_genre, entry_genre) or _normalized_contains(entry_genre, query_genre):
        return True
    # 别名表：将 query_genre 解析为规范值后再比较
    normalized_query = _normalize_filter_text(query_genre)
    canonical = next(
        (value for key, value in GENRE_ALIASES.items() if _normalize_filter_text(key) == normalized_query),
        query_genre,
    )
    if _normalized_contains(canonical, entry_genre) or _normalized_contains(entry_genre, canonical):
        return True
    return False


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """计算 a (1, dim) 与 b (N, dim) 的余弦相似度，返回 (N,)"""
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return (b_norm @ a_norm.T).flatten()


def _cjk_bigrams(text: str) -> set[str]:
    """字符二元组集合（去空白与常见标点）——中文短语匹配的零依赖近似。"""
    chars = [c for c in text if not c.isspace() and c not in "，。、；：/（）「」『』！？·,.;:()<>\"'-"]
    return {a + b for a, b in zip(chars, chars[1:])}


def _text_tokens(text: str) -> list[str]:
    ascii_words = re.findall(r"[A-Za-z0-9_]+", text.lower())
    return ascii_words + sorted(_cjk_bigrams(text))


def _bm25_rank(query_text: str, entries: list[dict], texts: list[str], k1=1.5, b=0.75) -> list[int]:
    query_tokens = _text_tokens(query_text)
    if not query_tokens:
        return []
    docs = [_text_tokens(text) for text in texts]
    if not docs:
        return []
    avgdl = sum(len(doc) for doc in docs) / max(len(docs), 1)
    df: dict[str, int] = {}
    for doc in docs:
        for token in set(doc):
            df[token] = df.get(token, 0) + 1
    scores: list[tuple[float, int]] = []
    n_docs = len(docs)
    for i, doc in enumerate(docs):
        if not doc:
            scores.append((0.0, i))
            continue
        tf: dict[str, int] = {}
        for token in doc:
            tf[token] = tf.get(token, 0) + 1
        score = 0.0
        for token in query_tokens:
            if token not in tf:
                continue
            idf = math.log(1 + (n_docs - df.get(token, 0) + 0.5) / (df.get(token, 0) + 0.5))
            denom = tf[token] + k1 * (1 - b + b * len(doc) / (avgdl or 1))
            score += idf * (tf[token] * (k1 + 1)) / denom
        scores.append((score, i))
    positive = [(score, i) for score, i in scores if score > 0]
    positive.sort(key=lambda item: item[0], reverse=True)
    return [i for _, i in positive]


def _rrf_pool(dense_order: list[int], sparse_order: list[int], pool_k: int, k: int = 60) -> list[int]:
    scores: dict[int, float] = {}
    for order in (dense_order, sparse_order):
        for rank, idx in enumerate(order, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    ranked = sorted(scores, key=lambda idx: scores[idx], reverse=True)
    return ranked[:pool_k]


def _mmr_select(cand_idx: list[int], vecs: np.ndarray, rank_scores: list[float],
                top_k: int, lam: float = 0.7) -> list[int]:
    """Greedy MMR over local candidate indexes; pools no larger than top_k are unchanged."""
    if len(cand_idx) <= top_k:
        return cand_idx
    remaining = list(cand_idx)
    selected: list[int] = []
    score_by_idx = {idx: float(score) for idx, score in zip(cand_idx, rank_scores)}

    while remaining and len(selected) < top_k:
        best_idx = None
        best_score = -float("inf")
        for idx in remaining:
            diversity_penalty = 0.0
            if selected:
                sims = cosine_similarity(vecs[idx:idx + 1], vecs[selected])
                diversity_penalty = float(np.max(sims))
            mmr_score = lam * score_by_idx[idx] - (1 - lam) * diversity_penalty
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx
        selected.append(best_idx)
        remaining.remove(best_idx)
    return selected


def _bm25_text_for(entry: dict) -> str:
    parts: list[str] = []
    if entry.get("description"):
        parts.append(str(entry["description"]))
    if entry.get("tags"):
        parts.append(" ".join(map(str, entry["tags"])))
    if entry.get("file"):
        parts.append(read_scene_text(entry["file"], max_chars=4000))
    return "\n".join(parts)


def _style_text_for(entry: dict) -> str:
    """候选场景的文风文本面 = scene style_profile + work style_card 的全部文字值。"""
    annotations = load_novel_annotations(entry.get("file", ""))
    parts: list[str] = []
    profile = annotations["style_profiles"].get(entry.get("scene_id")) or entry.get("style_profile")
    for blob in (profile, annotations.get("style_card")):
        if not isinstance(blob, dict):
            continue
        for v in blob.values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(item) for item in v)
    return " ".join(parts)


def _function_text_for(entry: dict) -> str:
    """候选场景的功能文本面 = tags + conflict_type/conflict_axis + description（缺字段拼空串）。"""
    parts: list[str] = []
    if entry.get("tags"):
        parts.append(" ".join(map(str, entry["tags"])))
    conflict = entry.get("conflict_type") or entry.get("conflict_axis")
    if conflict:
        parts.append(str(conflict))
    if entry.get("description"):
        parts.append(str(entry["description"]))
    return " ".join(parts)


def _fit_score(hint: str, entry: dict) -> float:
    """功能同构分：CJK 二元组覆盖率 over tags+conflict_type/axis+description。

    缺字段不加分不惩罚（退回可用字段面，全缺则 fit=0）。
    """
    hint_grams = _cjk_bigrams(hint)
    if not hint_grams:
        return 0.0
    grams = _cjk_bigrams(_function_text_for(entry))
    if not grams:
        return 0.0
    return len(hint_grams & grams) / len(hint_grams)


def _apply_fit_rank(candidates: list[dict], function_hint: str,
                    weight: float = FIT_RANK_WEIGHT) -> list[dict]:
    """按功能同构分混合进 rank_score 并重排（design §7 gate 已过，默认启用）。

    先给每条候选写入 fit 字段（供 §1.3 档位判定复用），再以小权重叠加进 rank_score。
    """
    for c in candidates:
        c["fit"] = round(_fit_score(function_hint, c), 3)
    for c in candidates:
        c["rank_score"] = c.get("rank_score", c.get("score", 0.0)) + weight * c["fit"]
    candidates.sort(key=lambda c: c["rank_score"], reverse=True)
    return candidates


def rerank_by_style_hint(candidates: list[dict], style_hint: str,
                         weight: float = STYLE_HINT_WEIGHT) -> list[dict]:
    """按语态提示重排：score + weight × (hint 二元组被该场景文风文本覆盖的比例)。

    无标注的候选覆盖率记 0（不加权不惩罚）；每条候选写入 style_match 便于排查。
    稳定排序：加权分相同时保持原 embedding 序。
    """
    hint_grams = _cjk_bigrams(style_hint)
    if not hint_grams:
        return candidates
    for c in candidates:
        grams = _cjk_bigrams(_style_text_for(c))
        ratio = len(hint_grams & grams) / len(hint_grams)
        c["style_match"] = round(ratio, 3)
        c["_adj_score"] = c["score"] + weight * ratio
    candidates.sort(key=lambda c: c["_adj_score"], reverse=True)
    for c in candidates:
        c.pop("_adj_score", None)
    return candidates


def load_style_channel(index: list[dict]) -> np.ndarray | None:
    """Load row-aligned style vectors; invalid indexes degrade to legacy bigram rerank."""
    if not STYLE_EMBEDDINGS_PATH.exists():
        return None
    vectors = np.load(str(STYLE_EMBEDDINGS_PATH))
    if vectors.shape[0] != len(index):
        print(
            f"⚠️ style_embeddings.npy 行数 {vectors.shape[0]} != scene_index {len(index)}，降级为二元组重排",
            file=sys.stderr,
        )
        return None
    return vectors.astype(np.float32, copy=False)


_EMBED_CACHE: dict[tuple[str, str], list] = {}


def _embed_text_cached(client, model: str, text: str, label: str):
    """进程内 embedding 缓存：同 (model, text) 只发一次 API。

    评测矩阵（多配置 × 同批 query）与重复 hint 场景把串行 API 调用压到唯一文本数。
    失败不缓存（保留重试机会）。
    """
    key = (model, text)
    if key in _EMBED_CACHE:
        return _EMBED_CACHE[key]

    def _embed():
        resp = client.embeddings.create(model=model, input=[text])
        return resp.data[0].embedding

    vec = retry_call(_embed, label=label)
    if vec is not None:
        _EMBED_CACHE[key] = vec
    return vec


def query(query_text: str, genre: str = None, lang: str = None,
          novel: str = None, source_medium: str = "novel",
          top_k: int = 3, threshold: float = 0.0,
          style_hint: str = None,
          style_mode: str = STYLE_MODE_DEFAULT,
          function_hint: str = None,
          hybrid: bool = True,
          mmr_lambda: float = 0.0,
          pool: int | None = None,
          model: str = EMBEDDING_MODEL) -> list[dict]:
    """检索最相关的场景

    两层匹配策略：
    - score >= threshold → match="high"（叙事技法+文风参考）
    - score <  threshold → match="style_only"（仅文风参考）
    所有 genre 内 top_k 结果均返回，不再因低于 threshold 而跳过。

    source_medium 参数（防 medium 污染）：
    - 默认 "novel" —— 主干写小说时只检索小说场景，排除戏剧 / 剧本
    - "all" —— 不过滤 medium
    - "stage_play" / "screenplay" / "teleplay" / ... —— 单值
    - "novel,stage_play" —— 逗号分隔多值（如 screenplay-writing Phase 6 可传 "stage_play"
      只看戏剧；或 "stage_play,screenplay" 多 medium 兼容）
    历史 entry 无 source_medium 字段者按 "novel" 处理（向后兼容）。
    """
    # 加载索引和向量
    if not INDEX_PATH.exists() or not EMBEDDINGS_PATH.exists():
        print(
            "⚠️ 知识库 embeddings 未配置——plugin 默认不含名著语料。\n"
            "   如需启用 scene-reference 链路：把语料放到 knowledge-base/novels/<书名>/，\n"
            "   并自行生成 knowledge-base/embeddings/scene_index.json + scene_embeddings.npy。\n"
            "   reference 链路本场景跳过，主干流程继续。",
            file=sys.stderr,
        )
        sys.exit(2)

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    embeddings = np.load(str(EMBEDDINGS_PATH))

    # 解析 source_medium：None / "all" → 不过滤；其它单值或逗号多值
    if source_medium and source_medium != "all":
        allowed_media = {m.strip() for m in source_medium.split(",") if m.strip()}
    else:
        allowed_media = None

    # 过滤（子串匹配 + 别名表 + medium 隔离）
    if genre or lang or novel or allowed_media:
        mask = []
        for i, entry in enumerate(index):
            entry_medium = entry.get("source_medium", "novel")  # 兼容历史
            if allowed_media and entry_medium not in allowed_media:
                mask.append(False)
            elif genre and not _genre_matches(genre, entry.get("genre", "")):
                mask.append(False)
            elif lang and entry.get("lang") != lang:
                mask.append(False)
            elif novel and not _normalized_contains(novel, entry.get("novel", "")):
                mask.append(False)
            else:
                mask.append(True)
        mask = np.array(mask)
        filtered_indices = np.where(mask)[0]

        if len(filtered_indices) == 0:
            filters = []
            if allowed_media:
                filters.append(f"source_medium={','.join(sorted(allowed_media))}")
            if genre:
                filters.append(f"genre={genre}")
            if lang:
                filters.append(f"lang={lang}")
            if novel:
                filters.append(f"novel={novel}")
            print(f"⚠️ 过滤后无结果（{', '.join(filters)}）", file=sys.stderr)
            return []

        filtered_embeddings = embeddings[filtered_indices]
        filtered_index = [index[i] for i in filtered_indices]
    else:
        filtered_embeddings = embeddings
        filtered_index = index
        filtered_indices = np.arange(len(index))

    # 计算 query embedding
    if not API_KEY:
        raise KBConfigError(
            "API key 未配置：请设置环境变量 MUSE_KB_API_KEY。"
            "首次配置见 knowledge-base/scripts/kb_setup_check.py 或 plugin 根 .env.example。"
        )
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=30)

    query_vec = _embed_text_cached(client, model, query_text, label="query-embed")
    if query_vec is None:
        raise KBInfraError(
            f"Query embedding 计算失败（base_url={BASE_URL}, model={model}）。"
            "常见原因：API key 无效 / 上游服务故障 / 网络不通。"
            "诊断：python3 knowledge-base/scripts/kb_setup_check.py"
        )

    query_vec = np.array(query_vec, dtype=np.float32).reshape(1, -1)

    # 余弦相似度
    scores = cosine_similarity(query_vec, filtered_embeddings)
    style_vectors = None
    style_hint_vec = None
    if style_hint and style_mode == "vector":
        style_vectors_all = load_style_channel(index)
        if style_vectors_all is not None:
            style_hint_vec_raw = _embed_text_cached(client, model, style_hint, label="style-hint-embed")
            if style_hint_vec_raw is not None:
                style_hint_vec = np.array(style_hint_vec_raw, dtype=np.float32).reshape(1, -1)
                if style_hint_vec.shape[1] == style_vectors_all.shape[1]:
                    style_vectors = style_vectors_all[filtered_indices]
                else:
                    print(
                        f"⚠️ style hint 维度 {style_hint_vec.shape[1]} != style_embeddings {style_vectors_all.shape[1]}，降级为二元组重排",
                        file=sys.stderr,
                    )
                    style_hint_vec = None

    # Top-K（不再跳过低分结果，改为分层标注）
    # 语态提示存在时先取更大候选池，按文风标注重排后再截 top_k
    pool_k_default = max(top_k * 3, 9) if (style_hint or hybrid) else top_k
    pool_k = min(pool if pool is not None else pool_k_default, len(scores))
    dense_order = list(np.argsort(scores)[::-1])
    sparse_rank_by_idx: dict[int, int] = {}
    if hybrid:
        texts = [_bm25_text_for(entry) for entry in filtered_index]
        sparse_order = _bm25_rank(query_text, filtered_index, texts)
        sparse_rank_by_idx = {idx: rank for rank, idx in enumerate(sparse_order, start=1)}
        top_indices = _rrf_pool(dense_order, sparse_order, pool_k) if sparse_order else dense_order[:pool_k]
    else:
        top_indices = dense_order[:pool_k]

    candidates = []
    for idx in top_indices:
        score = float(scores[idx])
        entry = filtered_index[idx]
        candidates.append({
            "score": score,
            "dense_score": score,
            "rank_score": score,
            "sparse_rank": sparse_rank_by_idx.get(int(idx)),
            "_local_idx": int(idx),
            "_global_idx": int(filtered_indices[idx]),
            "match": "high" if score >= threshold else "style_only",
            **entry,
        })

    if style_hint and style_mode == "vector" and style_vectors is not None and style_hint_vec is not None:
        for c in candidates:
            local_idx = int(np.where(filtered_indices == c["_global_idx"])[0][0])
            sim = 0.0
            if np.linalg.norm(style_vectors[local_idx]) > 1e-10:
                sim = float(cosine_similarity(style_hint_vec, style_vectors[local_idx:local_idx + 1])[0])
            c["style_match"] = round(sim, 3)
            c["rank_score"] = c["score"] + STYLE_VEC_WEIGHT * sim
        candidates.sort(key=lambda c: c["rank_score"], reverse=True)
    elif style_hint:
        candidates = rerank_by_style_hint(candidates, style_hint)
        for c in candidates:
            c["rank_score"] = c.get("score", 0.0) + STYLE_HINT_WEIGHT * c.get("style_match", 0.0)

    if function_hint:
        candidates = _apply_fit_rank(candidates, function_hint)

    if mmr_lambda > 0 and len(candidates) > top_k:
        local_order = [c["_local_idx"] for c in candidates]
        rank_scores = [c.get("rank_score", c.get("score", 0.0)) for c in candidates]
        selected_locals = _mmr_select(local_order, filtered_embeddings, rank_scores, top_k, lam=mmr_lambda)
        selected_set = set(selected_locals)
        candidates = [c for c in candidates if c["_local_idx"] in selected_set]
        candidates.sort(key=lambda c: selected_locals.index(c["_local_idx"]))

    results = []
    for rank, c in enumerate(candidates[:top_k]):
        c["rank"] = rank + 1
        c.pop("_local_idx", None)
        c.pop("_global_idx", None)
        results.append(c)

    return results


def _allowed_media(source_medium: str | None) -> set[str] | None:
    if source_medium and source_medium != "all":
        return {m.strip() for m in source_medium.split(",") if m.strip()}
    return None


def select_results(select: str, source_medium: str = "novel") -> list[dict]:
    if not INDEX_PATH.exists():
        print("⚠️ scene_index.json 不存在，无法手动指定参考", file=sys.stderr)
        return []
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    allowed_media = _allowed_media(source_medium)
    selected: list[dict] = []
    for raw in [part.strip() for part in select.split(",") if part.strip()]:
        if ":" not in raw:
            print(f"⚠️ 跳过无效 select 项: {raw}", file=sys.stderr)
            continue
        novel_part, scene_id = raw.split(":", 1)
        matches = [
            entry for entry in index
            if _normalized_contains(novel_part, entry.get("novel", ""))
            and entry.get("scene_id") == scene_id
        ]
        if not matches:
            print(f"⚠️ 跳过未找到场景: {raw}", file=sys.stderr)
            continue
        entry = matches[0]
        entry_medium = entry.get("source_medium", "novel")
        if allowed_media and entry_medium not in allowed_media:
            print(f"⚠️ 跳过 {raw}: source_medium={entry_medium} 不在 {','.join(sorted(allowed_media))}", file=sys.stderr)
            continue
        selected.append({
            "rank": len(selected) + 1,
            "score": None,
            "dense_score": None,
            "rank_score": None,
            "sparse_rank": None,
            "style_match": None,
            "match": "selected",
            **entry,
        })
    return selected


def format_candidate_table(results: list[dict]) -> str:
    lines = ["rank\tnovel\tscene_id\tdense\tsparse_rank\tstyle_match\tdescription"]
    for r in results:
        desc = (r.get("description") or "").replace("\n", " ")[:60]
        dense = "" if r.get("score") is None else f"{r.get('score'):.4f}"
        sparse = "" if r.get("sparse_rank") is None else str(r.get("sparse_rank"))
        style = "" if r.get("style_match") is None else str(r.get("style_match"))
        lines.append(
            f"{r.get('rank', '')}\t{r.get('novel', '')}\t{r.get('scene_id', '')}\t"
            f"{dense}\t{sparse}\t{style}\t{desc}"
        )
    return "\n".join(lines)


def read_scene_text(file_path: str, max_chars: int = 0) -> str:
    """读取场景原文，可选截断"""
    abs_path = KB_ROOT / file_path
    if not abs_path.exists():
        return f"[文件不存在: {abs_path}]"
    text = abs_path.read_text(encoding="utf-8")
    if max_chars > 0 and len(text) > max_chars:
        # 在最近的句号/感叹号/问号处截断，避免断在句子中间
        cut = text[:max_chars]
        for sep in ("。", "！", "？", "」", "\n"):
            last = cut.rfind(sep)
            if last > max_chars * 0.7:  # 至少保留 70%
                cut = cut[:last + 1]
                break
        return cut + f"\n\n[…原文共 {len(text)} 字，已截取前 {len(cut)} 字]"
    return text


def read_craft_notes(file_path: str) -> str | None:
    """读取手艺标注（如果存在）"""
    # scenes/scene_S15.md → craft_notes/scene_S15_beats.md
    p = Path(file_path)
    craft_path = KB_ROOT / p.parent.parent / "craft_notes" / (p.stem + "_beats.md")
    if craft_path.exists():
        return craft_path.read_text(encoding="utf-8")
    return None


_NOVEL_ANNOTATIONS_CACHE: dict[str, dict] = {}


def _container_dir(file_path: str) -> Path:
    p = Path(file_path)
    parts = p.parts
    if len(parts) >= 3 and parts[0] in {"novels", "dramas"}:
        return KB_ROOT / parts[0] / parts[1]
    return KB_ROOT / p.parent.parent


def load_novel_annotations(file_path: str) -> dict:
    """读取 per-work style_profile/style_card；缺失或坏文件静默降级。"""
    container = _container_dir(file_path)
    cache_key = str(container)
    if cache_key in _NOVEL_ANNOTATIONS_CACHE:
        return _NOVEL_ANNOTATIONS_CACHE[cache_key]

    annotations: dict = {"style_profiles": {}, "style_card": None}
    try:
        index_path = kb_index.index_path_of(container)
        if index_path is not None:
            for entry in kb_index.load_index(index_path):
                if entry.get("scene_id") and entry.get("style_profile"):
                    annotations["style_profiles"][entry["scene_id"]] = entry["style_profile"]
        card_path = container / "style_card.yaml"
        if card_path.exists():
            card = yaml.safe_load(card_path.read_text(encoding="utf-8")) or {}
            if isinstance(card, dict):
                annotations["style_card"] = card
    except (OSError, ValueError, yaml.YAMLError):
        annotations = {"style_profiles": {}, "style_card": None}

    _NOVEL_ANNOTATIONS_CACHE[cache_key] = annotations
    return annotations


def read_craft_sidecar(file_path: str) -> dict | None:
    """读取结构化手艺 sidecar；无效时静默降级到原 md。"""
    p = Path(file_path)
    sidecar_path = KB_ROOT / p.parent.parent / "craft_notes" / (p.stem + "_beats.yaml")
    if not sidecar_path.exists():
        return None
    try:
        data = yaml.safe_load(sidecar_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if isinstance(data, dict) and isinstance(data.get("patterns"), list):
        return data
    return None


def lookup_inspiration_cards(novel: str, scene_id: str, limit: int = 2) -> list[dict]:
    """按 scene backlink 取 inspiration cards；卡库缺失时静默降级。"""
    insp_dir = KB_ROOT / "inspiration"
    backlinks_path = insp_dir / "_backlinks.json"
    try:
        backlinks = json.loads(backlinks_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    card_ids = backlinks.get(f"{novel}|{scene_id}", [])[:limit]
    cards = []
    for card_id in card_ids:
        try:
            card_path = insp_dir / f"{card_id}.yaml"
            card = yaml.safe_load(card_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(card, dict):
            cards.append(card)
    return cards


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def format_results(results: list[dict], include_text: bool = False,
                    max_chars: int = 0) -> str:
    """格式化输出（供 Claude 解析）"""
    if not results:
        return "=== 无匹配结果（genre 过滤后无场景）==="

    lines = [f"=== 检索结果 (top {len(results)}) ===\n"]

    for r in results:
        match_label = "叙事+文风" if r.get("match") == "high" else "仅文风"
        lines.append(
            f"[{r['rank']}] score={r['score']:.4f} [{match_label}] | "
            f"{r.get('novel', '?')}({r.get('author', '?')}) · {r['scene_id']}"
        )
        if r.get("description"):
            lines.append(f"    描述: {r['description']}")
        if r.get("tags"):
            lines.append(f"    tags: {', '.join(r['tags'])}")
        if r.get("conflict_type"):
            lines.append(f"    冲突: {r['conflict_type']}")
        if r.get("pov"):
            lines.append(f"    POV: {r['pov']}")
        lines.append(f"    字数: {r.get('word_count', '?')}")
        abs_path = KB_ROOT / r["file"]
        lines.append(f"    文件: {abs_path}")

        if include_text:
            text = read_scene_text(r["file"], max_chars=max_chars)
            lines.append(f"\n--- 原文开始 ---\n{text}\n--- 原文结束 ---")
            sidecar = read_craft_sidecar(r["file"])
            if sidecar:
                lines.append("\n--- 手艺拆解 ---")
                for p in sidecar.get("patterns", []):
                    contrast = p.get("ai_default_failure")
                    contrast_text = f"失败对照：{contrast}；" if contrast else ""
                    lines.append(
                        f"- {p.get('pattern_id', '?')} | {p.get('dimension', '?')} | "
                        f"{p.get('original_move', '')}（{contrast_text}"
                        f"迁移：{p.get('transfer_rule', '')}；原句：{p.get('quote', '')}）"
                    )
                organization = sidecar.get("narrative_organization") or {}
                if organization:
                    rendered = "；".join(
                        f"{key}={value}" for key, value in organization.items() if value
                    )
                    lines.append(f"- 叙事组织：{rendered}")
                lines.append("--- 标注结束 ---")
            elif craft := read_craft_notes(r["file"]):
                lines.append(f"\n--- 手艺标注 ---\n{craft}\n--- 标注结束 ---")

        lines.append("")

    return '\n'.join(lines)


_TIER_RANK = {"style": 0, "material": 1, "full": 2}


def _tier_for(result: dict, fit_tau: float) -> str:
    """条目档位（design §1.3）：selected→full；high 按 fit 判 full/material；其余→style。

    无 --function-hint 时条目无 "fit" 键，视为 >=τ（不启用分档降级，高匹配仍 full）。
    """
    match = result.get("match", "high")
    if match == "selected":
        return "full"
    if match == "high":
        fit = result.get("fit")
        if fit is None or fit >= fit_tau:
            return "full"
        return "material"
    return "style"


def _render_reuse_shortlist(results: list[dict]) -> list[str]:
    """机械聚合复用候选 shortlist（design §3.1）：来源仅三处既有结构化字段——

    手艺拆解 quote 原句锚 / 灵感卡 reuse_candidates[] / 作品文风卡 signature_moves[]。
    不含落点（留给 writer 临场判断）；零 LLM、零新 dispatch。全空 → 返回空列表。
    """
    items: list[str] = []
    seen_style_novels: set[str] = set()
    for r in results:
        novel = r.get("novel", "?")
        scene_id = r.get("scene_id", "?")
        file_path = r.get("file", "")
        sidecar = read_craft_sidecar(file_path)
        if sidecar:
            for p in sidecar.get("patterns", []):
                quote = p.get("quote")
                if quote:
                    items.append(f"- [{novel} {scene_id}·手艺拆解] 「{quote}」")
        for card in lookup_inspiration_cards(novel, scene_id):
            for cand in card.get("reuse_candidates") or []:
                items.append(f"- [{novel} {scene_id}·灵感卡] {cand}")
        if novel not in seen_style_novels:
            seen_style_novels.add(novel)
            style_card = load_novel_annotations(file_path).get("style_card") or {}
            for move in style_card.get("signature_moves") or []:
                items.append(f"- [{novel}·文风卡] {move}")
    return items


def _load_lore(kb_root: Path, novel: str) -> dict | None:
    """装载世界观 lore 包（design §4.2）：phase1_world.yaml 固定键 + phase0_conception.yaml
    的 premise / genre.conventions，全量固定键、无语义裁剪、按来源分组原样嵌入。

    缺 pipeline 文件或解析失败 → 返回 None（调用方按此降级：区块不渲染、头部行不写）。
    """
    novels_dir = kb_root / "novels"
    resolved_novel = novel
    if novels_dir.is_dir():
        resolved_novel = next(
            (
                child.name for child in novels_dir.iterdir()
                if child.is_dir()
                and _normalize_filter_text(child.name) == _normalize_filter_text(novel)
            ),
            novel,
        )
    pipeline_dir = novels_dir / resolved_novel / "pipeline"
    world_path = pipeline_dir / "phase1_world.yaml"
    conception_path = pipeline_dir / "phase0_conception.yaml"
    if not world_path.exists() or not conception_path.exists():
        return None
    try:
        world = yaml.safe_load(world_path.read_text(encoding="utf-8")) or {}
        conception = yaml.safe_load(conception_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(world, dict) or not isinstance(conception, dict):
        return None

    phase1_world = {
        k: world[k] for k in
        ("setting", "world_rules", "genre_conventions", "daily_life", "creative_constraints")
        if k in world
    }
    phase0_conception: dict = {}
    if "premise" in conception:
        phase0_conception["premise"] = conception["premise"]
    genre = conception.get("genre")
    if isinstance(genre, dict) and "conventions" in genre:
        phase0_conception["genre_conventions"] = genre["conventions"]

    lore: dict = {}
    if phase1_world:
        lore["phase1_world"] = phase1_world
    if phase0_conception:
        lore["phase0_conception"] = phase0_conception
    return lore or None


def save_reference_file(results: list[dict], query_text: str,
                        genre: str, output_dir: str, scene_id: str,
                        max_chars: int = 0, style_hint: str = None,
                        fit_tau: float = FIT_TIER_TAU,
                        worldview: str = None,
                        shortform_pack: bool = False,
                        function_hint: str = None,
                        paired_function_bridge: bool = False) -> str:
    """保存检索结果到文件（含原文），返回文件路径"""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = "reference_pack.md" if shortform_pack else (
        f"{scene_id}_ref.md" if scene_id else "query_ref.md"
    )
    out_path = out_dir / filename

    title = "# 短篇名著参考包\n" if shortform_pack else f"# 名著范文参考 — 场景 {scene_id or '(未指定)'}\n"
    lines = [title]
    lines.append(f"query: \"{query_text}\"")
    if genre:
        lines.append(f"genre_filter: {genre}")
    if style_hint:
        lines.append(f"style_hint: {style_hint}（候选已按场景文风标注对齐重排）")
    lines.append(f"results: {len(results)}")
    # 复用指令信号：reuse_tier 三档取全条目最高档写头部；reuse_mandate 由 tier 派生
    # （= tier != style），旧 orchestrator 全等判读该行行为不变。
    # orchestrator 只读文件头判定是否在 writer dispatch prompt 注入复用指令段，不读全文。
    tiers = [_tier_for(r, fit_tau) for r in results]
    header_tier = max(tiers, key=lambda t: _TIER_RANK[t]) if tiers else "style"
    lines.append(f"reuse_mandate: {'true' if header_tier != 'style' else 'false'}")
    lines.append(f"reuse_tier: {header_tier}")
    # worldview 信号独立载体（design §A3）：来源=显式意图，不与 tier 自动计算混用。
    lore = _load_lore(KB_ROOT, worldview) if worldview else None
    if worldview and lore is None:
        print(
            f"⚠️ worldview lore 装载失败（{worldview} 缺 pipeline/phase1_world.yaml 或 "
            "phase0_conception.yaml）——世界观区块跳过，主干流程继续。",
            file=sys.stderr,
        )
    if lore is not None:
        lines.append(f"worldview_reuse: {worldview}")
    lines.append("")

    if not results:
        lines.append("genre 过滤后无场景，跳过参考。")
    else:
        lines.append("<usage_protocol>")
        lines.append("写作前最后读本文件——ref 是文风锚，离生成越近引力越强。读完每条范文原文后：")
        lines.append("1. 只提炼本场真正影响写法的 style anchor；可从叙事语态、句段呼吸、词汇质地、"
                     "对白形态或留白方式中按需选择，不设数量和维度覆盖配额。")
        lines.append("2. 正文以 style anchor 为准绳主动贴近范文的腔调与质感；范文是生成时的直接参考。")
        if header_tier == "full":
            lines.append("3. full 提供结构与句段候选，检索分数或手选不证明功能同构。先核对当前人物、处境与必要结果；明确要求复用时，最大化复用其中实际贴切的原词原句与连续段落，不设字符或段落长度上限。")
        elif header_tier == "material":
            lines.append("3. material 提供局部素材候选：最大化复用当前已采用且直接相关的来源专名、世界事实和专门术语；通用动作、物件、情节和单句须另有功能适配依据。")
        else:
            lines.append("3. 本场只作文风参考：提取语态、节奏、词汇质地、对白形态与留白方式，不迁移范文的情节和动作材料。")
        lines.append("4. 复用段落须做语态归一：剥离范文叙述者的专有腔调（说书人称呼语 / 语气词 / 与本篇冲突的人称与时代语感），"
                     "专名按当前故事设定映射，使段落融入本篇叙述语态——复用的是内容与句子，不是范文的叙述者本人。")
        lines.append("5. 跨语言 reference 可翻译、转写或保留原文，由交付语言决定。")
        lines.append("6. 标注「仅文风参考」的条目不学叙事结构；style anchor 与 scene_card / role_briefs / prose_risk_contract 冲突时设计文档优先。")
        lines.append("</usage_protocol>")
        lines.append("")

        if not shortform_pack:
            rhetoric_cards = select_rhetoric_cards(
                KB_ROOT,
                query_text,
                results,
                limit=3,
            )
            rendered_rhetoric = render_rhetoric_cards(rhetoric_cards)
            if rendered_rhetoric:
                lines.extend(rendered_rhetoric)
                lines.append("")

        # 短篇 composer 已从 outline / inspiration_ledger 接收采纳后的结构决定。
        # reference_pack 只承担世界规则、文风与原文 few-shot，避免把候选菜单和
        # 设计分析重复投进正文生成热路径。普通 Phase 6 scene ref 保持现有输出。
        if not shortform_pack:
            shortlist = _render_reuse_shortlist(results)
            if shortlist:
                lines.append("## 复用候选（脚本聚合——第一优先素材）")
                lines.append("")
                lines.extend(shortlist)
                lines.append("")

        if lore is not None:
            lines.append(f'<worldview_lore novel="{worldview}">')
            lines.append("")
            lines.append("```yaml")
            lines.append(yaml.safe_dump(lore, allow_unicode=True, sort_keys=False).rstrip("\n"))
            lines.append("```")
            lines.append("")
            lines.append("</worldview_lore>")
            lines.append("")

        for r in results:
            match = r.get("match", "high")
            if match == "selected":
                tier_label = "手动指定参考"
                tier_guide = (
                    "手动精选确定来源；按 usage_protocol 核对适配后使用"
                    "人物、设定、情节与原句，并完成语态归一。"
                )
                heading = f"## 手动指定参考: {r.get('novel', '?')} {r['scene_id']}"
            elif match == "high":
                entry_tier = _tier_for(r, fit_tau)
                if entry_tier == "full":
                    tier_label = "叙事+文风参考"
                    tier_guide = ("高匹配——可学其叙事节拍链、冲突推进方式，"
                                  "并按 usage_protocol 贴近文风")
                else:
                    tier_label = "叙事+文风参考（素材级）"
                    tier_guide = ("局部素材候选——当前已采用的相关专名/世界事实/术语可复用，"
                                  "不整段复用；仍按 usage_protocol 贴近文风")
                heading = (
                    f"## 参考 {r['rank']}: {r.get('novel', '?')} {r['scene_id']} "
                    f"(score={r['score']:.4f}, {tier_label})"
                )
            else:
                tier_label = "仅文风参考"
                tier_guide = ("叙事内容与当前场景无直接关联——不学叙事结构，"
                              "只按 usage_protocol 贴近文风")
                heading = (
                    f"## 参考 {r['rank']}: {r.get('novel', '?')} {r['scene_id']} "
                    f"(score={r['score']:.4f}, {tier_label})"
                )

            lines.append(heading)
            lines.append(f"> {tier_guide}")
            lines.append("")
            if r.get("description"):
                lines.append(f"> {r['description']}")
                lines.append("")

            # 注入文风画像（annotate_style_profile.py 离线标注；缺失跳过）
            annotations = load_novel_annotations(r["file"])
            sp = annotations.get("style_profiles", {}).get(r["scene_id"]) or r.get("style_profile")
            if sp:
                lines.append("**文风画像**（离线标注——style anchor 提取的直接锚点）：")
                lines.append("")
                lines.append("```yaml")
                for k in ("narration_voice", "diction", "rhetoric_density",
                          "dialogue_mode", "pacing"):
                    if sp.get(k):
                        lines.append(f"{k}: {sp[k]}")
                lines.append("```")
                lines.append("")

            style_card = annotations.get("style_card") if r.get("rank") == 1 else None
            if style_card:
                lines.append("**作品文风卡**（跨场景蒸馏——本书级 style anchor）：")
                lines.append("")
                lines.append("```yaml")
                for k, v in style_card.items():
                    if k == "style_card_by":
                        continue
                    if isinstance(v, list):
                        lines.append(f"{k}:")
                        for item in v:
                            lines.append(f"  - {item}")
                    elif v is not None:
                        lines.append(f"{k}: {v}")
                lines.append("```")
                lines.append("")

            if not shortform_pack:
                sidecar = read_craft_sidecar(r["file"])
                if sidecar:
                    lines.append("**手艺拆解**（结构化——pattern_id 可被审阅锚点引用）：")
                    lines.append("")
                    lines.append("| id | 节拍 | 原作怎么做 | AI 默认怎么写坏 | 迁移规则 | 原句锚 |")
                    lines.append("|---|---|---|---|---|---|")
                    for p in sidecar.get("patterns", []):
                        lines.append(
                            f"| {p.get('pattern_id', '?')} | {p.get('beat', '')} "
                            f"| {p.get('original_move', '')} | {p.get('ai_default_failure', '')} "
                            f"| {p.get('transfer_rule', '')} | {p.get('quote', '')} |"
                        )
                    traits = sidecar.get("overall_traits") or []
                    if traits:
                        lines.append("")
                        lines.append("整体手艺特征：" + "；".join(traits))
                    organization = sidecar.get("narrative_organization") or {}
                    if organization:
                        lines.append("")
                        lines.append("叙事组织：")
                        for key, value in organization.items():
                            if value:
                                lines.append(f"- {key}: {value}")
                    lines.append("")
                elif craft := read_craft_notes(r["file"]):
                    lines.append('<craft_notes note="同一范文的节拍级手艺拆解">')
                    lines.append(craft)
                    lines.append("</craft_notes>")
                    lines.append("")

                inspiration_cards = lookup_inspiration_cards(r.get("novel", ""), r["scene_id"])
                if inspiration_cards:
                    lines.append("**灵感卡**（本场是范式佐证）：")
                    lines.append("")
                    for card in inspiration_cards:
                        lines.append(
                            f"- **灵感卡·{card.get('pattern_name', card.get('card_id', '?'))}**"
                            f"（本场是该范式的佐证场景）：{card.get('dramatic_function', '')}"
                        )
                        reuse = card.get("reuse_candidates") or []
                        if reuse:
                            lines.append(f"  可直接复用的表层元素：{'；'.join(map(str, reuse))}")
                    lines.append("")

            # 注入段落密度观测（基于未截断的完整原文计算）
            full_scene_path = KB_ROOT / r["file"]
            density = _pd_analyze_file(full_scene_path)
            if density is not None:
                # KB 物理分段异常（如整章一段）会产出不可执行的病态目标，降级跳过
                if density.mean > 12 or density.n_paras < 5:
                    lines.append("**段落密度观测**：KB 分段异常（疑似物理分段缺失），"
                                 "本条密度数据不可作写作目标，跳过对齐。")
                    lines.append("")
                else:
                    # 范文源路径只在密度健康时输出——病态分段的范文跑 --compare 会产假性
                    # SIGNIFICANT_DEVIATION，orchestrator 以本行存在性决定是否跑对齐校验
                    lines.append(f"ref_source_file: {KB_ROOT / r['file']}")
                    lines.append("")
                    lines.append("**段落密度观测**（脚本自动计算——只供偏差诊断，不是写作配额）：")
                    lines.append("")
                    lines.append("```yaml")
                    lines.append(f"n_paras: {density.n_paras}")
                    lines.append(f"total_sentences: {density.total_sentences}")
                    lines.append(f"mean: {density.mean}")
                    lines.append(f"stdev: {density.stdev}")
                    lines.append(f"max_len: {density.max_len}")
                    lines.append(f"short_pct: {density.short_pct}   # ≤2 句段落占比")
                    lines.append(f"medium_pct: {density.medium_pct}  # 3-5 句")
                    lines.append(f"long_pct: {density.long_pct}    # ≥6 句")
                    lines.append(f"vlong_pct: {density.vlong_pct}   # ≥10 句")
                    lines.append("```")
                    lines.append("")

            # 量化文风诊断：指代策略 + 标点经济密度（仅 rank 1，即时计算不落库）
            if r.get("rank") == 1:
                stylo = _sm_analyze_file(full_scene_path)
                if stylo is not None:
                    lines.append("**量化文风诊断**（脚本自动计算——指代 / 标点表面信号，per-1k-chars；数值偏离不自动要求改写）：")
                    lines.append("")
                    lines.append("```yaml")
                    lines.append(f"dash_per_1k: {stylo.dash_per_1k}")
                    lines.append(f"colon_per_1k: {stylo.colon_per_1k}")
                    lines.append(f"semicolon_per_1k: {stylo.semicolon_per_1k}")
                    lines.append(f"ta_per_1k: {stylo.ta_per_1k}   # \"它\"")
                    lines.append(f"dem_classifier_per_1k: {stylo.dem_classifier_per_1k}  # 这/那+量词 限定式")
                    lines.append(f"pro_drop_ratio: {stylo.pro_drop_ratio}  # 句首无主语句占比（启发式）")
                    lines.append(f"top_noun_repetition_per_1k: {stylo.top_noun_repetition_per_1k}")
                    lines.append("```")
                    lines.append("")

            if paired_function_bridge and function_hint and r.get("description"):
                entry_tier = _tier_for(r, fit_tau)
                if entry_tier == "full":
                    bridge_boundary = (
                        "候选进入 full 范围；核对原文怎样改变危险、选择、关系或读者判断及当前条件，"
                        "并按 full 档复用契约接入当前故事。"
                    )
                elif entry_tier == "material":
                    bridge_boundary = (
                        "候选仅提示局部关联；按 material 档核对已采用的来源材料，不据分数迁移通用动作与情节。"
                    )
                else:
                    bridge_boundary = (
                        "本条仅按表达候选处理，声腔也需适配当前叙述；不据检索结果迁移源作结构、人物或事实。"
                    )
                target_function = " ".join(str(function_hint).split())
                source_function = " ".join(str(r["description"]).split())
                lines.append(
                    f'<function_bridge experimental="true" tier="{entry_tier}">'
                )
                lines.append(f"目标场景职责：{target_function}")
                lines.append(f"源场景职责线索：{source_function}")
                lines.append(f"迁移边界：{bridge_boundary}")
                lines.append("</function_bridge>")
                lines.append("")

            text = read_scene_text(r["file"], max_chars=max_chars)
            lines.append(f'<style_exemplar rank="{r["rank"]}" novel="{r.get("novel", "?")}" '
                         f'scene="{r["scene_id"]}" tier="{tier_label}">')
            lines.append(text)
            lines.append("</style_exemplar>")
            lines.append("")

    out_path.write_text('\n'.join(lines), encoding="utf-8")
    return str(out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="知识库场景检索")
    parser.add_argument("--query", type=str, required=False,
                        help="检索 query（场景描述关键词）")
    parser.add_argument("--genre", type=str, default=None,
                        help="按题材过滤（如：现实主义、武侠、科幻）")
    parser.add_argument("--lang", type=str, default=None,
                        help="按语言过滤（zh / en）")
    parser.add_argument("--novel", type=str, default=None,
                        help="按小说名过滤，子串匹配（如：三体、挪威的森林）")
    parser.add_argument("--source-medium", type=str, default="novel",
                        help="按 medium 过滤（防 medium 污染）。默认 'novel' —— "
                             "主干写小说时只检索小说场景，自动排除戏剧 / 剧本。"
                             "可选 'all' / 单值 'stage_play' / 'screenplay' / 等 / "
                             "逗号多值 'novel,stage_play'。"
                             "剧本按实际媒介选择参考池。")
    parser.add_argument("--top_k", type=int, default=2,
                        help="返回前 K 个结果 (默认: 2)")
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="匹配分层阈值：>=阈值标记为 high（叙事+文风），"
                             "<阈值标记为 style_only（仅文风）(默认: 0)")
    parser.add_argument("--model", type=str, default=EMBEDDING_MODEL,
                        help=f"Embedding 模型 (默认: {EMBEDDING_MODEL})")
    parser.add_argument("--include-text", action="store_true",
                        help="在终端输出中包含场景原文（不保存文件时使用）")
    parser.add_argument("--max-chars", type=int, default=4000,
                        help="每个场景原文的最大字符数，0=不截断 (默认: 4000)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="保存检索结果（含原文）到指定目录")
    parser.add_argument("--scene-id", type=str, default=None,
                        help="当前场景 ID，用于命名输出文件（如 S01）")
    parser.add_argument("--shortform-pack", action="store_true",
                        help="复用同一渲染器输出 reference_pack.md，供短链 composer 最后读取")
    parser.add_argument("--select", type=str, default=None,
                        help="手动指定参考，格式 '<novel>:<scene_id>,...'；跳过检索")
    parser.add_argument("--list", action="store_true",
                        help="只打印候选表，不写 ref 文件")
    parser.add_argument("--pool", type=int, default=None,
                        help="候选池大小；配合 --list 可控制候选表行数")
    parser.add_argument("--style-hint", type=str, default=None,
                        help="语态对齐提示（短语，如「限知内聚 心理戏 对白稀少」）——"
                             "按场景文风标注重排候选，纯文本匹配不发额外 API")
    parser.add_argument("--style-mode", choices=("vector", "bigram"), default=STYLE_MODE_DEFAULT,
                        help=f"语态对齐实现：vector 使用 style 向量通道，bigram 使用旧文本重排 (默认: {STYLE_MODE_DEFAULT})")
    parser.add_argument("--function-hint", type=str, default=None,
                        help="功能同构提示词（场景型/冲突型/节拍功能词，如「战前蓄势 守阵 群体调度」）——"
                             "决定 reuse_tier 分档，不进 rank_score")
    parser.add_argument("--paired-function-bridge", action="store_true",
                        help="实验性 A/B：在同一范文前显式配对目标/源场景职责；需同时传 --function-hint，默认关闭")
    parser.add_argument("--fit-tau", type=float, default=FIT_TIER_TAU,
                        help=f"功能同构分档阈值 (默认: {FIT_TIER_TAU})")
    parser.add_argument("--worldview", type=str, default=None,
                        help="显式复用某作品世界观：装载其 phase1_world.yaml + phase0_conception.yaml "
                             "lore 包进 ref（<worldview_lore> 区块 + worldview_reuse 头部行）；"
                             "缺 pipeline 文件时降级为不渲染，不阻断")
    parser.add_argument("--hybrid", dest="hybrid", action="store_true",
                        help="启用 BM25 + RRF 召回融合")
    parser.add_argument("--no-hybrid", dest="hybrid", action="store_false",
                        help="关闭 BM25 + RRF 召回融合")
    parser.set_defaults(hybrid=True)
    parser.add_argument("--mmr-lambda", type=float, default=0.0,
                        help="MMR 多样性截选权重，0 表示关闭 (默认: 0)")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 格式输出（而非人类可读格式）")
    args = parser.parse_args()

    if args.paired_function_bridge and not args.function_hint:
        parser.error("--paired-function-bridge requires --function-hint")

    try:
        if args.select:
            results = select_results(args.select, source_medium=args.source_medium)
            if not results:
                sys.exit(2)
        else:
            if not args.query:
                parser.error("--query is required unless --select is used")
            results = query(
                query_text=args.query,
                genre=args.genre,
                lang=args.lang,
                novel=args.novel,
                source_medium=args.source_medium,
                top_k=args.pool if args.list and args.pool is not None else args.top_k,
                threshold=args.threshold,
                style_hint=args.style_hint,
                style_mode=args.style_mode,
                function_hint=args.function_hint,
                hybrid=args.hybrid,
                mmr_lambda=args.mmr_lambda,
                pool=args.pool,
                model=args.model,
            )
    except KBConfigError as e:
        # 配置缺失：明确分类，不写假的 ref.md 让上游误以为"无匹配"
        print(f"❌ [kb_query CONFIG_ERROR] {e}", file=sys.stderr)
        sys.exit(2)
    except KBInfraError as e:
        # 基础设施故障：API key 无效 / 网络挂 / 上游服务挂
        # 同样 exit 2 触发 orchestrator graceful skip，但 stderr 分类不同便于排查
        print(f"❌ [kb_query INFRA_ERROR] {e}", file=sys.stderr)
        sys.exit(2)

    if args.list:
        if args.output_dir:
            print("❌ --list 与 --output-dir 互斥", file=sys.stderr)
            sys.exit(2)
        print(format_candidate_table(results))
    elif args.output_dir:
        out_path = save_reference_file(
            results, args.query or "", args.genre,
            args.output_dir, args.scene_id,
            max_chars=args.max_chars, style_hint=args.style_hint,
            fit_tau=args.fit_tau, worldview=args.worldview,
            shortform_pack=args.shortform_pack,
            function_hint=args.function_hint,
            paired_function_bridge=args.paired_function_bridge,
        )
        abs_out = str(Path(out_path).resolve())
        # 输出明确的读取指令——模型应读此文件，不要去读原场景文件
        if results:
            high = sum(1 for r in results if r.get("match") in {"high", "selected"})
            style = len(results) - high
            parts = []
            if high:
                parts.append(f"{high} 个叙事+文风参考")
            if style:
                parts.append(f"{style} 个文风参考")
            print(f"✅ 已保存 {', '.join(parts)}（含原文）。")
            print(f"📖 请读取此文件作为写作参考: {abs_out}")
        else:
            print(f"⚠️ genre 过滤后无场景，跳过参考。")
    elif args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_results(results, include_text=args.include_text,
                              max_chars=args.max_chars))


if __name__ == "__main__":
    main()
