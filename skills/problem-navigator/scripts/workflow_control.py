"""Small, local workflow controls. No research calls or autonomous decisions."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import re
from pathlib import Path
import tempfile
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import yaml
from web_research.security import normalize_public_url

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'references/artifacts.schema.json').read_text('utf-8'))
STAGES = ('problem-framing', 'research-design-kickoff', 'research-execution', 'decision-readiness-interview', 'adversarial-option-selection', 'solution-refinement', 'solution-documentation', 'solution-decomposition')
OUTPUTS = ('problem_frame', 'research_brief', 'evidence_package', 'readiness_pack', 'decision', 'refined_solution', 'solution_document', 'solution_spec_package')
DEFAULT_BUDGET = {'limit': 40, 'recovery_reserve': 6}


def validate(name: str, value: dict) -> None:
    schema = {'$schema': SCHEMA['$schema'], '$defs': SCHEMA['$defs'], '$ref': f'#/$defs/{name}'}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def _unique(values: list[dict], key: str) -> dict[str, dict]:
    result = {v[key]: v for v in values}
    if len(result) != len(values):
        raise ValueError(f'DUPLICATE_{key.upper()}')
    return result


def _boundary(workflow: dict, frame: dict, brief: dict) -> dict[str, dict]:
    for name, value in (('workflow', workflow), ('problem_frame', frame), ('research_brief', brief)):
        validate(name, value)
        if value['workflow_id'] != workflow['workflow_id']:
            raise ValueError('WORKFLOW_MISMATCH')
        if value.get('analysis_goal') != workflow.get('analysis_goal'):
            raise ValueError('GOAL_MISMATCH')
    tasks = _unique(brief['tasks'], 'task_id')
    if {'evidence_draft', 'evidence_package'} <= set(workflow['artifact_refs']):
        raise ValueError('AMBIGUOUS_EVIDENCE_REFS')
    if set(tasks) != set(workflow['call_counts']):
        raise ValueError('TASK_COUNTS_MISMATCH')
    for task_id, task in tasks.items():
        if task['task_kind'] == 'PUBLIC_WEB' and workflow['selected_backend'] == 'NONE':
            raise ValueError('OFFLINE_PUBLIC_TASK')
        if task['task_kind'] == 'PROVIDED_MATERIAL' and any(workflow['call_counts'][task_id].values()):
            raise ValueError('MATERIAL_NETWORK_COUNT')
    budget = workflow.get('research_budget', DEFAULT_BUDGET)
    if budget['recovery_reserve'] >= budget['limit']:
        raise ValueError('BUDGET_RESERVE_EXCEEDS_LIMIT')
    if sum(sum(c.values()) for c in workflow['call_counts'].values()) > budget['limit']:
        raise ValueError('RESEARCH_BUDGET_EXCEEDED')
    return tasks


def validate_evidence(workflow: dict, frame: dict, brief: dict, evidence: dict) -> None:
    """Validate receipt ownership and retained evidence before destructive ref changes."""
    tasks = _boundary(workflow, frame, brief)
    is_draft = 'completed_receipts' in evidence
    validate('evidence_draft' if is_draft else 'evidence_package', evidence)
    if evidence['workflow_id'] != workflow['workflow_id']:
        raise ValueError('WORKFLOW_MISMATCH')
    if evidence['brief_revision'] != brief['revision']:
        raise ValueError('BRIEF_REVISION_MISMATCH')
    if not is_draft and evidence['analysis_goal'] != workflow['analysis_goal']:
        raise ValueError('GOAL_MISMATCH')
    if workflow['analysis_goal'] == 'UNDERSTAND' and ('candidates' in evidence or 'candidate_basis' in evidence):
        raise ValueError('UNDERSTAND_CANDIDATES')
    receipts = _unique(evidence['completed_receipts'] if is_draft else evidence['execution_receipts'], 'task_id')
    unfinished = set(evidence.get('unfinished_task_ids', []))
    if set(receipts) & unfinished or set(receipts) | unfinished != set(tasks):
        raise ValueError('TASK_COVERAGE_MISMATCH')
    sources = _unique(evidence['sources'], 'source_id')
    for source in sources.values():
        if normalize_public_url(source['normalized_url']) != source['normalized_url']:
            raise ValueError('SOURCE_URL_NOT_NORMALIZED')
    external = _unique(evidence['external_sources'], 'external_source_id')
    _unique(evidence['evidence_items'], 'evidence_item_id')
    _unique(evidence['limitations'], 'limitation_id')
    candidates = _unique(evidence.get('candidates', []), 'candidate_id')
    source_owners: dict[str, str] = {}
    ext_owners: dict[str, str] = {}
    seen_calls: set[str] = set()
    for task_id, receipt in receipts.items():
        if tasks[task_id]['task_kind'] == 'PUBLIC_WEB' and receipt['external_source_ids']:
            raise ValueError('PUBLIC_TASK_EXTERNAL_SOURCE')
        calls = set(receipt['call_refs'])
        if calls & seen_calls or len(calls) > sum(workflow['call_counts'][task_id].values()):
            raise ValueError('RECEIPT_CALL_COUNT_MISMATCH')
        seen_calls.update(calls)
        for sid in receipt['source_ids']:
            if sid not in sources or sid in source_owners or sources[sid]['call_ref'] not in receipt['call_refs']:
                raise ValueError('SOURCE_RECEIPT_MISMATCH')
            source_owners[sid] = task_id
        for sid in receipt['external_source_ids']:
            if sid not in external or sid in ext_owners or external[sid]['task_id'] != task_id:
                raise ValueError('EXTERNAL_SOURCE_MISMATCH')
            ext_owners[sid] = task_id
        if tasks[task_id]['task_kind'] == 'PROVIDED_MATERIAL' and (receipt['source_ids'] or receipt['call_refs']):
            raise ValueError('MATERIAL_WEB_SOURCE')
        if tasks[task_id]['task_kind'] == 'PROVIDED_MATERIAL':
            declared = set(tasks[task_id]['material_refs'])
            observed = {external[sid]['artifact_ref'] for sid in receipt['external_source_ids']}
            if not observed <= declared or (receipt['quality_met'] and observed != declared):
                raise ValueError('MATERIAL_SCOPE_MISMATCH')
        if any(sources[sid]['provider'] == 'host_native' for sid in receipt['source_ids']):
            if receipt.get('fallback_authorization') != 'USER_APPROVED' or not receipt.get('fallback_reason'):
                raise ValueError('HOST_AUTHORIZATION_MISSING')
    if set(source_owners) != set(sources) or set(ext_owners) != set(external):
        raise ValueError('ORPHAN_SOURCE')
    supported: set[str] = set()
    limited: set[str] = set()
    for limitation in evidence['limitations']:
        tids = set(limitation['affected_task_ids'])
        cids = set(limitation['affected_candidate_ids'])
        if not tids <= set(tasks) or not cids <= set(candidates):
            raise ValueError('LIMITATION_REFERENCE_MISMATCH')
        limited.update(tids)
    for item in evidence['evidence_items']:
        task_id = item['task_id']
        if task_id not in receipts:
            raise ValueError('EVIDENCE_TASK_MISMATCH')
        if not set(item.get('candidate_ids', [])) <= set(candidates):
            raise ValueError('CANDIDATE_REFERENCE_MISMATCH')
        if any(source_owners.get(sid) != task_id for sid in item['web_source_ids']) or any(ext_owners.get(sid) != task_id for sid in item['external_source_ids']):
            raise ValueError('SOURCE_TASK_MISMATCH')
        if item['kind'] in ('ASSUMPTION', 'UNKNOWN') and task_id not in limited:
            raise ValueError('EVIDENCE_LIMITATION_MISSING')
        supported.add(task_id)
    for task_id, receipt in receipts.items():
        if receipt['outcome'] == 'WITH_RESULTS' and task_id not in supported:
            raise ValueError('EVIDENCE_SUPPORT_MISSING')
        if (receipt['outcome'] != 'WITH_RESULTS' or not receipt['quality_met']) and task_id not in limited:
            raise ValueError('RECEIPT_LIMITATION_MISSING')
    if not is_draft:
        state = 'RESEARCH_COMPLETE' if all(r['outcome'] == 'WITH_RESULTS' and r['quality_met'] for r in receipts.values()) else 'RESEARCH_PARTIAL'
        if evidence['research_state'] != state:
            raise ValueError('EVIDENCE_STATE_MISMATCH')


def validate_publication(workflow: dict, frame: dict, brief: dict, draft: dict, package: dict) -> None:
    """Validate the exact completed draft's evidence before accepted publication."""
    validate_evidence(workflow, frame, brief, draft)
    validate_evidence(workflow, frame, brief, package)
    if workflow['next_stage'] != 'research-execution' or 'evidence_draft' not in workflow['artifact_refs'] or draft['unfinished_task_ids']:
        raise ValueError('PUBLICATION_NOT_READY')
    if package['evidence_revision'] != draft['base_evidence_revision'] + 1:
        raise ValueError('PUBLICATION_REVISION_MISMATCH')
    for key in ('sources', 'external_sources', 'evidence_items', 'limitations', 'candidates', 'candidate_basis'):
        if package.get(key) != draft.get(key):
            raise ValueError('PUBLICATION_DRAFT_MISMATCH')
    if package['execution_receipts'] != draft['completed_receipts']:
        raise ValueError('PUBLICATION_DRAFT_MISMATCH')
    if not package['evidence_items']:
        raise ValueError('PUBLICATION_NO_EVIDENCE')


