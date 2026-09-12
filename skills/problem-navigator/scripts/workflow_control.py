"""Small, local workflow controls. No research calls or autonomous decisions."""
from __future__ import annotations

import argparse
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import time
import sys
import uuid
from datetime import date, datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import yaml
# Resolve this bundle's code independently of editable installs and the caller's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'mcp/web-research-mcp/src'))
from web_research.security import normalize_public_url

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'references/artifacts.schema.json').read_text('utf-8'))
STAGES = ('problem-framing', 'research-design-kickoff', 'research-execution', 'decision-readiness-interview', 'adversarial-option-selection', 'solution-refinement', 'solution-documentation', 'solution-decomposition')
OUTPUTS = ('problem_frame', 'research_brief', 'evidence_package', 'readiness_pack', 'decision', 'refined_solution', 'solution_document', 'solution_spec_package')
DEFAULT_BUDGET = {'limit': 40, 'recovery_reserve': 6}


def validate(name: str, value: dict) -> None:
    schema = {'$schema': SCHEMA['$schema'], '$defs': SCHEMA['$defs'], '$ref': f'#/$defs/{name}'}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    for source in ([value] if name == 'source' else value.get('sources', [])):
        stamp = source['retrieved_at']
        try:
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', stamp):
                date.fromisoformat(stamp)
            elif datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is None:
                raise ValueError('timezone required')
        except (TypeError, ValueError):
            raise ValueError('INVALID_SOURCE_RETRIEVAL_TIME') from None


def _unique(values: list[dict], key: str) -> dict[str, dict]:
    result = {v[key]: v for v in values}
    if len(result) != len(values):
        raise ValueError(f'DUPLICATE_{key.upper()}')
    return result


def validate_brief_design(frame: dict, brief: dict, *, require_design: bool = False) -> None:
    """Check declared coverage and prerequisite graph, not question relevance."""
    tasks = _unique(brief['tasks'], 'task_id')
    visiting, finished = set(), set()
    def visit(tid):
        if tid in visiting or tid not in tasks:
            raise ValueError('INVALID_TASK_DEPENDENCIES')
        if tid in finished:
            return
        visiting.add(tid)
        for dependency in tasks[tid].get('depends_on', []):
            visit(dependency)
        visiting.remove(tid); finished.add(tid)
    for tid in tasks:
        visit(tid)
    design = brief.get('design')
    if design is None:
        if require_design:
            raise ValueError('RESEARCH_DESIGN_REQUIRED')
        return
    rows = _unique(design['theme_coverage'], 'theme_id')
    if frame['content_profile'] == 'PRODUCT_SOFTWARE':
        if not design.get('product_context', '').strip() or not {'product-form', 'critical-resources', 'open-source-ecosystem', 'implementation-path'} <= set(rows):
            raise ValueError('PRODUCT_RESEARCH_COVERAGE_REQUIRED')
    elif 'product_context' in design:
        raise ValueError('GENERAL_PRODUCT_CONTEXT_FORBIDDEN')
    covered = set()
    for row in rows.values():
        tids = set(row['task_ids'])
        if not tids <= set(tasks) or (row['treatment'] == 'NOT_APPLICABLE') != (not tids):
            raise ValueError('RESEARCH_DESIGN_TASK_COVERAGE')
        if row['treatment'] == 'RESEARCH' and any(tasks[tid]['theme_id'] != row['theme_id'] for tid in tids):
            raise ValueError('RESEARCH_DESIGN_THEME_MISMATCH')
        covered.update(tids)
    if covered != set(tasks):
        raise ValueError('RESEARCH_DESIGN_TASK_COVERAGE')


def dependent_task_ids(brief: dict, task_ids) -> set[str]:
    ids = set(task_ids)
    while True:
        expanded = ids | {t['task_id'] for t in brief['tasks'] if ids.intersection(t.get('depends_on', []))}
        if expanded == ids:
            return ids
        ids = expanded


def _boundary(workflow: dict, frame: dict, brief: dict) -> dict[str, dict]:
    for name, value in (('workflow', workflow), ('problem_frame', frame), ('research_brief', brief)):
        validate(name, value)
        if value['workflow_id'] != workflow['workflow_id']:
            raise ValueError('WORKFLOW_MISMATCH')
        if value.get('analysis_goal') != workflow.get('analysis_goal'):
            raise ValueError('GOAL_MISMATCH')
    tasks = _unique(brief['tasks'], 'task_id')
    validate_brief_design(frame, brief)
    if (brief['problem_frame_id'], brief['problem_frame_version']) != (frame['problem_frame_id'], frame['problem_frame_version']):
        raise ValueError('FRAME_BINDING_MISMATCH')
    if frame['user_confirmation_status'] != 'ACCEPTED':
        raise ValueError('FRAME_NOT_ACCEPTED')
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


