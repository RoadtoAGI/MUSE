"""Workbench defaults are creation snapshots, never query-time inheritance."""
import importlib.util
from pathlib import Path
import os
import subprocess
import sys

import pytest
from muse_runtime.bootstrap import initialize_new_work
from muse_runtime.config import resolve_settings, set_mode, RuntimeConfigError

ROOT = Path(__file__).resolve().parents[2]


def test_template_is_snapshot_and_preserves_work_override(tmp_path, monkeypatch):
    defaults = tmp_path / 'defaults'
    defaults.mkdir()
    set_mode(defaults, 'jev')
    monkeypatch.setenv('MUSE_NEW_WORK_TEMPLATE', str(defaults / '.muse/runtime.yaml'))
    work = tmp_path / 'work'
    work.mkdir()
    # Setting a creation template never changes a query's resolution.
    assert resolve_settings(work).mode == 'standard'
    initialize_new_work(work)
    assert resolve_settings(work).mode == 'jev'
    set_mode(defaults, 'standard')
    assert resolve_settings(work).mode == 'jev'
    set_mode(work, 'standard')
    initialize_new_work(work)
    assert resolve_settings(work).mode == 'standard'


@pytest.mark.parametrize('script', ['init_run.py', 'init_short_run.py'])
def test_initializer_enables_new_work_but_preserves_existing(tmp_path, monkeypatch, script):
    defaults = tmp_path / 'defaults'
    defaults.mkdir()
    set_mode(defaults, 'jev')
    monkeypatch.setenv('MUSE_NEW_WORK_TEMPLATE', str(defaults / '.muse/runtime.yaml'))
    path = ROOT / 'skills/MUSE-writing/scripts' / script
    spec = importlib.util.spec_from_file_location(script[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = tmp_path / 'existing'
    old.mkdir()
    module.init_run_explicit(old)
    assert resolve_settings(old).mode == 'standard'
    new = tmp_path / 'new'
    module.init_run_explicit(new)
    assert resolve_settings(new).mode == 'jev'
    set_mode(new, 'standard')
    module.init_run_explicit(new)
    assert resolve_settings(new).mode == 'standard'


def test_no_template_keeps_standard_without_new_config(tmp_path, monkeypatch):
    monkeypatch.delenv('MUSE_NEW_WORK_TEMPLATE', raising=False)
    initialize_new_work(tmp_path)
    assert not (tmp_path / '.muse/runtime.yaml').exists()


def test_bad_template_is_visible(tmp_path, monkeypatch):
    monkeypatch.setenv('MUSE_NEW_WORK_TEMPLATE', 'relative.yaml')
    with pytest.raises(RuntimeConfigError, match='绝对路径'):
        initialize_new_work(tmp_path)


def test_serial_series_and_new_chapter_receive_default(tmp_path, monkeypatch):
    import yaml
    defaults = tmp_path / 'defaults'
    defaults.mkdir()
    set_mode(defaults, 'jev')
    monkeypatch.setenv('MUSE_NEW_WORK_TEMPLATE', str(defaults / '.muse/runtime.yaml'))
    scripts = ROOT / 'skills/MUSE-serial-writing/scripts'
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    result = subprocess.run([sys.executable, str(scripts / 'init_series.py'),
                             '--slug', 'new-serial', '--works-root', str(tmp_path / 'works')],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    series = Path(result.stdout.strip())
    assert resolve_settings(series).mode == 'jev'
    volume = series / 'series/volumes/V01.yaml'
    volume.parent.mkdir(parents=True, exist_ok=True)
    volume.write_text(yaml.safe_dump({'volume_id': 'V01', 'chapters': [
        {'chapter_id': 'C0001', 'status': 'outline'}]}))
    spec = importlib.util.spec_from_file_location('materialize_for_bootstrap', scripts / 'materialize_chapter.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Context assembly has a separate contract; this test covers directory ownership.
    monkeypatch.setattr(module, 'run_subprocess', lambda *args: None)
    chapter = module.run(series, 'V01', 'C0001', scripts)
    assert resolve_settings(chapter).mode == 'jev'
    (chapter / '.muse/runtime.yaml').unlink()
    module.run(series, 'V01', 'C0001', scripts)
    assert resolve_settings(chapter).mode == 'standard'