def _draft_path(workflow: dict) -> str:
    return f".problem-navigator/artifacts/{workflow['workflow_id']}/evidence-draft.yaml"


def _activate(workflow: dict) -> dict:
    updated = deepcopy(workflow)
    updated.update(next_stage='research-execution', research_state='RESEARCH_IN_PROGRESS')
    updated.pop('blocking_reason', None)
    for name in OUTPUTS[2:]:
        updated['artifact_refs'].pop(name, None)
    updated['artifact_refs']['evidence_draft'] = _draft_path(workflow)
    return updated


def initialize_draft(workflow: dict, frame: dict, brief: dict) -> tuple[dict, dict]:
    tasks = _boundary(workflow, frame, brief)
    if workflow['next_stage'] != 'research-execution' or workflow['research_state'] != 'NOT_STARTED' or any(any(c.values()) for c in workflow['call_counts'].values()) or any(k in workflow['artifact_refs'] for k in OUTPUTS[2:] + ('evidence_draft',)):
        raise ValueError('INITIALIZATION_WOULD_ERASE_HISTORY')
    draft = {'schema_version': 1, 'workflow_id': workflow['workflow_id'], 'brief_revision': brief['revision'], 'base_evidence_revision': 0, 'completed_receipts': [], 'sources': [], 'external_sources': [], 'evidence_items': [], 'limitations': [], 'unfinished_task_ids': list(tasks)}
    if workflow['analysis_goal'] == 'DECIDE':
        draft.update(candidate_basis='Candidates pending evidence; no selection made.', candidates=[])
    updated = _activate(workflow)
    validate_evidence(updated, frame, brief, draft)
    return updated, draft