def validate_evidence(workflow: dict, frame: dict, brief: dict, evidence: dict, *, require_candidate_coverage: bool = True) -> None:
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
        grant = workflow.get('research_reservations', {}).get(source['call_ref'])
        kind = source.get('content_kind')
        if grant and (grant['operation'] == 'map' or (kind == 'search_excerpt' and grant['operation'] != 'search')
                      or (grant['operation'] == 'search' and kind in ('page_excerpt', 'full_page'))):
            raise ValueError('SOURCE_OPERATION_MISMATCH')
    external = _unique(evidence['external_sources'], 'external_source_id')
    items = _unique(evidence['evidence_items'], 'evidence_item_id')
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
    candidate_themes: set[tuple[str, str]] = set()
    for limitation in evidence['limitations']:
        tids = set(limitation['affected_task_ids'])
        cids = set(limitation['affected_candidate_ids'])
        if not tids <= set(tasks) or not cids <= set(candidates):
            raise ValueError('LIMITATION_REFERENCE_MISMATCH')
        limited.update(tids)
        candidate_themes.update((cid, tasks[tid]['theme_id']) for cid in cids for tid in tids)
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
        if item['kind'] == 'INFERENCE':
            if any(eid not in items or items[eid]['kind'] != 'FACT' for eid in item['basis_evidence_ids']):
                raise ValueError('INFERENCE_BASIS_MISMATCH')
        if item['kind'] in ('FACT', 'INFERENCE'):
            candidate_themes.update((cid, tasks[task_id]['theme_id']) for cid in item.get('candidate_ids', []))
            supported.add(task_id)
    for task_id, receipt in receipts.items():
        if receipt['outcome'] == 'WITH_RESULTS' and task_id not in supported:
            raise ValueError('EVIDENCE_SUPPORT_MISSING')
        if (receipt['outcome'] != 'WITH_RESULTS' or not receipt['quality_met']) and task_id not in limited:
            raise ValueError('RECEIPT_LIMITATION_MISSING')
    unfinished_themes = {tasks[tid]['theme_id'] for tid in unfinished}
    required_themes = {(cid, tasks[tid]['theme_id']) for cid in candidates for tid in receipts if tasks[tid]['theme_id'] not in unfinished_themes}
    if require_candidate_coverage and not required_themes <= candidate_themes:
        raise ValueError('CANDIDATE_THEME_COVERAGE_MISSING')
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
    ids = dependent_task_ids(brief, ids)
    # A factual correction also invalidates conclusions in other tasks that
    # explicitly depend on those facts. Reopen their full receipts conservatively.
    while True:
        removed_items = {item['evidence_item_id'] for item in draft['evidence_items'] if item['task_id'] in ids}
        dependent_tasks = {item['task_id'] for item in draft['evidence_items'] if removed_items.intersection(item.get('basis_evidence_ids', []))}
        expanded = dependent_task_ids(brief, ids | dependent_tasks)
        if expanded == ids:
            break
        ids = expanded
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
    if 'design' in revised:
        rows = revised['design']['theme_coverage']
        for task in new_tasks:
            row = next((r for r in rows if r['theme_id'] == task['theme_id']), None)
            if row is None:
                rows.append({'theme_id': task['theme_id'], 'treatment': 'RESEARCH', 'rationale': reason, 'task_ids': [task['task_id']]})
            else:
                if row['treatment'] == 'NOT_APPLICABLE':
                    row.update(treatment='RESEARCH', rationale=reason)
                row['task_ids'].append(task['task_id'])
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


