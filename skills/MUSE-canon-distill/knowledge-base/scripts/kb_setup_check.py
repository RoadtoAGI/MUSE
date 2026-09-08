#!/usr/bin/env python3
"""kb_setup_check.py — 一键诊断 scene-reference 链路是否配置好。

检查项：
  1. python 依赖（openai / numpy / python-dotenv）是否就绪
  2. KB 资产是否就位（scene_index.json + scene_embeddings.npy）
  3. API 配置环境变量是否设值（MUSE_KB_API_KEY）
  4. 实际跑一次 1-token embedding 调用，验证 API key + base URL 真能通

用法：
    python3 ${CLAUDE_PLUGIN_ROOT}/knowledge-base/scripts/kb_setup_check.py

退出码：
    0  全 pass
    2  任一项 fail（stderr 报具体问题与修复指引）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


KB_ROOT = Path(__file__).resolve().parent.parent  # knowledge-base/
PLUGIN_ROOT = KB_ROOT.parent
INDEX_PATH = KB_ROOT / "embeddings" / "scene_index.json"
EMBEDDINGS_PATH = KB_ROOT / "embeddings" / "scene_embeddings.npy"
ENV_EXAMPLE = PLUGIN_ROOT / ".env.example"


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _fail(msg: str, fix: str = "") -> None:
    print(f"  ❌ {msg}", file=sys.stderr)
    if fix:
        for line in fix.split("\n"):
            print(f"     → {line}", file=sys.stderr)


def check_python_deps() -> bool:
    print("[1/4] Python 依赖")
    missing = []
    for mod in ("openai", "numpy", "dotenv"):
        try:
            __import__(mod)
            _ok(f"{mod} 已安装")
        except ImportError:
            missing.append(mod)
            _fail(
                f"{mod} 未安装",
                f"pip install {'openai' if mod=='openai' else 'numpy' if mod=='numpy' else 'python-dotenv'}",
            )
    return not missing


def check_kb_assets() -> bool:
    print("\n[2/4] 知识库资产")
    ok = True
    if not INDEX_PATH.exists():
        _fail(
            f"scene_index.json 不存在 ({INDEX_PATH})",
            "把名著语料放到 knowledge-base/novels/<书名>/ 后跑 extract_scene.py 生成索引",
        )
        ok = False
    else:
        import json
        idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        n = len(idx) if isinstance(idx, list) else len(idx.get("scenes", []))
        _ok(f"scene_index.json 存在（{n} 个场景）")
    if not EMBEDDINGS_PATH.exists():
        _fail(
            f"scene_embeddings.npy 不存在 ({EMBEDDINGS_PATH})",
            "embedding 文件缺失——跑 extract_scene.py 重新生成",
        )
        ok = False
    else:
        _ok(f"scene_embeddings.npy 存在（{EMBEDDINGS_PATH.stat().st_size // 1024} KB）")
    return ok


def check_env_config() -> tuple[bool, str, str]:
    print("\n[3/4] API 配置环境变量")
    # 加载 .env（如果存在）
    try:
        from dotenv import load_dotenv
        env_path = PLUGIN_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            _ok(f"{env_path} 已加载")
    except ImportError:
        pass  # check_python_deps 已经报过

    api_key = os.getenv("MUSE_KB_API_KEY") or ""
    base_url = (
        os.getenv("MUSE_KB_BASE_URL")
        or os.getenv("API_BASE_URL")
        or "https://your-compatible-endpoint.example/v1"
    )

    if not api_key:
        fix_lines = [
            "方式 A — shell 临时 export：",
            "  export MUSE_KB_API_KEY='sk-...'",
            "方式 B — 持久化（推荐）：写进 ~/.bashrc 或 ~/.zshrc",
            "方式 C — .env 文件：",
            f"  cp {ENV_EXAMPLE} {PLUGIN_ROOT}/.env 然后填值",
        ]
        _fail(
            "MUSE_KB_API_KEY 未设置",
            "\n".join(fix_lines),
        )
        return False, "", base_url

    _ok(f"API key 已设置（来源：MUSE_KB_API_KEY，长度 {len(api_key)}）")
    _ok(f"base URL: {base_url}")
    return True, api_key, base_url


def check_api_connectivity(api_key: str, base_url: str) -> bool:
    print("\n[4/4] API 真实连通性（1 token embedding 调用）")
    try:
        from openai import OpenAI
    except ImportError:
        _fail("openai 未安装，跳过连通性测试")
        return False

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=["ping"],
        )
        dim = len(resp.data[0].embedding)
        _ok(f"embedding 调用成功（dim={dim}）")
        return True
    except Exception as e:
        msg = str(e)
        fix_lines = []
        if "401" in msg or "No token" in msg or "unauthorized" in msg.lower():
            fix_lines.append("API key 无效或已过期——重新到供应商控制台获取")
        elif "404" in msg or "not found" in msg.lower():
            fix_lines.append(
                f"base URL {base_url} 可能错——确认供应商 endpoint 路径"
            )
        elif "timeout" in msg.lower() or "connect" in msg.lower():
            fix_lines.append("网络不通——检查代理 / 防火墙")
        else:
            fix_lines.append("未知错误，看完整异常信息排查")
        _fail(f"API 调用失败：{msg[:200]}", "\n".join(fix_lines))
        return False


def main() -> int:
    print(f"MUSE-canon-distill setup check — plugin root: {PLUGIN_ROOT}\n")
    ok1 = check_python_deps()
    ok2 = check_kb_assets()
    ok3, api_key, base_url = check_env_config()
    ok4 = check_api_connectivity(api_key, base_url) if ok3 else False

    print("\n=== 总结 ===")
    print(f"  依赖     : {'✅' if ok1 else '❌'}")
    print(f"  KB 资产  : {'✅' if ok2 else '❌'}")
    print(f"  API 配置 : {'✅' if ok3 else '❌'}")
    print(f"  连通性   : {'✅' if ok4 else '❌'}")

    if ok1 and ok2 and ok3 and ok4:
        print("\n✅ scene-reference 链路就绪")
        return 0
    print("\n❌ 至少一项 fail，按上面 → 指引修复", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