def _as_draft(evidence: dict) -> dict:
    if 'completed_receipts' in evidence:
        return deepcopy(evidence)
    draft = {k: deepcopy(evidence[k]) for k in ('schema_version', 'workflow_id', 'brief_revision', 'sources', 'external_sources', 'evidence_items', 'limitations')}
    draft.update(base_evidence_revision=evidence['evidence_revision'], completed_receipts=deepcopy(evidence['execution_receipts']), unfinished_task_ids=[])
    for key in ('candidate_basis', 'candidates'):
        if key in evidence:
            draft[key] = deepcopy(evidence[key])
    return draft


def reopen_research(workflow: dict, frame: dict, brief: dict, evidence: dict, task_ids: list[str], reason: str, *, user_requested: bool = False) -> tuple[dict, dict]:
    if workflow['next_stage'] == 'STOPPED' and not user_requested:
        raise ValueError('EXPLICIT_USER_REQUEST_REQUIRED')
    validate_evidence(workflow, frame, brief, evidence)
    ids = set(task_ids)
    if not reason.strip() or not ids or len(ids) != len(task_ids) or not ids <= set(workflow['call_counts']):
        raise ValueError('INVALID_CORRECTION_TASKS_OR_REASON')
    draft = _as_draft(evidence)
    draft['completed_receipts'] = [r for r in draft['completed_receipts'] if r['task_id'] not in ids]
    used_sources = {s for r in draft['completed_receipts'] for s in r['source_ids']}
    used_external = {s for r in draft['completed_receipts'] for s in r['external_source_ids']}
    draft['sources'] = [s for s in draft['sources'] if s['source_id'] in used_sources]
    draft['external_sources'] = [s for s in draft['external_sources'] if s['external_source_id'] in used_external]
    # Candidate definitions retain IDs; all conclusions are recomputed from current evidence.
    draft['evidence_items'] = [e for e in draft['evidence_items'] if e['task_id'] not in ids]
    kept_limits = []
    for limitation in draft['limitations']:
        remaining = [t for t in limitation['affected_task_ids'] if t not in ids]
        if remaining or (not limitation['affected_task_ids'] and limitation['affected_candidate_ids']):
            kept_limits.append({**limitation, 'affected_task_ids': remaining})
    draft['limitations'] = kept_limits
    unfinished = set(draft['unfinished_task_ids']) | ids
    draft['unfinished_task_ids'] = [t['task_id'] for t in brief['tasks'] if t['task_id'] in unfinished]
    if 'candidate_basis' in draft:
        draft['candidate_basis'] = 'Reassess every candidate against current evidence after correction.'
    updated = _activate(workflow)
    validate_evidence(updated, frame, brief, draft)
    return updated, draft