def validate_readiness(workflow: dict, frame: dict, brief: dict, evidence: dict, readiness: dict) -> None:
    """Check current limitation dispositions; factual sufficiency remains reviewed."""
    validate_evidence(workflow, frame, brief, evidence)
    validate('readiness_pack', readiness)
    if workflow['analysis_goal'] != 'DECIDE' or readiness['workflow_id'] != workflow['workflow_id']:
        raise ValueError('READINESS_WORKFLOW_MISMATCH')
    if readiness['brief_revision'] != brief['revision'] or readiness['evidence_revision'] != evidence.get('evidence_revision'):
        raise ValueError('STALE_UPSTREAM_BINDING')
    limitations = _unique(evidence['limitations'], 'limitation_id')
    dispositions = _unique(readiness['limitation_dispositions'], 'limitation_id')
    if set(dispositions) != set(limitations):
        raise ValueError('LIMITATION_DISPOSITION_COVERAGE_MISMATCH')
    if readiness['status'] == 'READY':
        if any(d['disposition'] != 'ACCEPTED' for d in dispositions.values()):
            raise ValueError('READINESS_UNRESOLVED_LIMITATION')
        if any(limitation['may_change_decision'] for limitation in limitations.values()):
            raise ValueError('READINESS_MATERIAL_LIMITATION_UNRESOLVED')
    if readiness['status'] == 'NEEDS_SUPPLEMENTAL':
        candidates = {candidate['candidate_id'] for candidate in evidence['candidates']}
        if not set(readiness['supplemental_request']['affected_candidate_ids']) <= candidates:
            raise ValueError('SUPPLEMENTAL_BINDING_MISMATCH')


def validate_decision(workflow: dict, frame: dict, brief: dict, evidence: dict, readiness: dict, decision: dict, *, project_root: Path | None = None) -> None:
    """Validate a selected decision against current evidence and its real review."""
    validate_readiness(workflow, frame, brief, evidence, readiness)
    validate('decision', decision)
    if decision['workflow_id'] != workflow['workflow_id']:
        raise ValueError('WORKFLOW_MISMATCH')
    if readiness['status'] != 'READY':
        raise ValueError('READINESS_NOT_READY')
    if (decision['readiness_pack_id'], decision['readiness_pack_version'], decision['evidence_revision']) != (readiness['readiness_pack_id'], readiness['readiness_pack_version'], evidence['evidence_revision']):
        raise ValueError('STALE_UPSTREAM_BINDING')
    if not set(decision['selected_candidate_ids']) <= {candidate['candidate_id'] for candidate in evidence['candidates']}:
        raise ValueError('DECISION_CANDIDATE_MISMATCH')
    path = Path(__file__).resolve().parents[2] / 'adversarial-option-selection/scripts/court_control.py'
    if not path.is_file():
        raise ValueError('COURT_VALIDATOR_MISSING')
    spec = importlib.util.spec_from_file_location('problem_navigator_court_control', path)
    court = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(court)
    court.validate_decision_review(project_root, workflow, frame, brief, evidence, readiness, decision)


def validate_document(frame: dict, refined: dict, document: dict, *, project_root: Path | None = None) -> None:
    """Check metadata, and frozen files when root is supplied; not prose truth."""
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
    requirements = _unique(refined.get('requirements', []), 'requirement_id')
    traces = document.get('traceability', [])
    if {trace['requirement_id'] for trace in traces} != set(requirements):
        raise ValueError('DOCUMENT_TRACE_REQUIREMENT_MISMATCH')
    if any(trace['member'] not in document['members'] for trace in traces):
        raise ValueError('DOCUMENT_TRACE_MEMBER_MISMATCH')
    if 'member_hashes' in document and set(document['member_hashes']) != set(document['members']):
        raise ValueError('DOCUMENT_MEMBER_HASH_COVERAGE_MISMATCH')
    if project_root is not None:
        root = Path(project_root).resolve()
        if set(document.get('member_hashes', {})) != set(document['members']):
            raise ValueError('DOCUMENT_MEMBER_HASH_COVERAGE_MISMATCH')
        contents = {}
        for member in document['members']:
            path = _path(root, member)
            if not path.is_file():
                raise ValueError('DOCUMENT_MEMBER_MISSING')
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != document['member_hashes'][member]:
                raise ValueError('DOCUMENT_MEMBER_HASH_MISMATCH')
            contents[member] = content
        for trace in traces:
            if trace['locator'] not in contents[trace['member']].decode('utf-8'):
                raise ValueError('DOCUMENT_TRACE_LOCATOR_MISSING')


