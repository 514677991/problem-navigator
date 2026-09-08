"""Local court records and safe receipts; never spawns workers or decides a winner.

Host capability, fresh contexts, transcript isolation, and substantive neutrality
are host declarations, not facts this Python process can independently attest.
Exclusive writes and SHA256 seals detect changed artifacts; a party controlling
all files can rewrite a whole ledger. Preserve receipts outside the case when an
external integrity anchor is required. No provider calls or canonical-state writes.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import re
import sys

from jsonschema import Draft202012Validator
import yaml

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'references/court.schema.json'
DIMENSIONS = ('mechanism', 'capabilities', 'interfaces', 'adaptability', 'total_cost', 'failure_conditions', 'combination')
UPSTREAM = ('problem_frame', 'research_brief', 'evidence_package', 'readiness_pack')
RESIDUAL = {'UNRESOLVED', 'NEEDS_RESEARCH', 'NEEDS_VALUE'}
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')


def fail(code):
    raise ValueError('COURT_' + code)


def _schema(name, value):
    schema = json.loads(SCHEMA_PATH.read_text('utf-8'))
    if not Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/' + name}).is_valid(value):
        fail('INVALID_' + name.upper())


def _path(root, ref):
    root = Path(root).resolve()
    if not isinstance(ref, str) or not ref or Path(ref).is_absolute() or PureWindowsPath(ref).is_absolute() or ':' in ref or '\\' in ref:
        fail('PATH_OUTSIDE_PROJECT')
    path = (root / ref).resolve()
    if root not in path.parents or any(part in ('.', '..') for part in ref.split('/')):
        fail('PATH_OUTSIDE_PROJECT')
    return path


def _read(root, ref):
    try:
        raw = _path(root, ref).read_text('utf-8')
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return yaml.safe_load(raw)
    except (OSError, yaml.YAMLError, UnicodeError):
        fail('UNREADABLE_RECORD')


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _descriptor(root, ref):
    return {'ref': ref, 'sha256': hashlib.sha256(_path(root, ref).read_bytes()).hexdigest()}


def _verify(root, descriptor):
    if not isinstance(descriptor, dict) or set(descriptor) != {'ref', 'sha256'}:
        fail('INVALID_DESCRIPTOR')
    try:
        observed = _descriptor(root, descriptor['ref'])
    except OSError:
        fail('MISSING_RECORD')
    if observed != descriptor:
        fail('HASH_MISMATCH')
    return _read(root, descriptor['ref'])


def _write_once(root, ref, value):
    path = _path(root, ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(_bytes(value))
    except FileExistsError:
        fail('ALREADY_SEALED')
    return _descriptor(root, ref)


def _workflow_binding(workflow):
    # Later stages and downstream refs naturally change after selection. Upstream
    # paths, budget, counts, identity and policy remain bound to this case.
    result = {k: deepcopy(v) for k, v in workflow.items() if k not in {'next_stage', 'artifact_refs', 'blocking_reason'}}
    result['artifact_refs'] = {k: workflow.get('artifact_refs', {}).get(k) for k in UPSTREAM}
    return result


def _binding(workflow, frame, brief, evidence, readiness):
    return {name: _hash(value) for name, value in zip(('workflow',) + UPSTREAM, (_workflow_binding(workflow), frame, brief, evidence, readiness))}


def _host(declaration):
    _schema('host_declaration', declaration)
    if declaration['team_support'] == 'SUPPORTED':
        if declaration['mode'] != 'TEAM': fail('TEAM_REQUIRED')
        if not declaration['team_enabled']: fail('TEAM_UNAVAILABLE')
    elif declaration['mode'] != 'MANUAL_SESSIONS' or declaration['team_enabled']:
        fail('HOST_DECLARATION_MISMATCH')


def _guard_inputs(workflow, frame, brief, evidence, readiness):
    path = Path(__file__).resolve().parents[2] / 'problem-navigator/scripts/workflow_control.py'
    spec = importlib.util.spec_from_file_location('_court_workflow_guards', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.validate_evidence(workflow, frame, brief, evidence)
        module.validate_readiness(workflow, frame, brief, evidence, readiness)
    except Exception:
        fail('UPSTREAM_INVALID')
    if workflow.get('next_stage') != 'adversarial-option-selection' or frame.get('analysis_goal') != 'DECIDE' or readiness.get('status') != 'READY':
        fail('UPSTREAM_NOT_READY')


def _role(manifest, role_id):
    for role in manifest['roles']:
        if role['role_id'] == role_id: return role
    fail('UNKNOWN_ROLE')


def prepare_case(project_root, workflow_ref, host_declaration, case_id):
    root = Path(project_root).resolve()
    _host(host_declaration)
    if not ID.fullmatch(case_id): fail('INVALID_CASE_ID')
    workflow = _read(root, workflow_ref)
    values = [_read(root, workflow['artifact_refs'][key]) for key in UPSTREAM]
    frame, brief, evidence, readiness = values
    _guard_inputs(workflow, *values)
    candidate_ids = [c['candidate_id'] for c in evidence.get('candidates', [])]
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)): fail('CANDIDATE_COVERAGE')
    case_dir = '.problem-navigator/courts/' + workflow['workflow_id'] + '/' + case_id
    case_ref = case_dir + '/manifest.json'
    if _path(root, case_dir).exists(): fail('ALREADY_EXISTS')
    snapshot = {'workflow': _workflow_binding(workflow), **dict(zip(UPSTREAM, values))}
    snapshot_desc = {'ref': case_dir + '/snapshot.json', 'sha256': _hash(snapshot)}
    roles = [{'role_id': 'advocate-' + str(i + 1), 'kind': 'ADVOCATE', 'candidate_ids': [cid]} for i, cid in enumerate(candidate_ids)]
    roles += [{'role_id': role, 'kind': role.upper(), 'candidate_ids': candidate_ids} for role in ('redteam', 'feasibility', 'judge')]
    manifest = {'schema_version': 1, 'case_id': case_id, 'workflow_id': workflow['workflow_id'], 'workflow_ref': workflow_ref, 'host_declaration': deepcopy(host_declaration), 'input_hashes': _binding(workflow, *values), 'snapshot': snapshot_desc, 'candidate_ids': candidate_ids, 'theme_ids': sorted({task['theme_id'] for task in brief['tasks']}), 'roles': roles, 'max_rounds': 2, 'expression_budget_chars': 24000 + 2000 * len(candidate_ids) * len({t['theme_id'] for t in brief['tasks']}), 'integrity_boundary': 'HOST_DECLARED_CONTEXTS_AND_CAPABILITY; LOCAL_HASHES_NOT_EXTERNAL_ATTESTATION'}
    _schema('manifest', manifest)
    _write_once(root, snapshot_desc['ref'], snapshot)
    _write_once(root, case_ref, manifest)
    packets = []
    for role in roles:
        if role['kind'] != 'JUDGE': packets.append(role_packet(root, case_ref, role['role_id'], 'independent'))
    return {'case_id': case_id, 'case_ref': case_ref, 'case_sha256': _descriptor(root, case_ref)['sha256'], 'mode': host_declaration['mode'], 'status': 'PREPARED', 'packets': packets}


def _base(root, case_ref):
    manifest = _read(root, case_ref)
    _schema('manifest', manifest)
    _host(manifest['host_declaration'])
    case_dir = str(Path(case_ref).parent).replace('\\', '/')
    expected = '.problem-navigator/courts/' + manifest['workflow_id'] + '/' + manifest['case_id']
    if case_dir != expected or Path(case_ref).name != 'manifest.json': fail('CASE_PATH_MISMATCH')
    if _path(root, case_dir + '/invalidated.json').exists(): fail('INVALIDATED')
    if manifest['snapshot']['ref'] != case_dir + '/snapshot.json': fail('CASE_PATH_MISMATCH')
    snapshot = _verify(root, manifest['snapshot'])
    actual = {key: _hash(snapshot[key]) for key in ('workflow',) + UPSTREAM}
    if actual != manifest['input_hashes']: fail('INPUT_MISMATCH')
    candidate_ids = [v['candidate_id'] for v in snapshot['evidence_package']['candidates']]
    expected_roles = [{'role_id': 'advocate-' + str(i + 1), 'kind': 'ADVOCATE', 'candidate_ids': [cid]} for i, cid in enumerate(candidate_ids)] + [{'role_id': role, 'kind': role.upper(), 'candidate_ids': candidate_ids} for role in ('redteam', 'feasibility', 'judge')]
    if manifest['candidate_ids'] != candidate_ids or manifest['roles'] != expected_roles or manifest['theme_ids'] != sorted({t['theme_id'] for t in snapshot['research_brief']['tasks']}): fail('COVERAGE_MISMATCH')
    if manifest['expression_budget_chars'] != 24000 + 2000 * len(candidate_ids) * len(manifest['theme_ids']): fail('EXPRESSION_BUDGET')
    current_workflow = _read(root, manifest['workflow_ref'])
    current_inputs = [_read(root, current_workflow['artifact_refs'][key]) for key in UPSTREAM]
    if _binding(current_workflow, *current_inputs) != manifest['input_hashes']: fail('INPUT_MISMATCH')
    return manifest, snapshot, case_dir


def _seal_data(root, case_ref, case_dir, name, required=False):
    ref = case_dir + '/' + name + '.seal.json'
    if not _path(root, ref).exists():
        if required: fail('PAPERS_NOT_SEALED' if name == 'papers' else 'DEBATE_NOT_SEALED')
        return None, []
    seal = _read(root, ref)
    if seal.get('manifest') != _descriptor(root, case_ref): fail('HASH_MISMATCH')
    for dependency in seal.get('dependencies', []): _verify(root, dependency)
    records = [_verify(root, d) for d in seal['records']]
    return seal, records


def _load(root, case_ref):
    manifest, snapshot, case_dir = _base(root, case_ref)
    data = {}
    for name in ('papers', 'round-1-challenges', 'round-1-responses', 'round-2-challenges', 'round-2-responses', 'verdict'):
        seal, records = _seal_data(root, case_ref, case_dir, name)
        if seal is not None: data[name] = records
    _record_map([record for records in data.values() for record in records])
    if 'papers' in data: _validate_papers(root, case_ref, manifest, snapshot, data['papers'])
    for number in (1, 2):
        if f'round-{number}-challenges' in data: _validate_challenges(root, case_ref, manifest, snapshot, data, number, data[f'round-{number}-challenges'])
        if f'round-{number}-responses' in data: _validate_responses(root, case_ref, manifest, snapshot, data, number, data[f'round-{number}-responses'])
    if 'verdict' in data:
        if len(data['verdict']) != 1: fail('VERDICT_COVERAGE')
        _validate_verdict(root, case_ref, manifest, snapshot, data, data['verdict'][0])
    return manifest, snapshot, case_dir, data


def _record_map(records, key='record_id'):
    result = {r[key]: r for r in records}
    if len(result) != len(records): fail('DUPLICATE_ID')
    return result


def _residual(data, number):
    return {r['challenge_id'] for doc in data.get(f'round-{number}-responses', []) for r in doc['responses'] if r['disposition'] in RESIDUAL}


def _packet_value(root, case_ref, manifest, role_id, phase, number, data):
    if number not in (1, 2): fail('ROUND_LIMIT')
    role = _role(manifest, role_id)
    refs = [manifest['snapshot']]
    records = []
    if phase == 'independent':
        if role['kind'] == 'JUDGE': fail('JUDGE_MUST_WAIT')
        schema_name = 'paper'
    else:
        if 'papers' not in data: fail('PAPERS_NOT_SEALED')
        if phase == 'judge':
            if role['kind'] != 'JUDGE': fail('JUDGE_ROLE_REQUIRED')
            if 'round-1-responses' not in data or ('round-2-challenges' in data and 'round-2-responses' not in data): fail('DEBATE_NOT_SEALED')
            names = [n for n in data if n != 'verdict']
            schema_name = 'verdict'
        elif phase in ('challenge', 'response'):
            if role['kind'] == 'JUDGE': fail('JUDGE_CANNOT_PARTICIPATE')
            if number == 2:
                if 'round-1-responses' not in data: fail('DEBATE_NOT_SEALED')
                if not _residual(data, 1): fail('NO_RESIDUAL')
            names = ['papers']
            if number == 2: names += ['round-1-challenges', 'round-1-responses']
            if phase == 'response':
                if f'round-{number}-challenges' not in data: fail('CHALLENGES_NOT_SEALED')
                names += [f'round-{number}-challenges']
            schema_name = 'challenge_submission' if phase == 'challenge' else 'response_submission'
        else: fail('INVALID_PHASE')
        case_dir = str(Path(case_ref).parent).replace('\\', '/')
        for name in names:
            seal = _read(root, case_dir + '/' + name + '.seal.json')
            refs.extend(seal['records'])
            records.extend(r['record_id'] for r in data[name])
    instructions = ('Start a fresh independent context for Phase 1 or judging. Read only these neutral inputs and this role packet; never inherit the coordinator transcript. Phase 1 cannot read peers. Coordinator receives only IDs/status/refs/hashes, never arguments. Do not call research providers or write canonical workflow. Request missing facts through research; values through readiness. Use strong evidence-based arguments, disclose serious failure conditions, apply every dimension or explain non-applicability. Redteam tests reject-all and missing routes; feasibility tests bounded combinations. Do not infer truth or host independence from this file. Write the completed record to assigned_submission_ref. Only for an actual MANUAL_SESSIONS external Session without file access, return the full schema-valid record directly to that external Session user for saving and transfer; never send it to the coordinator or an automatic forwarding channel. After Phase 1, retain your own role context for challenge/response. Judge is a new context and never an advocate. Use court.schema.json for the output contract.')
    resources = Path(__file__).resolve().parents[1] / 'references'
    operating_instructions = {name: (resources / filename).read_text('utf-8') for name, filename in (('court_protocol', 'court-protocol.md'), ('role_packets', 'role-packets.md'))}
    submission_ref = str(Path(case_ref).parent).replace('\\', '/') + '/incoming/' + role_id + '-' + phase + '-' + str(number) + '.json'
    return {'schema_version': 1, 'case_id': manifest['case_id'], 'assigned_submission_ref': submission_ref, 'role': role, 'phase': phase, 'round': number if phase in ('challenge', 'response') else 0, 'instructions': instructions, 'operating_instructions': operating_instructions, 'input_refs': refs, 'record_ids': records, 'residual_challenge_ids': sorted(_residual(data, 1)) if number == 2 else [], 'dimensions': list(DIMENSIONS), 'expression_budget_chars': manifest['expression_budget_chars'], 'output_schema': {'definition': schema_name, 'schema': json.loads(SCHEMA_PATH.read_text('utf-8'))}, 'record_template': {'schema_version': 1, 'case_id': manifest['case_id'], 'record_id': 'REPLACE_WITH_UNIQUE_ID', 'role_id': role_id, 'context_id': 'REPLACE_WITH_ACTUAL_HOST_CONTEXT_ID', 'isolated_context': True, 'main_context_clean': True, 'input_packet_sha256': 'USE_PACKET_RECEIPT_SHA256'}}


def _packet_ref(case_ref, role_id, phase, number):
    case_dir = str(Path(case_ref).parent).replace('\\', '/')
    return case_dir + '/packets/' + role_id + '-' + phase + '-' + str(number) + '.json'


def role_packet(project_root, case_ref, role_id, phase, round_number=1):
    root = Path(project_root).resolve()
    manifest, snapshot, case_dir, data = _load(root, case_ref)
    value = _packet_value(root, case_ref, manifest, role_id, phase, round_number, data)
    ref = _packet_ref(case_ref, role_id, phase, round_number)
    if _path(root, ref).exists():
        if _read(root, ref) != value: fail('PACKET_MISMATCH')
        descriptor = _descriptor(root, ref)
    else: descriptor = _write_once(root, ref, value)
    return {'case_id': manifest['case_id'], 'role_id': role_id, 'status': 'PACKET_READY', 'packet_ref': ref, 'packet_sha256': descriptor['sha256'], 'assigned_submission_ref': value['assigned_submission_ref']}


def _common(root, case_ref, manifest, doc, schema_name, phase, number, data):
    _schema(schema_name, doc)
    if doc['case_id'] != manifest['case_id']: fail('CASE_MISMATCH')
    role = _role(manifest, doc['role_id'])
    if doc['context_id'] == manifest['host_declaration']['coordinator_context_id']: fail('COORDINATOR_CONTEXT')
    packet_value = _packet_value(root, case_ref, manifest, doc['role_id'], phase, number, data)
    ref = _packet_ref(case_ref, doc['role_id'], phase, number)
    if _read(root, ref) != packet_value or doc['input_packet_sha256'] != _descriptor(root, ref)['sha256']: fail('PACKET_MISMATCH')
    # One expression allowance per role and phase; equal allowance does not force filler.
    if len(json.dumps(doc, ensure_ascii=False)) > manifest['expression_budget_chars']: fail('EXPRESSION_BUDGET')
    return role


def _citations(snapshot, item):
    evidence_ids = {e['evidence_item_id'] for e in snapshot['evidence_package']['evidence_items']}
    limitation_ids = {e['limitation_id'] for e in snapshot['evidence_package']['limitations']}
    if not set(item['evidence_item_ids']) <= evidence_ids or not set(item['limitation_ids']) <= limitation_ids: fail('EVIDENCE_REFERENCE')
    if not item['evidence_item_ids'] and not item['limitation_ids']: fail('BASIS_REQUIRED')


def _validate_papers(root, case_ref, manifest, snapshot, papers):
    expected = {r['role_id'] for r in manifest['roles'] if r['kind'] != 'JUDGE'}
    if {p.get('role_id') for p in papers} != expected or len(papers) != len(expected): fail('PAPER_COVERAGE')
    contexts = []
    all_claims = []
    _record_map(papers)
    for paper in papers:
        role = _common(root, case_ref, manifest, paper, 'paper', 'independent', 1, {})
        contexts.append(paper['context_id'])
        if paper['candidate_ids'] != role['candidate_ids']: fail('CANDIDATE_COVERAGE')
        if {d['dimension'] for d in paper['dimensions']} != set(DIMENSIONS) or len(paper['dimensions']) != len(DIMENSIONS): fail('DIMENSION_COVERAGE')
        for claim in paper['claims']: _citations(snapshot, claim); all_claims.append(claim)
        for dimension in paper['dimensions']: _citations(snapshot, dimension)
        if role['kind'] == 'REDTEAM' and not paper.get('alternative_test', '').strip(): fail('REDTEAM_COVERAGE')
        if role['kind'] == 'FEASIBILITY' and not paper.get('combination_test', '').strip(): fail('FEASIBILITY_COVERAGE')
    _record_map(all_claims, 'claim_id')
    if len(contexts) != len(set(contexts)): fail('CONTEXT_NOT_INDEPENDENT')


def _validate_challenges(root, case_ref, manifest, snapshot, data, number, submissions):
    if 'papers' not in data: fail('PAPERS_NOT_SEALED')
    papers = _record_map(data['papers'])
    authors = {p['role_id']: p for p in data['papers']}
    if number == 1 and ({d.get('role_id') for d in submissions} != set(authors) or len(submissions) != len(authors)): fail('CHALLENGER_COVERAGE')
    _record_map(submissions, 'role_id'); _record_map(submissions)
    previous = {q['challenge_id']: q for s in data.get('round-1-challenges', []) for q in s['challenges']}
    challenges = []
    for doc in submissions:
        _common(root, case_ref, manifest, doc, 'challenge_submission', 'challenge', number, data)
        if doc['context_id'] != authors[doc['role_id']]['context_id']: fail('CONTEXT_CHANGED')
        for challenge in doc['challenges']:
            target = papers.get(challenge['target_paper_id'])
            if not target or target['role_id'] == doc['role_id'] or challenge['target_claim_id'] not in {c['claim_id'] for c in target['claims']}: fail('CHALLENGE_TARGET')
            if challenge['theme_id'] not in manifest['theme_ids']: fail('THEME_REFERENCE')
            _citations(snapshot, challenge)
            prior_id = challenge.get('prior_challenge_id')
            if number == 1 and prior_id: fail('UNEXPECTED_PRIOR_CHALLENGE')
            if number == 2:
                if prior_id not in _residual(data, 1): fail('NON_RESIDUAL_CHALLENGE')
                prior = previous[prior_id]
                if any(challenge[k] != prior[k] for k in ('target_paper_id', 'target_claim_id', 'theme_id')): fail('RESIDUAL_TARGET_CHANGED')
                if challenge['challenge_id'] in previous: fail('DUPLICATE_ID')
            challenges.append(challenge)
    _record_map(challenges, 'challenge_id')
    if number == 1:
        covered = {(q['target_paper_id'], q['theme_id']) for q in challenges}
        if covered != {(pid, theme) for pid in papers for theme in manifest['theme_ids']}: fail('CHALLENGE_COVERAGE')
        candidate_papers = {p['record_id'] for p in data['papers'] if _role(manifest, p['role_id'])['kind'] == 'ADVOCATE'}
        for reviewer in ('redteam', 'feasibility'):
            reviewed = {(q['target_paper_id'], q['theme_id']) for doc in submissions if doc['role_id'] == reviewer for q in doc['challenges']}
            if not {(pid, theme) for pid in candidate_papers for theme in manifest['theme_ids']} <= reviewed: fail('REVIEWER_COVERAGE')
    elif {q['prior_challenge_id'] for q in challenges} != _residual(data, 1) or len(challenges) != len(_residual(data, 1)):
        fail('RESIDUAL_COVERAGE')


def _validate_responses(root, case_ref, manifest, snapshot, data, number, submissions):
    key = f'round-{number}-challenges'
    if key not in data: fail('CHALLENGES_NOT_SEALED')
    questions = {q['challenge_id']: q for doc in data[key] for q in doc['challenges']}
    papers = _record_map(data['papers'])
    authors = {p['role_id']: p for p in data['papers']}
    _record_map(submissions, 'role_id'); _record_map(submissions)
    responses = []
    for doc in submissions:
        _common(root, case_ref, manifest, doc, 'response_submission', 'response', number, data)
        if doc['context_id'] != authors[doc['role_id']]['context_id']: fail('CONTEXT_CHANGED')
        for response in doc['responses']:
            question = questions.get(response['challenge_id'])
            if not question or papers[question['target_paper_id']]['role_id'] != doc['role_id']: fail('RESPONSE_TARGET')
            _citations(snapshot, response)
            if not set(response['withdrawn_claim_ids']) <= {c['claim_id'] for c in authors[doc['role_id']]['claims']}: fail('WITHDRAWAL_TARGET')
            if response['disposition'] == 'WITHDRAWN' and not response['withdrawn_claim_ids']: fail('WITHDRAWAL_REQUIRED')
            responses.append(response)
    if set(_record_map(responses, 'challenge_id')) != set(questions): fail('RESPONSE_COVERAGE')


def _validate_verdict(root, case_ref, manifest, snapshot, data, verdict):
    _common(root, case_ref, manifest, verdict, 'verdict', 'judge', 1, data)
    if verdict['role_id'] != 'judge' or verdict['context_id'] in {p['context_id'] for p in data['papers']}: fail('JUDGE_CONTEXT_NOT_INDEPENDENT')
    expected_records = {r['record_id'] for key, docs in data.items() if key != 'verdict' for r in docs}
    if set(verdict['reviewed_record_ids']) != expected_records or len(verdict['reviewed_record_ids']) != len(expected_records): fail('JUDGE_CORPUS_COVERAGE')
    claims = {c['claim_id'] for p in data['papers'] for c in p['claims']}
    if not set(verdict['surviving_claim_ids']) <= claims: fail('VERDICT_CLAIM_REFERENCE')
    withdrawals = {cid for key, docs in data.items() if key.endswith('responses') for d in docs for r in d['responses'] for cid in r['withdrawn_claim_ids']}
    if set(verdict['surviving_claim_ids']) & withdrawals: fail('WITHDRAWN_CLAIM_SURVIVES')
    last_round = 2 if 'round-2-responses' in data else 1
    if set(verdict['unresolved_challenge_ids']) != _residual(data, last_round): fail('RESIDUAL_VERDICT_COVERAGE')
    dispositions = _record_map(verdict['residual_dispositions'], 'challenge_id')
    if set(dispositions) != _residual(data, last_round): fail('RESIDUAL_DISPOSITION_COVERAGE')
    for disposition in dispositions.values(): _citations(snapshot, disposition)
    summary = verdict['neutral_summary']
    selected = set(summary['selected_candidate_ids'])
    if summary['status'] != verdict['outcome'] or not selected <= set(manifest['candidate_ids']): fail('VERDICT_SELECTION')
    if verdict['outcome'] == 'SELECTED':
        if not selected or not verdict['surviving_claim_ids']: fail('VERDICT_SELECTION')
        if any(v['disposition'] != 'NON_BLOCKING' for v in dispositions.values()): fail('ROUTING_REQUIRED')
        related = {cid for paper in data['papers'] for claim in paper['claims'] if claim['claim_id'] in verdict['surviving_claim_ids'] for cid in paper['candidate_ids']}
        if not selected <= related: fail('SELECTED_CLAIM_COVERAGE')
        if any(r['disposition'] in {'NEEDS_RESEARCH', 'NEEDS_VALUE'} for d in data[f'round-{last_round}-responses'] for r in d['responses']): fail('ROUTING_REQUIRED')
    elif selected: fail('VERDICT_SELECTION')
    rejects = _record_map(verdict['rejected_candidates'], 'candidate_id')
    if set(rejects) != set(manifest['candidate_ids']) - selected: fail('REJECTION_COVERAGE')
    for rejection in rejects.values():
        if not set(rejection['claim_ids']) <= claims: fail('VERDICT_CLAIM_REFERENCE')


def _incoming(root, case_ref, submission_refs):
    records = [_read(root, ref) for ref in submission_refs]
    if any(isinstance(doc, dict) and (doc.get('main_context_clean') is False or doc.get('isolated_context') is False) for doc in records):
        invalidate_case(root, case_ref, 'CONTEXT_LEAK')
        fail('CONTEXT_LEAK')
    return records


def _seal(root, case_ref, case_dir, name, records, dependencies):
    ref = case_dir + '/' + name + '.seal.json'
    if _path(root, ref).exists(): fail('ALREADY_SEALED')
    existing = []
    for path in _path(root, case_dir).glob('*.seal.json'):
        seal = _read(root, path.relative_to(root).as_posix())
        existing.extend(_verify(root, d) for d in seal['records'])
    _record_map(existing + records)
    records = sorted(records, key=lambda doc: hashlib.sha256((doc['case_id'] + ':' + doc['role_id']).encode('utf-8')).hexdigest())
    descriptors = [_write_once(root, case_dir + '/sealed/' + name + '/' + str(i + 1) + '.json', doc) for i, doc in enumerate(records)]
    seal = {'schema_version': 1, 'manifest': _descriptor(root, case_ref), 'dependencies': [_descriptor(root, case_dir + '/' + d + '.seal.json') for d in dependencies], 'records': descriptors, 'presentation_order': [r['role_id'] for r in records]}
    descriptor = _write_once(root, ref, seal)
    return {'status': name.upper().replace('-', '_') + '_SEALED', 'seal_ref': ref, 'seal_sha256': descriptor['sha256'], 'record_ids': [r['record_id'] for r in records], 'records': descriptors}


def seal_papers(project_root, case_ref, submission_refs):
    root = Path(project_root).resolve()
    manifest, snapshot, case_dir, data = _load(root, case_ref)
    if 'papers' in data: fail('ALREADY_SEALED')
    papers = _incoming(root, case_ref, submission_refs)
    _validate_papers(root, case_ref, manifest, snapshot, papers)
    return _seal(root, case_ref, case_dir, 'papers', papers, [])


def seal_challenges(project_root, case_ref, round_number, submission_refs):
    root = Path(project_root).resolve()
    manifest, snapshot, case_dir, data = _load(root, case_ref)
    if 'verdict' in data or _path(root, case_dir + '/packets/judge-judge-1.json').exists(): fail('JUDGMENT_STARTED')
    name = f'round-{round_number}-challenges'
    if name in data: fail('ALREADY_SEALED')
    docs = _incoming(root, case_ref, submission_refs)
    _validate_challenges(root, case_ref, manifest, snapshot, data, round_number, docs)
    return _seal(root, case_ref, case_dir, name, docs, ['papers'] + (['round-1-challenges', 'round-1-responses'] if round_number == 2 else []))


def seal_responses(project_root, case_ref, round_number, submission_refs):
    root = Path(project_root).resolve()
    manifest, snapshot, case_dir, data = _load(root, case_ref)
    name = f'round-{round_number}-responses'
    if name in data: fail('ALREADY_SEALED')
    docs = _incoming(root, case_ref, submission_refs)
    _validate_responses(root, case_ref, manifest, snapshot, data, round_number, docs)
    return _seal(root, case_ref, case_dir, name, docs, ['papers', f'round-{round_number}-challenges'])


def seal_verdict(project_root, case_ref, submission_ref):
    root = Path(project_root).resolve()
    manifest, snapshot, case_dir, data = _load(root, case_ref)
    if 'verdict' in data: fail('ALREADY_SEALED')
    doc = _incoming(root, case_ref, [submission_ref])[0]
    _validate_verdict(root, case_ref, manifest, snapshot, data, doc)
    return _seal(root, case_ref, case_dir, 'verdict', [doc], list(data))


def check_case(project_root, case_ref):
    manifest, snapshot, case_dir, data = _load(Path(project_root).resolve(), case_ref)
    return {'case_id': manifest['case_id'], 'case_ref': case_ref, 'mode': manifest['host_declaration']['mode'], 'status': 'VERDICT_SEALED' if 'verdict' in data else ('DEBATE_SEALED' if 'round-1-responses' in data else 'PAPERS_SEALED' if 'papers' in data else 'PREPARED'), 'sealed_phases': list(data)}


def neutral_outcome(project_root, case_ref):
    manifest, snapshot, case_dir, data = _load(Path(project_root).resolve(), case_ref)
    if 'verdict' not in data: fail('VERDICT_NOT_SEALED')
    return {'case_id': manifest['case_id'], **deepcopy(data['verdict'][0]['neutral_summary'])}


def invalidate_case(project_root, case_ref, reason_code):
    root = Path(project_root).resolve()
    if reason_code not in {'CONTEXT_LEAK', 'HOST_DECLARATION_INVALID', 'UPSTREAM_CHANGED', 'USER_STOPPED'}: fail('INVALID_REASON_CODE')
    manifest, snapshot, case_dir = _base(root, case_ref)
    descriptor = _write_once(root, case_dir + '/invalidated.json', {'case_id': manifest['case_id'], 'reason_code': reason_code})
    return {'case_id': manifest['case_id'], 'status': 'INVALIDATED', **descriptor}


def validate_decision_review(project_root, workflow, frame, brief, evidence, readiness, decision):
    """Public workflow guard: validate declared mode and actual current sealed case."""
    review = decision.get('review')
    if not isinstance(review, dict): fail('REVIEW_REQUIRED')
    if review.get('mode') == 'DIRECT':
        if set(review) != {'mode', 'reason'} or not isinstance(review['reason'], str) or not review['reason'].strip(): fail('REVIEW_REQUIRED')
        if len(evidence.get('candidates', [])) != 1 or frame.get('court_required') is True: fail('COURT_REQUIRED')
        if decision.get('selected_candidate_ids') != [evidence['candidates'][0]['candidate_id']]: fail('VERDICT_SELECTION')
        return
    if set(review) != {'mode', 'case_ref'} or review.get('mode') not in {'TEAM', 'MANUAL_SESSIONS'}: fail('REVIEW_REQUIRED')
    if project_root is None: fail('PROJECT_ROOT_REQUIRED')
    manifest, snapshot, case_dir, data = _load(Path(project_root).resolve(), review['case_ref'])
    if manifest['host_declaration']['mode'] != review['mode']: fail('MODE_MISMATCH')
    if manifest['input_hashes'] != _binding(workflow, frame, brief, evidence, readiness): fail('INPUT_MISMATCH')
    if 'verdict' not in data: fail('VERDICT_NOT_SEALED')
    summary = data['verdict'][0]['neutral_summary']
    if summary['status'] != 'SELECTED' or any(decision.get(k) != v for k, v in summary.items()): fail('VERDICT_MISMATCH')
    for key, value in {'workflow_id': workflow['workflow_id'], 'readiness_pack_id': readiness['readiness_pack_id'], 'readiness_pack_version': readiness['readiness_pack_version'], 'evidence_revision': evidence['evidence_revision']}.items():
        if decision.get(key) != value: fail('INPUT_MISMATCH')


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        fail('INVALID_ARGUMENTS')


def main(argv=None):
    parser = _SafeParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--workflow', required=True)
    prepare.add_argument('--host-declaration', required=True)
    prepare.add_argument('--case-id', required=True)
    for action in ('packet', 'seal-papers', 'seal-challenges', 'seal-responses', 'seal-verdict', 'check', 'outcome', 'invalidate'):
        item = sub.add_parser(action)
        item.add_argument('--case', required=True)
        if action == 'packet':
            item.add_argument('--role', required=True)
            item.add_argument('--phase', choices=('independent', 'challenge', 'response', 'judge'), required=True)
            item.add_argument('--round', type=int, default=1)
        if action in ('seal-challenges', 'seal-responses'): item.add_argument('--round', type=int, choices=(1, 2), required=True)
        if action.startswith('seal-'): item.add_argument('--submission', action='append' if action != 'seal-verdict' else 'store', required=True)
        if action == 'invalidate': item.add_argument('--reason-code', required=True)
    try:
        args = parser.parse_args(argv)
        root = args.project_root.resolve()
        if args.action == 'prepare': result = prepare_case(root, args.workflow, _read(root, args.host_declaration), args.case_id)
        elif args.action == 'packet': result = role_packet(root, args.case, args.role, args.phase, args.round)
        elif args.action == 'seal-papers': result = seal_papers(root, args.case, args.submission)
        elif args.action == 'seal-challenges': result = seal_challenges(root, args.case, args.round, args.submission)
        elif args.action == 'seal-responses': result = seal_responses(root, args.case, args.round, args.submission)
        elif args.action == 'seal-verdict': result = seal_verdict(root, args.case, args.submission)
        elif args.action == 'check': result = check_case(root, args.case)
        elif args.action == 'outcome': result = neutral_outcome(root, args.case)
        else: result = invalidate_case(root, args.case, args.reason_code)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'COURT_[A-Z_]+', str(exc)) else 'COURT_INVALID_INPUT'
        print(json.dumps({'status': 'ERROR', 'code': code}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
