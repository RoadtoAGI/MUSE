"""Step 5 lint 脚本测试共享 fixture。"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import pytest


@pytest.fixture
def clean_draft():
    """无 AI 口癖 / 无排比模板 / 无 Markdown 结构的干净样本。"""
    return (Path(__file__).parent / "fixtures/sample_clean.md").read_text(encoding="utf-8")


@pytest.fixture
def polluted_draft():
    """含多种模式命中的污染样本。"""
    return (Path(__file__).parent / "fixtures/sample_polluted.md").read_text(encoding="utf-8")


@pytest.fixture
def tmp_work_dir(tmp_path):
    """临时 work_dir，含 pipeline/scenes/ 目录。"""
    scenes = tmp_path / "pipeline" / "scenes"
    scenes.mkdir(parents=True)
    return tmp_path