def resume_stage(workflow: dict, target: str, artifacts: dict[str, dict], *, user_requested: bool = False, project_root: Path | None = None) -> dict:
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
    if 'readiness_pack' in retained:
        validate_readiness(workflow, artifacts['problem_frame'], artifacts['research_brief'], artifacts['evidence_package'], artifacts['readiness_pack'])
        if artifacts['readiness_pack']['status'] != 'READY':
            raise ValueError('READINESS_NOT_READY')
    if 'decision' in retained:
        validate_decision(workflow, artifacts['problem_frame'], artifacts['research_brief'], artifacts['evidence_package'], artifacts['readiness_pack'], artifacts['decision'], project_root=project_root)
    if 'solution_document' in retained:
        validate_document(artifacts['problem_frame'], artifacts['refined_solution'], artifacts['solution_document'], project_root=project_root)
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
    text = (json.dumps(value, ensure_ascii=False, indent=2) + '\n'
            if path.suffix.lower() == '.json' else yaml.safe_dump(value, allow_unicode=True, sort_keys=False))
    _write_bytes(path, text.encode('utf-8'))


def _read_file(path: Path):
    data = path.read_bytes()
    return json.loads(data) if path.suffix.lower() == '.json' else yaml.safe_load(data)


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.workflow-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def workflow_lock(workflow_path: Path, timeout: float = 10.0):
    """Serialize a complete local read/validate/write, never a provider call.

    An OS lock is released after process death. All cooperating mutating helpers
    use this same path; copied/cloud-synced workspaces are not a shared lock domain.
    """
    path = Path(str(workflow_path.resolve()) + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'\0'); stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise ValueError('WORKFLOW_BUSY') from None
                time.sleep(0.025)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('INVALID_ARGUMENTS')


