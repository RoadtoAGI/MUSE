"""Information survives annotation, indexing, retrieval and original-text delivery."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
import yaml

bic = importlib.import_module('skills.MUSE-canon-distill.knowledge-base.scripts.build_inspiration_cards')
iq = importlib.import_module('skills.MUSE-canon-distill.knowledge-base.scripts.inspiration_query')


@pytest.fixture
def kb(tmp_path, monkeypatch):
    root = tmp_path / 'kb'
    for work in ('作品甲', '作品乙'):
        folder = root / 'novels' / work
        (folder / 'scenes').mkdir(parents=True)
        (folder / 'scenes/source.md').write_text('场景开头\n前置条件\n关键行动\n后续结果\n', encoding='utf-8')
        (folder / 'scene_index.json').write_text(json.dumps([
            {'scene_id': 'S01', 'file': 'scenes/source.md', 'description': '完整来源'}
        ], ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(bic, 'KB_ROOT', root)
    monkeypatch.setattr(bic, 'INSPIRATION_DIR', root / 'inspiration')
    monkeypatch.setattr(iq, 'KB_ROOT', root)
    return root


def analysis(work='作品甲', reason='保存完整记录却失去相互理解'):
    return dict(novel=work, creative_move='把保存与理解分开', narrative_reason=reason,
                transfer_conditions='关系需要对方回应，完整记录不能替代回应', source_scene_ids=['S01'])


def card():
    return dict(card_id='archive-and-response', pattern_name='记录与回应',
                dramatic_function='呈现认识变化', applicability='信息保存题材',
                reuse_candidates=['档案'], tags=['记忆'], phase_affinity=[0, 3],
                mechanism='记录的完整性与关系的相互性具有不同条件',
                source_analyses=[analysis()],
                source_scenes=[dict(novel='作品甲', scene_id='S01', note='条件到结果',
                                    line_start=2, line_end=4)])


def test_prepare_ingest_cluster_query_reading_roundtrip(kb, tmp_path):
    tasks = tmp_path / 'tasks'
    assert bic.prepare_nominate('作品甲', False, str(tasks)) == 0
    task = json.loads((tasks / '作品甲.task.json').read_text())
    assert Path(task['source_root']).samefile(kb / 'novels/作品甲')
    assert task['output_contract']['nominations'][0]['source_analyses']
    candidate = card()
    nomination = {key: candidate[key] for key in bic.NOMINATION_FIELDS if key != 'evidence_scenes'}
    nomination.update(mechanism=candidate['mechanism'], source_analyses=candidate['source_analyses'],
                      phase_affinity=[0, 3], evidence_scenes=[
                          {key: value for key, value in candidate['source_scenes'][0].items() if key != 'novel'}])
    output = tmp_path / 'nomination.json'
    output.write_text(json.dumps({'novel': '作品甲', 'nominations': [nomination]}, ensure_ascii=False))
    assert bic.ingest_nominate(str(output)) == 0
    cluster_task = tmp_path / 'cluster.task.json'
    assert bic.prepare_cluster(str(cluster_task)) == 0
    clustered_input = json.loads(cluster_task.read_text())['nominations'][0]
    assert clustered_input['source_analyses'] == candidate['source_analyses']
    assert clustered_input['evidence_scenes'][0]['line_start'] == 2
    output.write_text(json.dumps({'cards': [candidate]}, ensure_ascii=False))
    assert bic.ingest_cluster(str(output), replace=False) == 0
    saved = yaml.safe_load((kb / 'inspiration/archive-and-response.yaml').read_text())
    assert saved == candidate
    refs = tmp_path / 'run/references'
    assert iq.run(0, json.dumps({'narrative_problem': '相互理解'}, ensure_ascii=False), str(refs)) == 0
    rendered = (refs / 'inspiration/phase0_cards.md').read_text()
    assert candidate['source_analyses'][0]['narrative_reason'] in rendered
    assert candidate['source_analyses'][0]['transfer_conditions'] in rendered
    assert iq.read_card(candidate['card_id'], str(refs)) == 0
    reading = (refs / 'inspiration/archive-and-response_reading.md').read_text()
    assert '2: 前置条件\n3: 关键行动\n4: 后续结果' in reading
    assert '场景开头' not in reading
    assert str(kb / 'novels/作品甲/scenes/source.md') in reading


def test_different_source_conditions_survive(kb):
    value = card()
    value['source_scenes'].append(dict(novel='作品乙', scene_id='S01', note='相邻机制'))
    value['source_analyses'].append(analysis('作品乙', '记录缺失给对方留下解释空间'))
    clean = bic.validate_card(value, bic.load_idx_map())
    rendered = iq.render_cards(0, [clean], [])
    assert all(a['narrative_reason'] in rendered for a in value['source_analyses'])


@pytest.mark.parametrize('change', ['ghost-source', 'wrong-work', 'author-without-source', 'reverse-lines'])
def test_enrichment_rejects_broken_source_contract(kb, change):
    value = card()
    if change == 'ghost-source': value['source_analyses'][0]['source_scene_ids'] = ['S99']
    elif change == 'wrong-work': value['source_analyses'][0]['novel'] = '作品乙'
    elif change == 'author-without-source': value['source_analyses'][0]['author_motivation'] = {'claim': '作者的意图'}
    else: value['source_scenes'][0]['line_end'] = 1
    with pytest.raises(ValueError): bic.validate_card(value, bic.load_idx_map())


def test_old_card_still_reads_full_source(kb, tmp_path):
    value = card()
    del value['mechanism'], value['source_analyses']
    del value['source_scenes'][0]['line_start'], value['source_scenes'][0]['line_end']
    bic.write_card(kb / 'inspiration', bic.validate_card(value, bic.load_idx_map()))
    assert iq.read_card(value['card_id'], str(tmp_path)) == 0
    assert '1: 场景开头' in (tmp_path / 'inspiration/archive-and-response_reading.md').read_text()


def test_explicit_source_selection_and_failed_reread_clear_stale_output(kb, tmp_path):
    value = card()
    value['source_scenes'].append(dict(novel='作品乙', scene_id='S01', note='别的条件'))
    bic.write_card(kb / 'inspiration', bic.validate_card(value, bic.load_idx_map()))
    assert iq.read_card(value['card_id'], str(tmp_path), ['作品乙:S01']) == 0
    output = tmp_path / 'inspiration/archive-and-response_reading.md'
    assert '作品甲:S01' not in output.read_text()
    (kb / 'novels/作品乙/scenes/source.md').unlink()
    assert iq.read_card(value['card_id'], str(tmp_path), ['作品乙:S01']) == 2
    assert not output.exists()


def test_reading_out_of_bounds_is_not_silently_truncated(kb, tmp_path):
    value = card()
    value['source_scenes'][0]['line_end'] = 900
    bic.write_card(kb / 'inspiration', value)
    assert iq.read_card(value['card_id'], str(tmp_path)) == 2
    assert not (tmp_path / 'inspiration/archive-and-response_reading.md').exists()


def test_failed_query_does_not_leave_last_selection(kb, tmp_path):
    bic.write_card(kb / 'inspiration', card())
    assert iq.run(0, '{}', str(tmp_path)) == 0
    assert iq.run(0, '{broken', str(tmp_path)) == 2
    assert not (tmp_path / 'inspiration/phase0_cards.md').exists()