def extend_brief(workflow: dict, frame: dict, brief: dict, evidence: dict, new_tasks: list[dict], reason: str, *, user_requested: bool = False, readiness: dict | None = None) -> tuple[dict, dict, dict]:
    if workflow['next_stage'] == 'STOPPED' and not user_requested:
        raise ValueError('EXPLICIT_USER_REQUEST_REQUIRED')
    validate_evidence(workflow, frame, brief, evidence)
    if not reason.strip() or not new_tasks or len(new_tasks) > 4:
        raise ValueError('INVALID_SUPPLEMENTAL_TASKS')
    if readiness is not None and readiness.get('status') == 'NEEDS_SUPPLEMENTAL':
        validate('readiness_pack', readiness)
        request = readiness['supplemental_request']
        if workflow['analysis_goal'] != 'DECIDE' or readiness['workflow_id'] != workflow['workflow_id'] or readiness['brief_revision'] != brief['revision'] or readiness['evidence_revision'] != evidence.get('evidence_revision'):
            raise ValueError('SUPPLEMENTAL_BINDING_MISMATCH')
        candidates = {c['candidate_id'] for c in evidence.get('candidates', [])}
        if not set(request['affected_candidate_ids']) <= candidates or any(t.get('supplemental_request_id') != request['request_id'] for t in new_tasks):
            raise ValueError('SUPPLEMENTAL_BINDING_MISMATCH')
        kind = 'PUBLIC_WEB' if request['gap_kind'] == 'PUBLIC_FACT' else 'PROVIDED_MATERIAL'
        if any(t['task_kind'] != kind for t in new_tasks):
            raise ValueError('SUPPLEMENTAL_SCOPE_MISMATCH')
        if kind == 'PROVIDED_MATERIAL' and {ref for task in new_tasks for ref in task['material_refs']} != set(request['material_refs']):
            raise ValueError('SUPPLEMENTAL_SCOPE_MISMATCH')
    elif any('supplemental_request_id' in t for t in new_tasks):
        raise ValueError('SUPPLEMENTAL_CARRIER_MISSING')
    revised = deepcopy(brief)
    revised['revision'] += 1
    revised['tasks'].extend(deepcopy(new_tasks))
    ids = _unique(revised['tasks'], 'task_id')
    validate('research_brief', revised)
    draft = _as_draft(evidence)
    draft['brief_revision'] = revised['revision']
    draft['unfinished_task_ids'].extend(t['task_id'] for t in new_tasks)
    updated = _activate(workflow)
    for tid in ids.keys() - workflow['call_counts'].keys():
        updated['call_counts'][tid] = {'search': 0, 'fetch': 0, 'map': 0}
    validate_evidence(updated, frame, revised, draft)
    return updated, revised, draft


def reserve_call(workflow: dict, frame: dict, brief: dict, task_id: str, operation: str, *, recovery: bool = False) -> dict:
    tasks = _boundary(workflow, frame, brief)
    if task_id not in tasks or operation not in ('search', 'fetch', 'map'):
        raise ValueError('INVALID_TASK_OR_OPERATION')
    if tasks[task_id]['task_kind'] != 'PUBLIC_WEB':
        raise ValueError('MATERIAL_NETWORK_CALL')
    if workflow['selected_backend'] not in ('RESEARCH_CORE', 'HOST_NATIVE'):
        raise ValueError('NO_AUTHORIZED_WEB_BACKEND')
    if workflow['next_stage'] != 'research-execution':
        raise ValueError('WRONG_STAGE')
    budget = workflow.get('research_budget', DEFAULT_BUDGET)
    used = sum(sum(c.values()) for c in workflow['call_counts'].values())
    if used >= budget['limit'] - (0 if recovery else budget['recovery_reserve']):
        raise ValueError('RESEARCH_BUDGET_EXHAUSTED')
    updated = deepcopy(workflow)
    updated['call_counts'][task_id][operation] += 1
    return updated


