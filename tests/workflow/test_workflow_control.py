"""Exercise shipped workflow controls, not a test-only transition oracle."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from test_artifact_contracts import minimal_payloads

SCRIPT = Path(__file__).parents[2] / 'skills/problem-navigator/scripts/workflow_control.py'


@pytest.fixture
def control():
    assert SCRIPT.exists(), 'The shipped workflow control is missing'
    spec = importlib.util.spec_from_file_location('workflow_control', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    base = minimal_payloads()
    frame = {**base['problem_frame'], 'analysis_goal': 'UNDERSTAND', 'content_profile': 'GENERAL', 'delivery_endpoint': 'RESEARCH_REPORT'}
    brief = copy.deepcopy(base['research_brief'])
    task = brief['tasks'][0]
    task['material_refs'] = ['material.md']
    web = {'task_id': 'RES-002', 'theme_id': 'THEME-002', 'question': 'Public counterpart?', 'task_kind': 'PUBLIC_WEB', 'direction': 'auto', 'domains': [], 'freshness': '', 'quality_bar': 'Primary evidence', 'stop_condition': 'Supported answer'}
    brief['tasks'].append(web)
    workflow = {**base['workflow'], 'analysis_goal': 'UNDERSTAND', 'selected_backend': 'RESEARCH_CORE', 'next_stage': 'research-execution', 'artifact_refs': {'problem_frame': 'frame.yaml', 'research_brief': 'brief.yaml'}, 'call_counts': {t['task_id']: {'search': 0, 'fetch': 0, 'map': 0} for t in brief['tasks']}}
    return workflow, frame, brief


def completed(control):
    workflow, frame, brief = inputs()
    workflow, draft = control.initialize_draft(workflow, frame, brief)
    draft['unfinished_task_ids'] = []
    draft['external_sources'] = [{'external_source_id': 'EXT-1', 'task_id': 'RES-001', 'kind': 'document', 'producer': 'user', 'artifact_ref': 'material.md', 'limitations': []}]
    draft['sources'] = [{'source_id': 'SRC-2', 'call_ref': 'call-2', 'title': 'Official page', 'normalized_url': 'https://example.com/doc', 'provider': 'brave', 'source_type': 'web', 'retrieved_at': '2026-09-08T00:00:00Z'}]
    draft['completed_receipts'] = [
        {'task_id': 'RES-001', 'outcome': 'WITH_RESULTS', 'quality_met': True, 'call_refs': [], 'source_ids': [], 'external_source_ids': ['EXT-1']},
        {'task_id': 'RES-002', 'outcome': 'WITH_RESULTS', 'quality_met': True, 'call_refs': ['call-2'], 'source_ids': ['SRC-2'], 'external_source_ids': []},
    ]
    draft['evidence_items'] = [
        {'evidence_item_id': 'E-1', 'task_id': 'RES-001', 'kind': 'FACT', 'statement': 'Local fact', 'web_source_ids': [], 'external_source_ids': ['EXT-1']},
        {'evidence_item_id': 'E-2', 'task_id': 'RES-002', 'kind': 'FACT', 'statement': 'Web fact', 'web_source_ids': ['SRC-2'], 'external_source_ids': []},
    ]
    package = {k: v for k, v in draft.items() if k not in ('unfinished_task_ids', 'completed_receipts', 'base_evidence_revision')}
    package.update(analysis_goal='UNDERSTAND', evidence_revision=1, research_state='RESEARCH_COMPLETE', neutral_synthesis='Two supported facts', execution_receipts=draft['completed_receipts'])
    workflow['call_counts']['RES-002']['search'] = 2
    workflow.update(next_stage='DONE', research_state='RESEARCH_COMPLETE')
    workflow['artifact_refs'].pop('evidence_draft')
    workflow['artifact_refs']['evidence_package'] = 'package.yaml'
    return workflow, frame, brief, package


def test_initial_mixed_draft_is_schema_valid_and_does_not_mutate_inputs(control):
    w, f, b = inputs()
    original = copy.deepcopy(w)
    updated, draft = control.initialize_draft(w, f, b)
    assert w == original
    assert updated['research_state'] == 'RESEARCH_IN_PROGRESS'
    assert draft['unfinished_task_ids'] == ['RES-001', 'RES-002']
    assert draft['completed_receipts'] == []
    control.validate('workflow', updated)
    control.validate('evidence_draft', draft)


def test_none_cannot_initialize_public_task(control):
    w, f, b = inputs()
    w['selected_backend'] = 'NONE'
    with pytest.raises(ValueError, match='OFFLINE'):
        control.initialize_draft(w, f, b)


def test_initialization_cannot_erase_interrupted_history(control):
    w, f, b = inputs()
    w['call_counts']['RES-002']['search'] = 1
    with pytest.raises(ValueError, match='INITIALIZATION'):
        control.initialize_draft(w, f, b)


def test_understand_correction_preserves_counts_and_unaffected_material(control):
    w, f, b, p = completed(control)
    original = copy.deepcopy((w, p))
    updated, draft = control.reopen_research(w, f, b, p, ['RES-002'], 'Wrong company identity')
    assert (w, p) == original
    assert updated['next_stage'] == 'research-execution'
    assert updated['call_counts'] == w['call_counts']
    assert 'evidence_package' not in updated['artifact_refs']
    assert draft['unfinished_task_ids'] == ['RES-002']
    assert draft['sources'] == []
    assert draft['external_sources'] == p['external_sources']
    assert [e['evidence_item_id'] for e in draft['evidence_items']] == ['E-1']
    assert draft['base_evidence_revision'] == 1


def test_correction_rejects_unknown_task_and_source_laundering(control):
    w, f, b, p = completed(control)
    with pytest.raises(ValueError, match='TASK'):
        control.reopen_research(w, f, b, p, ['RES-999'], 'Correct identity')
    p['evidence_items'][0]['web_source_ids'] = ['SRC-2']
    with pytest.raises(ValueError, match='SOURCE'):
        control.reopen_research(w, f, b, p, ['RES-002'], 'Correct identity')


def test_new_questions_keep_old_counts_and_can_follow_later_revision(control):
    w, f, b, p = completed(control)
    b['revision'] = p['brief_revision'] = 3
    extra = {**b['tasks'][1], 'task_id': 'RES-003', 'question': 'Another relevant question'}
    updated, revised, draft = control.extend_brief(w, f, b, p, [extra], 'Remaining evidence gap')
    assert revised['revision'] == 4
    assert revised['tasks'][:2] == b['tasks']
    assert updated['call_counts']['RES-002']['search'] == 2
    assert updated['call_counts']['RES-003'] == {'search': 0, 'fetch': 0, 'map': 0}
    assert draft['unfinished_task_ids'] == ['RES-003']
    assert draft['completed_receipts'] == p['execution_receipts']


def test_append_validates_optional_readiness_carrier(control):
    w, f, b, p = completed(control)
    w['analysis_goal'] = f['analysis_goal'] = b['analysis_goal'] = p['analysis_goal'] = 'DECIDE'
    p.update(candidate_basis='Evidence', candidates=[{'candidate_id': 'CAND-001', 'name': 'One', 'definition': 'One'}])
    base = minimal_payloads()
    ready = {**base['readiness_pack'], 'status': 'NEEDS_SUPPLEMENTAL', 'supplemental_request': base['supplemental_request']}
    extra = {**b['tasks'][1], 'task_id': 'RES-003', 'supplemental_request_id': 'SUP-001'}
    control.extend_brief(w, f, b, p, [extra], 'Evidence gap', readiness=ready)
    extra['supplemental_request_id'] = 'WRONG'
    with pytest.raises(ValueError, match='SUPPLEMENTAL'):
        control.extend_brief(w, f, b, p, [extra], 'Evidence gap', readiness=ready)
    with pytest.raises(ValueError, match='SUPPLEMENTAL'):
        control.extend_brief(w, f, b, p, [extra], 'Evidence gap')


def test_global_budget_reserves_recovery_and_does_not_depend_on_task_split(control):
    w, f, b = inputs()
    w['research_budget'] = {'limit': 8, 'recovery_reserve': 2}
    w['call_counts']['RES-002'] = {'search': 4, 'fetch': 2, 'map': 0}
    with pytest.raises(ValueError, match='BUDGET'):
        control.reserve_call(w, f, b, 'RES-002', 'fetch')
    revised = control.reserve_call(w, f, b, 'RES-002', 'fetch', recovery=True)
    assert revised['call_counts']['RES-002']['fetch'] == 3
    revised = control.reserve_call(revised, f, b, 'RES-002', 'fetch', recovery=True)
    assert revised['call_counts']['RES-002']['fetch'] == 4
    with pytest.raises(ValueError, match='BUDGET'):
        control.reserve_call(revised, f, b, 'RES-002', 'search', recovery=True)
    assert w['call_counts']['RES-002']['fetch'] == 2


def test_material_task_never_consumes_network_budget(control):
    w, f, b = inputs()
    with pytest.raises(ValueError, match='MATERIAL'):
        control.reserve_call(w, f, b, 'RES-001', 'search')


def test_stopped_recovery_requires_user_request_and_valid_inputs(control):
    w, f, b, p = completed(control)
    w.update(next_stage='STOPPED', blocking_reason={'code': 'UNRESOLVABLE_READINESS', 'task_ids': []}, analysis_goal='DECIDE')
    f['analysis_goal'] = b['analysis_goal'] = p['analysis_goal'] = 'DECIDE'
    p.update(candidate_basis='Evidence', candidates=[{'candidate_id': 'C-1', 'name': 'One', 'definition': 'One option'}])
    artifacts = {'problem_frame': f, 'research_brief': b, 'evidence_package': p}
    with pytest.raises(ValueError, match='USER_REQUEST'):
        control.resume_stage(w, 'decision-readiness-interview', artifacts)
    revised = control.resume_stage(w, 'decision-readiness-interview', artifacts, user_requested=True)
    assert revised['next_stage'] == 'decision-readiness-interview'
    assert 'blocking_reason' not in revised
    assert revised['call_counts'] == w['call_counts']
    p['workflow_id'] = '550e8400-e29b-41d4-a716-446655440999'
    with pytest.raises(ValueError, match='WORKFLOW'):
        control.resume_stage(w, 'decision-readiness-interview', artifacts, user_requested=True)


def test_technical_only_document_schema(control):
    doc = minimal_payloads()['solution_document']
    doc['content_profile'] = 'PRODUCT_SOFTWARE'
    doc['members'] = ['01-technical-solution-spec.md']
    control.validate('solution_document', doc)


@pytest.mark.parametrize('action', ['reopen', 'append'])
def test_stopped_research_controls_require_explicit_recovery(control, action):
    w, f, b, p = completed(control)
    w.update(next_stage='STOPPED', blocking_reason={'code': 'MISSING_OR_INVALID_ARTIFACT', 'task_ids': ['RES-002']})
    fn = control.reopen_research if action == 'reopen' else control.extend_brief
    payload = ['RES-002'] if action == 'reopen' else [{**b['tasks'][1], 'task_id': 'RES-003'}]
    with pytest.raises(ValueError, match='USER_REQUEST'):
        fn(w, f, b, p, payload, 'User supplied corrected evidence')
    result = fn(w, f, b, p, payload, 'User supplied corrected evidence', user_requested=True)
    assert result[0]['next_stage'] == 'research-execution'
    assert result[0]['call_counts']['RES-002'] == w['call_counts']['RES-002']


@pytest.mark.parametrize('endpoint,members', [
    ('PRD_ONLY', ['01-prd.md']),
    ('TECHNICAL_SPEC_ONLY', ['01-technical-solution-spec.md']),
    ('FORMAL_DOCUMENT', ['01-prd.md', '02-technical-solution-spec.md']),
    ('FINAL_SPEC_PACKAGE', ['01-prd.md', '02-technical-solution-spec.md']),
])
def test_document_members_are_bound_to_frame_endpoint(control, endpoint, members):
    base = minimal_payloads()
    frame = {**base['problem_frame'], 'analysis_goal': 'DECIDE', 'content_profile': 'PRODUCT_SOFTWARE', 'delivery_endpoint': endpoint}
    refined = base['refined_solution']
    doc = {**base['solution_document'], 'content_profile': 'PRODUCT_SOFTWARE', 'members': members}
    control.validate_document(frame, refined, doc)
    doc['members'] = ['01-prd.md'] if endpoint != 'PRD_ONLY' else ['01-technical-solution-spec.md']
    with pytest.raises(ValueError, match='ENDPOINT'):
        control.validate_document(frame, refined, doc)


def test_delegated_refinement_is_draft_until_final_review(control):
    refined = minimal_payloads()['refined_solution']
    refined['user_confirmation_status'] = 'DRAFT'
    control.validate('refined_solution', refined)


def test_private_host_source_is_rejected_by_real_control(control):
    w, f, b, p = completed(control)
    p['sources'][0]['normalized_url'] = 'http://127.0.0.1/private'
    with pytest.raises(ValueError):
        control.validate_evidence(w, f, b, p)


def test_dual_evidence_refs_rejected_before_correction(control):
    w, f, b, p = completed(control)
    w['artifact_refs']['evidence_draft'] = 'stale.yaml'
    with pytest.raises(ValueError, match='AMBIGUOUS'):
        control.reopen_research(w, f, b, p, ['RES-002'], 'Correct fact')


@pytest.mark.parametrize('corruption', ['uncounted', 'over_budget', 'duplicate_calls'])
def test_evidence_calls_close_to_preserved_budget(control, corruption):
    w, f, b, p = completed(control)
    if corruption == 'uncounted':
        w['call_counts']['RES-002']['search'] = 0
    elif corruption == 'over_budget':
        w['research_budget'] = {'limit': 1, 'recovery_reserve': 0}
    else:
        b['tasks'][0] = {**b['tasks'][1], 'task_id': 'RES-001'}
        w['call_counts']['RES-001']['search'] = 1
        p['execution_receipts'][0]['call_refs'] = ['call-2']
        p['execution_receipts'][0]['external_source_ids'] = []
        p['execution_receipts'][0]['source_ids'] = ['SRC-1']
        p['sources'].append({**p['sources'][0], 'source_id': 'SRC-1'})
        p['external_sources'] = []
        p['evidence_items'][0].update(web_source_ids=['SRC-1'], external_source_ids=[])
    with pytest.raises(ValueError, match='CALL|BUDGET'):
        control.validate_evidence(w, f, b, p)


def test_publication_matches_current_draft_and_next_revision(control):
    w, f, b, p = completed(control)
    draft = control._as_draft(p)
    draft['base_evidence_revision'] = 0
    w = control._activate(w)
    control.validate_publication(w, f, b, draft, p)
    p['evidence_revision'] = 99
    with pytest.raises(ValueError, match='REVISION'):
        control.validate_publication(w, f, b, draft, p)
    p['evidence_revision'] = 1
    p['evidence_items'][0]['statement'] = 'A different unreviewed claim'
    with pytest.raises(ValueError, match='DRAFT'):
        control.validate_publication(w, f, b, draft, p)


def test_material_source_cannot_escape_declared_carriers(control):
    w, f, b, p = completed(control)
    p['external_sources'][0]['artifact_ref'] = 'unrelated-private-file.md'
    with pytest.raises(ValueError, match='MATERIAL_SCOPE'):
        control.validate_evidence(w, f, b, p)


def test_public_task_cannot_launder_private_material_as_web_evidence(control):
    w, f, b, p = completed(control)
    w['call_counts']['RES-002']['search'] = 0
    p['sources'] = []
    p['external_sources'].append({'external_source_id': 'EXT-2', 'task_id': 'RES-002', 'kind': 'document', 'producer': 'external', 'artifact_ref': 'private-payroll.md', 'limitations': []})
    p['execution_receipts'][1].update(source_ids=[], call_refs=[], external_source_ids=['EXT-2'])
    p['evidence_items'][1].update(web_source_ids=[], external_source_ids=['EXT-2'])
    with pytest.raises(ValueError, match='PUBLIC_TASK_EXTERNAL_SOURCE'):
        control.validate_evidence(w, f, b, p)


def test_invalid_selected_candidate_blocks_upstream_resume(control):
    base = minimal_payloads()
    w, f, b, p = completed(control)
    w['analysis_goal'] = f['analysis_goal'] = b['analysis_goal'] = p['analysis_goal'] = 'DECIDE'
    p.update(candidate_basis='Evidence', candidates=[{'candidate_id': 'C-1', 'name': 'One', 'definition': 'One'}])
    ready = {**base['readiness_pack'], 'evidence_revision': 1, 'brief_revision': 1}
    decision = {**base['decision'], 'readiness_pack_id': ready['readiness_pack_id'], 'readiness_pack_version': ready['readiness_pack_version'], 'evidence_revision': 1, 'selected_candidate_ids': ['MISSING']}
    w.update(next_stage='solution-documentation')
    w['artifact_refs'].update(readiness_pack='ready.yaml', decision='decision.yaml')
    with pytest.raises(ValueError, match='CANDIDATE'):
        control.resume_stage(w, 'solution-refinement', {'problem_frame': f, 'research_brief': b, 'evidence_package': p, 'readiness_pack': ready, 'decision': decision})


def test_cli_initializes_real_yaml_and_rejects_external_artifact_path(control, tmp_path):
    w, f, b = inputs()
    for name, data in [('workflow.yaml', w), ('frame.yaml', f), ('brief.yaml', b)]:
        (tmp_path / name).write_text(yaml.safe_dump(data), encoding='utf-8')
    command = [sys.executable, str(SCRIPT), '--project-root', str(tmp_path), '--workflow', 'workflow.yaml', 'init']
    result = subprocess.run(command, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    saved = yaml.safe_load((tmp_path / 'workflow.yaml').read_text('utf-8'))
    draft = yaml.safe_load((tmp_path / saved['artifact_refs']['evidence_draft']).read_text('utf-8'))
    assert draft['unfinished_task_ids'] == ['RES-001', 'RES-002']
    saved['artifact_refs']['problem_frame'] = '../outside.yaml'
    (tmp_path / 'workflow.yaml').write_text(yaml.safe_dump(saved), encoding='utf-8')
    result = subprocess.run(command, text=True, capture_output=True)
    assert result.returncode != 0
    assert not (tmp_path.parent / 'outside.yaml').exists()