def _research_helper():
    path = Path(__file__).resolve().parents[2] / 'research-execution/scripts/research_control.py'
    spec = importlib.util.spec_from_file_location('workflow_research_dispatch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = _SafeParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--workflow', required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    create = sub.add_parser('create')
    create.add_argument('--backend', choices=('NONE', 'UNSET', 'RESEARCH_CORE', 'HOST_NATIVE'), required=True)
    create.add_argument('--user-approved-host', action='store_true')
    accept = sub.add_parser('accept-frame')
    accept.add_argument('--frame', required=True)
    accept.add_argument('--reviewed-sha256', required=True)
    accept.add_argument('--user-response', required=True)
    sub.add_parser('attach-brief').add_argument('--brief', required=True)
    for action in ('preview-report', 'accept-report'):
        report = sub.add_parser(action)
        report.add_argument('--package', required=True)
        if action == 'preview-report':
            report.add_argument('--output', required=True)
        else:
            report.add_argument('--report', required=True)
            report.add_argument('--reviewed-sha256', required=True)
            report.add_argument('--user-response', required=True)
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
    readiness_check = sub.add_parser('validate-readiness')
    readiness_check.add_argument('--readiness', required=True)
    decision_check = sub.add_parser('validate-decision')
    decision_check.add_argument('--decision', required=True)
    publication = sub.add_parser('validate-publication')
    publication.add_argument('--package', required=True)
    brief_check = sub.add_parser('validate-brief')
    brief_check.add_argument('--require-design', action='store_true')
    args = parser.parse_args()
    root = args.project_root.resolve()
    workflow_path = _path(root, args.workflow)
    with workflow_lock(workflow_path):
        _run_cli(args, root, workflow_path)


def _run_cli(args, root: Path, workflow_path: Path) -> None:
    if args.action == 'create':
        if workflow_path.exists():
            raise ValueError('WORKFLOW_ALREADY_EXISTS')
        if (args.backend == 'HOST_NATIVE') != args.user_approved_host:
            raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        identifier = str(uuid.UUID(workflow_path.stem)) if re.fullmatch(SCHEMA['$defs']['workflow_id']['pattern'], workflow_path.stem) else str(uuid.uuid4())
        workflow = dict(schema_version=1, workflow_id=identifier, next_stage='problem-framing',
                        selected_backend=args.backend, native_fallback_approved=args.user_approved_host,
                        research_state='NOT_STARTED', call_counts={}, artifact_refs={}, research_budget=deepcopy(DEFAULT_BUDGET))
        validate('workflow', workflow)
        _write(workflow_path, workflow)
        print(json.dumps({'workflow_id': workflow['workflow_id'], 'next_stage': 'problem-framing'}))
        return
    workflow = _read_file(workflow_path)
    validate('workflow', workflow)
    if args.action == 'accept-frame':
        if workflow['next_stage'] != 'problem-framing' or workflow['call_counts']:
            raise ValueError('FRAME_ACCEPTANCE_STAGE_REQUIRED')
        path = _path(root, args.frame)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != args.reviewed_sha256 or not args.user_response.strip():
            raise ValueError('REVIEWED_FRAME_AND_RESPONSE_REQUIRED')
        frame = json.loads(data) if path.suffix.lower() == '.json' else yaml.safe_load(data)
        validate('problem_frame', frame)
        if frame['workflow_id'] != workflow['workflow_id']:
            raise ValueError('WORKFLOW_MISMATCH')
        frame.update(user_confirmation_status='ACCEPTED', confirmation_basis=args.user_response)
        validate('problem_frame', frame)
        ref = f".problem-navigator/artifacts/{workflow['workflow_id']}/problem-frame.yaml"
        workflow.update(analysis_goal=frame['analysis_goal'], next_stage='research-design-kickoff')
        workflow['artifact_refs']['problem_frame'] = ref
        validate('workflow', workflow)
        _write(_path(root, ref), frame)
        _write(workflow_path, workflow)
        print(json.dumps({'next_stage': workflow['next_stage'], 'frame_ref': ref}))
        return
    def read(name: str) -> dict:
        return _read_file(_path(root, workflow['artifact_refs'][name]))
    if args.action == 'attach-brief':
        if workflow['next_stage'] != 'research-design-kickoff' or workflow['call_counts'] or 'research_brief' in workflow['artifact_refs']:
            raise ValueError('INITIAL_BRIEF_STAGE_REQUIRED')
        frame = read('problem_frame')
        brief = _read_file(_path(root, args.brief))
        if brief['revision'] != 1:
            raise ValueError('INITIAL_BRIEF_REVISION_REQUIRED')
        workflow['artifact_refs']['research_brief'] = args.brief
        workflow['call_counts'] = {t['task_id']: {'search': 0, 'fetch': 0, 'map': 0} for t in brief['tasks']}
        workflow['next_stage'] = 'research-execution'
        _boundary(workflow, frame, brief)
        validate_brief_design(frame, brief, require_design=True)
        _write(workflow_path, workflow)
        print(json.dumps({'next_stage': 'research-execution'}))
        return
    frame, brief = read('problem_frame'), read('research_brief')
    if args.action in ('preview-report', 'accept-report'):
        package = _read_file(_path(root, args.package))
        report = package['neutral_synthesis'].encode('utf-8')
        digest = hashlib.sha256(report).hexdigest()
        package_digest = hashlib.sha256(_path(root, args.package).read_bytes()).hexdigest()
        acceptance_path = _path(root, f".problem-navigator/artifacts/{workflow['workflow_id']}/report-acceptance.json")
        if args.action == 'accept-report':
            if not args.user_response.strip() or args.reviewed_sha256 != digest or _path(root, args.report).read_bytes() != report:
                raise ValueError('REVIEWED_REPORT_AND_RESPONSE_REQUIRED')
            # Repeating acceptance of the same published package is harmless.
            if workflow['artifact_refs'].get('evidence_package') == args.package:
                accepted = json.loads(acceptance_path.read_text('utf-8'))
                if accepted['report_sha256'] != digest or accepted['package_sha256'] != package_digest:
                    raise ValueError('ACCEPTED_REPORT_CHANGED')
                validate_evidence(workflow, frame, brief, package)
                print(json.dumps({'next_stage': workflow['next_stage'], 'already_accepted': True}))
                return
        draft = read('evidence_draft')
        validate_publication(workflow, frame, brief, draft, package)
        _research_helper().validate_dispatch_publication(root, workflow, frame, brief, draft, package)
        if args.action == 'preview-report':
            path = _path(root, args.output)
            input_refs = list(workflow['artifact_refs'].values()) + [args.package]
            input_refs.extend(ref for task in brief['tasks'] for ref in task.get('material_refs', []))
            protected = {_path(root, ref) for ref in input_refs} | {workflow_path, acceptance_path}
            if path.suffix.lower() != '.md' or path in protected:
                raise ValueError('REPORT_MARKDOWN_PATH_REQUIRED')
            _write_bytes(path, report)
            print(json.dumps({'report_ref': args.output, 'report_sha256': digest,
                              'research_state': package['research_state'], 'awaiting_acceptance': True}))
            return
        workflow['artifact_refs'].pop('evidence_draft')
        workflow['artifact_refs']['evidence_package'] = args.package
        workflow.update(research_state=package['research_state'], next_stage='DONE' if workflow['analysis_goal'] == 'UNDERSTAND' else 'decision-readiness-interview')
        workflow.pop('blocking_reason', None)
        validate('workflow', workflow)
        acceptance = {'package_ref': args.package, 'report_ref': args.report,
                      'report_sha256': digest, 'package_sha256': package_digest, 'user_response': args.user_response}
        _write(acceptance_path, acceptance)
        _write(workflow_path, workflow)
        print(json.dumps({'next_stage': workflow['next_stage'], 'research_state': workflow['research_state']}))
        return
    if args.action == 'validate-brief':
        _boundary(workflow, frame, brief)
        validate_brief_design(frame, brief, require_design=args.require_design)
        print(json.dumps({'brief_valid': True, 'revision': brief['revision']}))
        return
    if args.action == 'validate-publication':
        package = _read_file(_path(root, args.package))
        validate_publication(workflow, frame, brief, read('evidence_draft'), package)
        _research_helper().validate_dispatch_publication(root, workflow, frame, brief, read('evidence_draft'), package)
        print(json.dumps({'publication_valid': True}))
        return
    if args.action == 'validate-document':
        decision, refined = read('decision'), read('refined_solution')
        validate_decision(workflow, frame, brief, read('evidence_package'), read('readiness_pack'), decision, project_root=root)
        if (refined['decision_id'], refined['decision_version']) != (decision['decision_id'], decision['decision_version']):
            raise ValueError('STALE_UPSTREAM_BINDING')
        document = _read_file(_path(root, args.document))
        validate_document(frame, refined, document, project_root=root)
        print(json.dumps({'document_valid': True}))
        return
    if args.action == 'validate-readiness':
        readiness = _read_file(_path(root, args.readiness))
        validate_readiness(workflow, frame, brief, read('evidence_package'), readiness)
        print(json.dumps({'readiness_valid': True, 'status': readiness['status']}))
        return
    if args.action == 'validate-decision':
        decision = _read_file(_path(root, args.decision))
        validate_decision(workflow, frame, brief, read('evidence_package'), read('readiness_pack'), decision, project_root=root)
        print(json.dumps({'decision_valid': True, 'review_mode': decision['review']['mode']}))
        return
    writes: list[tuple[Path, dict]] = []
    if args.action == 'init':
        updated, draft = initialize_draft(workflow, frame, brief)
    elif args.action in ('reopen', 'append'):
        evidence = read('evidence_draft' if 'evidence_draft' in workflow['artifact_refs'] else 'evidence_package')
        if args.action == 'reopen':
            reopen_ids = _research_helper().affected_dispatch_tasks(root, workflow, brief, evidence, args.task_id)
            updated, draft = reopen_research(workflow, frame, brief, evidence, list(reopen_ids), args.reason, user_requested=args.user_requested)
        else:
            tasks = _read_file(_path(root, args.tasks))
            readiness = read('readiness_pack') if 'readiness_pack' in workflow['artifact_refs'] else None
            updated, revised, draft = extend_brief(workflow, frame, brief, evidence, tasks, args.reason, user_requested=args.user_requested, readiness=readiness)
            writes.append((_path(root, workflow['artifact_refs']['research_brief']), revised))
    elif args.action == 'resume':
        needed = OUTPUTS[:STAGES.index(args.target)]
        updated = resume_stage(workflow, args.target, {k: read(k) for k in needed}, user_requested=args.user_requested, project_root=root)
    else:
        _research_helper().guard_legacy_reserve(root, workflow, args.task_id)
        evidence = read('evidence_draft')
        validate_evidence(workflow, frame, brief, evidence)
        if args.task_id not in evidence['unfinished_task_ids']:
            raise ValueError('TASK_ALREADY_COMPLETED')
        updated = reserve_call(workflow, frame, brief, args.task_id, args.operation, recovery=args.recovery)
    validate('workflow', updated)
    if args.action == 'reopen':
        affected = set(draft['unfinished_task_ids']) - set(evidence.get('unfinished_task_ids', []))
        _research_helper().invalidate_dispatch(root, workflow, affected | reopen_ids)
    elif args.action == 'append':
        _research_helper().invalidate_dispatch(root, workflow, pending_only=True)
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