def validate_document(frame: dict, refined: dict, document: dict) -> None:
    """Check accepted document metadata before publication; review remains human."""
    for name, value in (('problem_frame', frame), ('refined_solution', refined), ('solution_document', document)):
        validate(name, value)
        if value['workflow_id'] != frame['workflow_id']:
            raise ValueError('WORKFLOW_MISMATCH')
    if frame['analysis_goal'] != 'DECIDE' or document['content_profile'] != frame['content_profile']:
        raise ValueError('PROFILE_OR_GOAL_MISMATCH')
    if refined['user_confirmation_status'] != 'ACCEPTED':
        raise ValueError('DOCUMENT_SEMANTICS_NOT_ACCEPTED')
    if document['refined_solution_id'] != refined['refined_solution_id'] or document['refined_solution_version'] != refined['refined_solution_version']:
        raise ValueError('STALE_UPSTREAM_BINDING')
    endpoint = frame['delivery_endpoint']
    if frame['content_profile'] == 'PRODUCT_SOFTWARE':
        members = {'PRD_ONLY': ['01-prd.md'], 'TECHNICAL_SPEC_ONLY': ['01-technical-solution-spec.md'], 'FORMAL_DOCUMENT': ['01-prd.md', '02-technical-solution-spec.md'], 'FINAL_SPEC_PACKAGE': ['01-prd.md', '02-technical-solution-spec.md']}
        if document['members'] != members.get(endpoint):
            raise ValueError('DOCUMENT_ENDPOINT_MISMATCH')
    elif endpoint not in ('FORMAL_DOCUMENT', 'FINAL_SPEC_PACKAGE'):
        raise ValueError('DOCUMENT_ENDPOINT_MISMATCH')


def resume_stage(workflow: dict, target: str, artifacts: dict[str, dict], *, user_requested: bool = False) -> dict:
    validate('workflow', workflow)
    if workflow['next_stage'] == 'STOPPED' and not user_requested:
        raise ValueError('EXPLICIT_USER_REQUEST_REQUIRED')
    if target not in STAGES[3:]:
        raise ValueError('USE_INIT_OR_REOPEN_FOR_RESEARCH_RECOVERY')
    if workflow.get('analysis_goal') != 'DECIDE':
        raise ValueError('UNDERSTAND_USE_REOPEN')
    position = STAGES.index(target)
    for key in OUTPUTS[:position]:
        if key not in artifacts or key not in workflow['artifact_refs']:
            raise ValueError(f'MISSING_UPSTREAM_{key}')
        validate(key, artifacts[key])
        if artifacts[key]['workflow_id'] != workflow['workflow_id']:
            raise ValueError('WORKFLOW_MISMATCH')
    validate_evidence(workflow, artifacts['problem_frame'], artifacts['research_brief'], artifacts['evidence_package'])
    checks = [('readiness_pack', 'evidence_revision', 'evidence_package', 'evidence_revision'), ('readiness_pack', 'brief_revision', 'research_brief', 'revision'), ('decision', 'readiness_pack_id', 'readiness_pack', 'readiness_pack_id'), ('decision', 'readiness_pack_version', 'readiness_pack', 'readiness_pack_version'), ('decision', 'evidence_revision', 'evidence_package', 'evidence_revision'), ('refined_solution', 'decision_id', 'decision', 'decision_id'), ('refined_solution', 'decision_version', 'decision', 'decision_version'), ('solution_document', 'refined_solution_id', 'refined_solution', 'refined_solution_id'), ('solution_document', 'refined_solution_version', 'refined_solution', 'refined_solution_version')]
    retained = set(OUTPUTS[:position])
    for child, field, parent, parent_field in checks:
        if child in retained and artifacts[child][field] != artifacts[parent][parent_field]:
            raise ValueError('STALE_UPSTREAM_BINDING')
    if 'readiness_pack' in retained and artifacts['readiness_pack']['status'] != 'READY':
        raise ValueError('READINESS_NOT_READY')
    if 'decision' in retained:
        candidates = {c['candidate_id'] for c in artifacts['evidence_package'].get('candidates', [])}
        if not set(artifacts['decision']['selected_candidate_ids']) <= candidates:
            raise ValueError('DECISION_CANDIDATE_MISMATCH')
    if 'solution_document' in retained:
        validate_document(artifacts['problem_frame'], artifacts['refined_solution'], artifacts['solution_document'])
        if artifacts['problem_frame']['delivery_endpoint'] != 'FINAL_SPEC_PACKAGE':
            raise ValueError('DECOMPOSITION_NOT_REQUESTED')
    updated = deepcopy(workflow)
    updated.update(next_stage=target, research_state=artifacts['evidence_package']['research_state'])
    updated.pop('blocking_reason', None)
    for name in OUTPUTS[position:] + ('evidence_draft',):
        updated['artifact_refs'].pop(name, None)
    validate('workflow', updated)
    return updated


def _path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if target == root or root not in target.parents or Path(relative).is_absolute():
        raise ValueError('PATH_OUTSIDE_PROJECT')
    return target


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.workflow-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            yaml.safe_dump(value, stream, allow_unicode=True, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--workflow', required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('init')
    for action in ('reopen', 'append'):
        item = sub.add_parser(action)
        item.add_argument('--reason', required=True)
        item.add_argument('--user-requested', action='store_true')
        if action == 'reopen':
            item.add_argument('--task-id', action='append', required=True)
        else:
            item.add_argument('--tasks', required=True)
    resume = sub.add_parser('resume')
    resume.add_argument('--target', choices=STAGES[3:], required=True)
    resume.add_argument('--user-requested', action='store_true')
    reserve = sub.add_parser('reserve')
    reserve.add_argument('--task-id', required=True)
    reserve.add_argument('--operation', choices=('search', 'fetch', 'map'), required=True)
    reserve.add_argument('--recovery', action='store_true')
    document_check = sub.add_parser('validate-document')
    document_check.add_argument('--document', required=True)
    publication = sub.add_parser('validate-publication')
    publication.add_argument('--package', required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    workflow_path = _path(root, args.workflow)
    workflow = yaml.safe_load(workflow_path.read_text('utf-8'))
    validate('workflow', workflow)
    def read(name: str) -> dict:
        return yaml.safe_load(_path(root, workflow['artifact_refs'][name]).read_text('utf-8'))
    frame, brief = read('problem_frame'), read('research_brief')
    if args.action == 'validate-publication':
        package = yaml.safe_load(_path(root, args.package).read_text('utf-8'))
        validate_publication(workflow, frame, brief, read('evidence_draft'), package)
        print(json.dumps({'publication_valid': True}))
        return
    if args.action == 'validate-document':
        _boundary(workflow, frame, brief)
        document = yaml.safe_load(_path(root, args.document).read_text('utf-8'))
        validate_document(frame, read('refined_solution'), document)
        print(json.dumps({'document_valid': True}))
        return
    writes: list[tuple[Path, dict]] = []
    if args.action == 'init':
        updated, draft = initialize_draft(workflow, frame, brief)
    elif args.action in ('reopen', 'append'):
        evidence = read('evidence_draft' if 'evidence_draft' in workflow['artifact_refs'] else 'evidence_package')
        if args.action == 'reopen':
            updated, draft = reopen_research(workflow, frame, brief, evidence, args.task_id, args.reason, user_requested=args.user_requested)
        else:
            tasks = yaml.safe_load(_path(root, args.tasks).read_text('utf-8'))
            readiness = read('readiness_pack') if 'readiness_pack' in workflow['artifact_refs'] else None
            updated, revised, draft = extend_brief(workflow, frame, brief, evidence, tasks, args.reason, user_requested=args.user_requested, readiness=readiness)
            writes.append((_path(root, workflow['artifact_refs']['research_brief']), revised))
    elif args.action == 'resume':
        needed = OUTPUTS[:STAGES.index(args.target)]
        updated = resume_stage(workflow, args.target, {k: read(k) for k in needed}, user_requested=args.user_requested)
    else:
        evidence = read('evidence_draft')
        validate_evidence(workflow, frame, brief, evidence)
        if args.task_id not in evidence['unfinished_task_ids']:
            raise ValueError('TASK_ALREADY_COMPLETED')
        updated = reserve_call(workflow, frame, brief, args.task_id, args.operation, recovery=args.recovery)
    validate('workflow', updated)
    if args.action in ('init', 'reopen', 'append'):
        writes.append((_path(root, updated['artifact_refs']['evidence_draft']), draft))
    for path, value in writes:
        _write(path, value)
    _write(workflow_path, updated)
    print(json.dumps({'next_stage': updated['next_stage'], 'research_state': updated['research_state']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # No artifact bodies, request values, or external data in CLI errors.
        code = str(error) if isinstance(error, ValueError) and re.fullmatch(r'[A-Z0-9_]+', str(error)) else 'MISSING_OR_INVALID_ARTIFACT'
        raise SystemExit(f'Workflow operation rejected: {code}.') from None
