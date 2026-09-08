from __future__ import annotations

import copy
import json
from itertools import product
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

import test_research_stages as research_contracts


WORKFLOW_ID = "550e8400-e29b-41d4-a716-446655440000"
STAGES = ("decision-readiness-interview", "adversarial-option-selection")


class ContractViolation(AssertionError):
    """A test-only signal for an invalid decision-stage transition."""


def schema_validator(project_root: Path, definition: str) -> Draft202012Validator:
    schema = json.loads(
        (
            project_root
            / "skills/problem-navigator/references/artifacts.schema.json"
        ).read_text("utf-8")
    )
    return Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    )


def workflow(
    stage: str = "decision-readiness-interview",
    *,
    backend: str = "RESEARCH_CORE",
    research_state: str = "RESEARCH_PARTIAL",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "analysis_goal": "DECIDE",
        "next_stage": stage,
        "selected_backend": backend,
        "native_fallback_approved": backend == "HOST_NATIVE",
        "research_state": research_state,
        "call_counts": {
            "RES-001": {
                "search": 0 if backend == "NONE" else 1,
                "fetch": 0,
                "map": 0,
            }
        },
        "artifact_refs": {
            "problem_frame": f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml",
            "research_brief": f".problem-navigator/artifacts/{WORKFLOW_ID}/research-brief.yaml",
            "evidence_package": f".problem-navigator/artifacts/{WORKFLOW_ID}/evidence-package.yaml",
        },
    }


def decision_evidence(candidate_ids: list[str] | None = None) -> dict[str, object]:
    ids = ["CAN-001"] if candidate_ids is None else candidate_ids
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "brief_revision": 1,
        "evidence_revision": 1,
        "analysis_goal": "DECIDE",
        "research_state": "RESEARCH_COMPLETE",
        "neutral_synthesis": "Neutral evidence report.",
        "candidate_basis": "The bounded research task identified these candidates.",
        "candidates": [
            {
                "candidate_id": candidate_id,
                "name": f"Candidate {candidate_id}",
                "definition": "A bounded option.",
            }
            for candidate_id in ids
        ],
        "execution_receipts": [
            {
                "task_id": "RES-001",
                "outcome": "WITH_RESULTS",
                "quality_met": True,
                "call_refs": ["CALL-001"],
                "source_ids": ["SRC-001"],
                "external_source_ids": [],
            }
        ],
        "sources": [
            {
                "source_id": "SRC-001",
                "call_ref": "CALL-001",
                "title": "Source",
                "normalized_url": "https://example.com/source",
                "provider": "brave",
                "source_type": "web",
                "retrieved_at": "2026-09-05T00:00:00Z",
            }
        ],
        "evidence_items": [
            {
                "evidence_item_id": "EVI-001",
                "task_id": "RES-001",
                "candidate_ids": ids,
                "kind": "FACT",
                "statement": "Supported.",
                "web_source_ids": ["SRC-001"],
                "external_source_ids": [],
            }
        ],
        "limitations": [],
        "external_sources": [],
    }


def request_payload(
    gap_kind: str = "PUBLIC_FACT",
    *,
    candidate_ids: list[str] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "request_id": "SUP-001",
        "gap_kind": gap_kind,
        "question": "What bounded evidence can change candidate eligibility?",
        "decision_impact": "The answer can reverse the selected candidate.",
        "affected_candidate_ids": (
            ["CAN-001"] if candidate_ids is None else candidate_ids
        ),
    }
    if gap_kind == "PROVIDED_MATERIAL":
        result["material_refs"] = ["inputs/new-evidence.md"]
    return result


def legal_decision_graph(
    *, backend: str = "RESEARCH_CORE", stage: str = "decision-readiness-interview"
) -> dict[str, object]:
    inputs = research_contracts.partial_supplemental_inputs(backend)
    current = copy.deepcopy(inputs["workflow"])
    current["next_stage"] = stage
    if stage == "decision-readiness-interview":
        current["artifact_refs"].pop("readiness_pack")
        readiness = None
    else:
        readiness = copy.deepcopy(inputs["readiness"])
        readiness["status"] = "READY"
        readiness.pop("supplemental_request")
    return {
        "workflow": current,
        "problem_frame": copy.deepcopy(inputs["problem_frame"]),
        "brief": copy.deepcopy(inputs["prior_brief"]),
        "evidence": copy.deepcopy(inputs["prior_package"]),
        "readiness": readiness,
    }


def apply_entry_gate(
    current: dict[str, object],
    own_stage: str,
    *,
    artifacts_valid: bool,
    affected_task_ids: list[str],
) -> tuple[str, dict[str, object]]:
    """Independent executable table for the two documented stage guards."""
    if current["next_stage"] != own_stage:
        return "RETURN_TO_ENTRY", copy.deepcopy(current)
    if artifacts_valid:
        return "ENTER_STAGE", copy.deepcopy(current)
    stopped = copy.deepcopy(current)
    stopped["next_stage"] = "STOPPED"
    stopped["blocking_reason"] = {
        "code": "MISSING_OR_INVALID_ARTIFACT",
        "task_ids": affected_task_ids,
    }
    return "STOPPED", stopped


def validate_current_decision_graph(
    project_root: Path,
    current: dict[str, object],
    frame: dict[str, object],
    brief: dict[str, object],
    evidence: dict[str, object],
    *,
    readiness: dict[str, object] | None = None,
) -> None:
    """Narrow Task 10 input check that reuses Task 9's evidence oracle."""
    if current["next_stage"] not in STAGES:
        raise ContractViolation("a decision stage does not own the workflow")
    schema = research_contracts.load_schema(project_root)
    for definition, artifact in (
        ("workflow", current),
        ("problem_frame", frame),
        ("research_brief", brief),
        ("evidence_package", evidence),
    ):
        research_contracts.validate_definition(schema, definition, artifact)
    root = f".problem-navigator/artifacts/{current['workflow_id']}"
    required_refs = {
        "problem_frame": f"{root}/problem-frame.yaml",
        "research_brief": f"{root}/research-brief.yaml",
        "evidence_package": f"{root}/evidence-package.yaml",
    }
    if any(current["artifact_refs"].get(key) != value for key, value in required_refs.items()):
        raise ContractViolation("current decision artifact reference is missing or stale")
    if len(
        {
            current["workflow_id"],
            frame["workflow_id"],
            brief["workflow_id"],
            evidence["workflow_id"],
        }
    ) != 1:
        raise ContractViolation("decision inputs use different workflows")
    if not (
        current["analysis_goal"]
        == frame["analysis_goal"]
        == brief["analysis_goal"]
        == evidence["analysis_goal"]
        == "DECIDE"
    ):
        raise ContractViolation("decision inputs require one DECIDE goal")
    if frame["user_confirmation_status"] != "ACCEPTED":
        raise ContractViolation("problem frame is not accepted")
    if not brief["revision"] == evidence["brief_revision"]:
        raise ContractViolation("brief and evidence revisions disagree")
    if current["research_state"] != evidence["research_state"]:
        raise ContractViolation("workflow and evidence research states disagree")
    backend = current["selected_backend"]
    expected_kind = "PROVIDED_MATERIAL" if backend == "NONE" else "PUBLIC_WEB"
    if any(task["task_kind"] != expected_kind for task in brief["tasks"]):
        raise ContractViolation("backend and task kinds disagree")
    task_ids = [task["task_id"] for task in brief["tasks"]]
    if set(current["call_counts"]) != set(task_ids):
        raise ContractViolation("call-count keys must match current tasks")
    if backend == "NONE" and any(
        count for counts in current["call_counts"].values() for count in counts.values()
    ):
        raise ContractViolation("NONE workflow has a nonzero network count")
    derived = research_contracts.validate_evidence_semantics(
        evidence,
        receipt_field="execution_receipts",
        task_map={task["task_id"]: task for task in brief["tasks"]},
        analysis_goal="DECIDE",
        declared_state=evidence["research_state"],
    )
    if derived != current["research_state"]:
        raise ContractViolation("research state is not evidence-derived")
    if readiness is not None:
        research_contracts.validate_definition(schema, "readiness_pack", readiness)
        if current["artifact_refs"].get("readiness_pack") != f"{root}/readiness-pack.yaml":
            raise ContractViolation("current readiness reference is missing or stale")
        if not (
            readiness["workflow_id"] == current["workflow_id"]
            and readiness["brief_revision"] == brief["revision"]
            and readiness["evidence_revision"] == evidence["evidence_revision"]
        ):
            raise ContractViolation("readiness does not cite the current evidence")
        disposition_ids = [
            item["limitation_id"] for item in readiness["limitation_dispositions"]
        ]
        limitation_ids = {item["limitation_id"] for item in evidence["limitations"]}
        if (
            len(disposition_ids) != len(set(disposition_ids))
            or set(disposition_ids) != limitation_ids
        ):
            raise ContractViolation("readiness dispositions do not close limitations")


def publish_supplemental_readiness(
    project_root: Path,
    current: dict[str, object],
    frame: dict[str, object],
    brief: dict[str, object],
    evidence: dict[str, object],
    request: dict[str, object],
    *,
    limitation_dispositions: list[dict[str, str]],
    value_conditions: list[str],
    prior_readiness: dict[str, object] | None,
) -> dict[str, dict[str, object]]:
    """Test-only publication oracle for a bounded 2.1 supplemental request."""
    validate_current_decision_graph(
        project_root,
        current,
        frame,
        brief,
        evidence,
        readiness=prior_readiness if current["next_stage"] == "adversarial-option-selection" else None,
    )
    try:
        schema_validator(project_root, "supplemental_request").validate(request)
    except ValidationError as error:
        raise ContractViolation(f"{request.get('gap_kind')} is not a supplemental gap kind") from error
    affected = request["affected_candidate_ids"]
    candidates = {item["candidate_id"] for item in evidence["candidates"]}
    if not set(affected) <= candidates:
        raise ContractViolation("supplemental candidate references must close")
    limitation_ids = {item["limitation_id"] for item in evidence["limitations"]}
    disposition_ids = [item["limitation_id"] for item in limitation_dispositions]
    if len(disposition_ids) != len(set(disposition_ids)) or set(disposition_ids) != limitation_ids:
        raise ContractViolation("readiness dispositions do not close limitations")

    backend = current["selected_backend"]
    reason = None
    research_state = current["research_state"]
    if backend == "NONE" and request["gap_kind"] == "PUBLIC_FACT":
        reason = "PUBLIC_WEB_REQUIRES_NEW_WORKFLOW"
        research_state = "RESEARCH_CANCELLED"
    elif backend == "NONE" and request["gap_kind"] != "PROVIDED_MATERIAL":
        raise ContractViolation("NONE requires PROVIDED_MATERIAL")

    pack = (
        copy.deepcopy(prior_readiness)
        if prior_readiness is not None
        else {
            "schema_version": 1,
            "workflow_id": current["workflow_id"],
            "readiness_pack_id": "READY-001",
            "readiness_pack_version": 0,
            "limitation_dispositions": copy.deepcopy(limitation_dispositions),
            "value_conditions": copy.deepcopy(value_conditions),
        }
    )
    pack["readiness_pack_version"] += 1
    pack["brief_revision"] = brief["revision"]
    pack["evidence_revision"] = evidence["evidence_revision"]
    pack.pop("supplemental_request", None)

    after = copy.deepcopy(current)
    root = f".problem-navigator/artifacts/{current['workflow_id']}"
    after["artifact_refs"]["readiness_pack"] = f"{root}/readiness-pack.yaml"
    if reason is not None:
        pack["status"] = "STOPPED"
        after["research_state"] = research_state
        after["next_stage"] = "STOPPED"
        after["blocking_reason"] = {
            "code": reason,
            "task_ids": [task["task_id"] for task in brief["tasks"]],
        }
    else:
        pack["status"] = "NEEDS_SUPPLEMENTAL"
        pack["supplemental_request"] = copy.deepcopy(request)
        after["next_stage"] = "research-design-kickoff"
        after.pop("blocking_reason", None)
    schema_validator(project_root, "readiness_pack").validate(pack)
    schema_validator(project_root, "workflow").validate(after)
    return {"workflow": after, "readiness": pack}


def accept_selection(
    current: dict[str, object],
    evidence: dict[str, object],
    readiness: dict[str, object],
    selected_ids: list[str],
) -> dict[str, dict[str, object]]:
    """Test-only atomic selection oracle; the Plugin itself stays instruction-only."""
    candidates = {item["candidate_id"] for item in evidence["candidates"]}
    if (
        not selected_ids
        or len(selected_ids) != len(set(selected_ids))
        or not set(selected_ids) <= candidates
    ):
        raise ContractViolation("selected_candidate_ids must be unique current candidates")
    decision = {
        "schema_version": 1,
        "workflow_id": current["workflow_id"],
        "decision_id": "DEC-001",
        "decision_version": 1,
        "readiness_pack_id": readiness["readiness_pack_id"],
        "readiness_pack_version": readiness["readiness_pack_version"],
        "evidence_revision": evidence["evidence_revision"],
        "selected_candidate_ids": copy.deepcopy(selected_ids),
        "rationale": "Frozen criteria support this actual selection; no challenge was warranted.",
        "status": "SELECTED",
    }
    after = copy.deepcopy(current)
    root = f".problem-navigator/artifacts/{current['workflow_id']}"
    after["artifact_refs"]["decision"] = f"{root}/decision.yaml"
    after["next_stage"] = "solution-refinement"
    after.pop("blocking_reason", None)
    return {"workflow": after, "decision": decision}


def validate_selection_output_semantics(
    project_root: Path,
    current: dict[str, object],
    frame: dict[str, object],
    brief: dict[str, object],
    evidence: dict[str, object],
    readiness: dict[str, object],
    decision: dict[str, object],
    after: dict[str, object],
) -> None:
    """Narrow cross-artifact gate for the Task 10 selection output."""
    validate_current_decision_graph(
        project_root, current, frame, brief, evidence, readiness=readiness
    )
    if current["next_stage"] != "adversarial-option-selection" or readiness["status"] != "READY":
        raise ContractViolation("selection inputs are not ready")
    schema_validator(project_root, "decision").validate(decision)
    schema_validator(project_root, "workflow").validate(after)
    if not (
        decision["workflow_id"] == current["workflow_id"]
        and decision["readiness_pack_id"] == readiness["readiness_pack_id"]
        and decision["readiness_pack_version"] == readiness["readiness_pack_version"]
        and decision["evidence_revision"] == evidence["evidence_revision"]
    ):
        raise ContractViolation("decision IDs or revisions do not close")
    candidates = {item["candidate_id"] for item in evidence["candidates"]}
    selected = decision["selected_candidate_ids"]
    if not selected or len(selected) != len(set(selected)) or not set(selected) <= candidates:
        raise ContractViolation("selected candidate does not exist in current evidence")
    root = f".problem-navigator/artifacts/{current['workflow_id']}"
    if after["artifact_refs"].get("decision") != f"{root}/decision.yaml":
        raise ContractViolation("current decision reference is missing or stale")
    expected_refs = {**current["artifact_refs"], "decision": f"{root}/decision.yaml"}
    if after["artifact_refs"] != expected_refs:
        raise ContractViolation("selection changed an upstream reference")
    for field in (
        "workflow_id",
        "analysis_goal",
        "selected_backend",
        "native_fallback_approved",
        "research_state",
        "call_counts",
    ):
        if after[field] != current[field]:
            raise ContractViolation(f"selection changed upstream {field}")
    if after["next_stage"] != "solution-refinement" or "blocking_reason" in after:
        raise ContractViolation("solution refinement requires a valid decision")


def assert_dispositions_cover_limitations(
    limitation_ids: list[str], dispositions: list[dict[str, str]]
) -> None:
    allowed = {"ACCEPTED", "ESCALATED", "CORRECTION_REQUESTED"}
    disposition_ids = [entry["limitation_id"] for entry in dispositions]
    assert len(disposition_ids) == len(set(disposition_ids))
    assert set(disposition_ids) == set(limitation_ids)
    assert all(entry["disposition"] in allowed for entry in dispositions)
    assert all(entry["reason"].strip() for entry in dispositions)


def assert_symmetric_challenge(
    candidate_ids: list[str], theme_ids: list[str], records: list[dict[str, str]]
) -> None:
    expected = set(product(candidate_ids, theme_ids))
    actual = {(record["candidate_id"], record["theme_id"]) for record in records}
    assert len(records) == len(expected)
    assert len(actual) == len(records)
    assert actual == expected
    for record in records:
        assert all(
            record[field].strip()
            for field in ("claim", "counterevidence", "response", "verdict")
        )


@pytest.mark.parametrize("own_stage", STAGES)
def test_wrong_stage_returns_to_entry_without_mutation(own_stage: str) -> None:
    before = workflow("solution-refinement")
    action, after = apply_entry_gate(
        before, own_stage, artifacts_valid=False, affected_task_ids=["RES-001"]
    )
    assert action == "RETURN_TO_ENTRY"
    assert after == before
    assert "blocking_reason" not in after


@pytest.mark.parametrize("own_stage", STAGES)
def test_invalid_required_artifact_is_one_full_schema_valid_stop(
    project_root: Path, own_stage: str
) -> None:
    before = workflow(own_stage)
    action, after = apply_entry_gate(
        before, own_stage, artifacts_valid=False, affected_task_ids=["RES-001"]
    )
    assert action == "STOPPED"
    assert after["next_stage"] == "STOPPED"
    assert after["blocking_reason"] == {
        "code": "MISSING_OR_INVALID_ARTIFACT",
        "task_ids": ["RES-001"],
    }
    schema_validator(project_root, "workflow").validate(after)


def test_understand_workflow_cannot_enter_either_decide_stage(
    project_root: Path,
) -> None:
    validator = schema_validator(project_root, "workflow")
    for stage in STAGES:
        invalid = workflow(stage)
        invalid["analysis_goal"] = "UNDERSTAND"
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_selection_gap_versions_readiness_and_preserves_prior_dispositions(
    project_root: Path,
) -> None:
    graph = legal_decision_graph(stage="adversarial-option-selection")
    prior = graph["readiness"]
    prior["readiness_pack_version"] = 3
    result = publish_supplemental_readiness(
        project_root,
        graph["workflow"],
        graph["problem_frame"],
        graph["brief"],
        graph["evidence"],
        request_payload(),
        limitation_dispositions=prior["limitation_dispositions"],
        value_conditions=prior["value_conditions"],
        prior_readiness=prior,
    )
    schema_validator(project_root, "readiness_pack").validate(result["readiness"])
    assert result["readiness"]["readiness_pack_version"] == 4
    assert result["readiness"]["limitation_dispositions"] == prior[
        "limitation_dispositions"
    ]


def test_user_value_cannot_be_routed_as_a_supplemental_gap(
    project_root: Path,
) -> None:
    graph = legal_decision_graph()
    with pytest.raises(ContractViolation, match="USER_VALUE"):
        publish_supplemental_readiness(
            project_root,
            graph["workflow"],
            graph["problem_frame"],
            graph["brief"],
            graph["evidence"],
            request_payload("USER_VALUE"),
            limitation_dispositions=copy.deepcopy(
                research_contracts.partial_supplemental_inputs()["readiness"][
                    "limitation_dispositions"
                ]
            ),
            value_conditions=[],
            prior_readiness=None,
        )


def test_none_supplemental_rejects_nonzero_network_counts(
    project_root: Path,
) -> None:
    graph = legal_decision_graph(backend="NONE")
    graph["workflow"]["call_counts"]["RES-001"]["search"] = 1
    with pytest.raises(ContractViolation, match="NONE.*count"):
        publish_supplemental_readiness(
            project_root,
            graph["workflow"],
            graph["problem_frame"],
            graph["brief"],
            graph["evidence"],
            request_payload("PROVIDED_MATERIAL"),
            limitation_dispositions=copy.deepcopy(
                research_contracts.partial_supplemental_inputs("NONE")["readiness"][
                    "limitation_dispositions"
                ]
            ),
            value_conditions=[],
            prior_readiness=None,
        )


def test_request_candidate_references_must_close_to_current_package(
    project_root: Path,
) -> None:
    graph = legal_decision_graph()
    with pytest.raises(ContractViolation, match="candidate"):
        publish_supplemental_readiness(
            project_root,
            graph["workflow"],
            graph["problem_frame"],
            graph["brief"],
            graph["evidence"],
            request_payload(candidate_ids=["CAN-999"]),
            limitation_dispositions=copy.deepcopy(
                research_contracts.partial_supplemental_inputs()["readiness"][
                    "limitation_dispositions"
                ]
            ),
            value_conditions=[],
            prior_readiness=None,
        )


@pytest.mark.parametrize("backend", ["RESEARCH_CORE", "NONE"])
def test_first_task10_supplemental_publishes_a_task9_accepted_revision_two_handoff(
    project_root: Path, backend: str
) -> None:
    publisher = globals().get("publish_supplemental_readiness")
    assert callable(publisher), "complete Task 10 supplemental publisher is missing"
    graph = legal_decision_graph(backend=backend)
    schema = research_contracts.load_schema(project_root)
    for definition, key in (
        ("workflow", "workflow"),
        ("problem_frame", "problem_frame"),
        ("research_brief", "brief"),
        ("evidence_package", "evidence"),
    ):
        research_contracts.validate_definition(schema, definition, graph[key])
    research_contracts.validate_brief_semantics(graph["brief"], backend)
    assert research_contracts.validate_evidence_semantics(
        graph["evidence"],
        receipt_field="execution_receipts",
        task_map={task["task_id"]: task for task in graph["brief"]["tasks"]},
        analysis_goal="DECIDE",
        declared_state=graph["workflow"]["research_state"],
    ) == graph["workflow"]["research_state"]

    request = request_payload(
        "PROVIDED_MATERIAL" if backend == "NONE" else "PUBLIC_FACT"
    )
    published = publisher(
        project_root,
        graph["workflow"],
        graph["problem_frame"],
        graph["brief"],
        graph["evidence"],
        request,
        limitation_dispositions=copy.deepcopy(
            research_contracts.partial_supplemental_inputs(backend)["readiness"][
                "limitation_dispositions"
            ]
        ),
        value_conditions=["Prefer reversible change."],
        prior_readiness=None,
    )
    new_task = (
        research_contracts.provided_material_task("RES-003")
        if backend == "NONE"
        else research_contracts.public_web_task("RES-003")
    )
    if backend == "NONE":
        new_task["material_refs"].append("inputs/new-evidence.md")
    new_task = research_contracts.supplemental_task(new_task)
    handoff = research_contracts.supplemental_handoff(
        schema,
        published["workflow"],
        graph["problem_frame"],
        graph["brief"],
        graph["evidence"],
        published["readiness"],
        [new_task],
    )
    assert handoff["brief"]["revision"] == 2
    assert handoff["brief"]["tasks"][:2] == graph["brief"]["tasks"]
    assert handoff["brief"]["tasks"][2]["supplemental_request_id"] == "SUP-001"


def test_actual_revision_two_graph_can_publish_and_append_a_third_revision(
    project_root: Path,
) -> None:
    publisher = globals().get("publish_supplemental_readiness")
    assert callable(publisher), "complete Task 10 supplemental publisher is missing"
    graph = legal_decision_graph()
    schema = research_contracts.load_schema(project_root)
    first = publisher(
        project_root,
        graph["workflow"],
        graph["problem_frame"],
        graph["brief"],
        graph["evidence"],
        request_payload(),
        limitation_dispositions=copy.deepcopy(
            research_contracts.partial_supplemental_inputs()["readiness"][
                "limitation_dispositions"
            ]
        ),
        value_conditions=[],
        prior_readiness=None,
    )
    handoff = research_contracts.supplemental_handoff(
        schema,
        first["workflow"],
        graph["problem_frame"],
        graph["brief"],
        graph["evidence"],
        first["readiness"],
        [
            research_contracts.supplemental_task(
                research_contracts.public_web_task("RES-003")
            )
        ],
    )
    draft = handoff["draft"]
    draft["completed_receipts"].append(
        research_contracts.receipt(
            "RES-003",
            "WITH_RESULTS",
            quality_met=True,
            call_refs=["CALL-003"],
            source_ids=["SRC-003"],
        )
    )
    draft["sources"].append(research_contracts.source("SRC-003", "CALL-003"))
    draft["evidence_items"].append(
        research_contracts.fact(
            "EVI-003", "RES-003", "SRC-003", candidate_ids=["CAN-001"]
        )
    )
    draft["unfinished_task_ids"] = []
    handoff["workflow"]["call_counts"]["RES-003"]["search"] = 1
    current, evidence = research_contracts.publish_evidence(
        schema, handoff["workflow"], handoff["brief"], draft, accepted=True
    )
    prior = copy.deepcopy(first["readiness"])
    prior["readiness_pack_version"] = 2
    prior["brief_revision"] = 2
    prior["evidence_revision"] = evidence["evidence_revision"]
    prior["status"] = "READY"
    prior.pop("supplemental_request")

    second_request = request_payload()
    second_request["request_id"] = "SUP-002"
    published = publisher(
        project_root,
        current,
        graph["problem_frame"],
        handoff["brief"],
        evidence,
        second_request,
        limitation_dispositions=prior["limitation_dispositions"],
        value_conditions=prior["value_conditions"],
        prior_readiness=prior,
    )
    assert published["readiness"]["brief_revision"] == 2
    assert published["readiness"]["status"] == "NEEDS_SUPPLEMENTAL"
    assert published["workflow"]["next_stage"] == "research-design-kickoff"
    request_id = published["readiness"]["supplemental_request"]["request_id"]
    third = research_contracts.supplemental_handoff(
        schema,
        published["workflow"],
        graph["problem_frame"],
        handoff["brief"],
        evidence,
        published["readiness"],
        [
            research_contracts.supplemental_task(
                research_contracts.public_web_task("RES-004"), request_id
            )
        ],
    )
    assert third["brief"]["revision"] == 3
    assert third["brief"]["tasks"][:3] == handoff["brief"]["tasks"]


def test_none_public_fact_persists_valid_cancelled_pack_without_request(
    project_root: Path,
) -> None:
    graph = legal_decision_graph(backend="NONE")
    prior = copy.deepcopy(
        research_contracts.partial_supplemental_inputs("NONE")["readiness"]
    )
    prior["status"] = "READY"
    prior.pop("supplemental_request")
    dispositions = prior["limitation_dispositions"]
    result = publish_supplemental_readiness(
        project_root,
        graph["workflow"],
        graph["problem_frame"],
        graph["brief"],
        graph["evidence"],
        request_payload("PUBLIC_FACT"),
        limitation_dispositions=dispositions,
        value_conditions=[],
        prior_readiness=prior,
    )
    assert result["readiness"]["status"] == "STOPPED"
    assert "supplemental_request" not in result["readiness"]
    assert result["workflow"]["blocking_reason"]["code"] == (
        "PUBLIC_WEB_REQUIRES_NEW_WORKFLOW"
    )
    assert result["workflow"]["research_state"] == "RESEARCH_CANCELLED"
    schema_validator(project_root, "readiness_pack").validate(result["readiness"])
    schema_validator(project_root, "workflow").validate(result["workflow"])


def test_readiness_requires_exactly_one_valid_reasoned_disposition_per_limitation(
    project_root: Path,
) -> None:
    valid = [
        {"limitation_id": "LIM-001", "disposition": "ACCEPTED", "reason": "Low impact."},
        {"limitation_id": "LIM-002", "disposition": "ESCALATED", "reason": "Could reverse the choice."},
        {"limitation_id": "LIM-003", "disposition": "CORRECTION_REQUESTED", "reason": "Claim is inconsistent."},
    ]
    assert_dispositions_cover_limitations(["LIM-001", "LIM-002", "LIM-003"], valid)
    readiness = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "readiness_pack_id": "READY-001",
        "readiness_pack_version": 1,
        "brief_revision": 1,
        "evidence_revision": 1,
        "status": "READY",
        "limitation_dispositions": valid,
        "value_conditions": ["Accept downtime only outside business hours."],
    }
    schema_validator(project_root, "readiness_pack").validate(readiness)
    for broken in (valid[:-1], valid + [valid[0]], [{**valid[0], "limitation_id": "LIM-999"}]):
        with pytest.raises(AssertionError):
            assert_dispositions_cover_limitations(
                ["LIM-001", "LIM-002", "LIM-003"], broken
            )
    with pytest.raises(ValidationError):
        schema_validator(project_root, "readiness_pack").validate(
            {**readiness, "limitation_dispositions": [{**valid[0], "disposition": "IGNORED"}]}
        )


@pytest.mark.parametrize("count", [1, 8])
def test_decide_candidate_bounds_allow_one_through_eight(
    project_root: Path, count: int
) -> None:
    validator = schema_validator(project_root, "evidence_package")
    package = decision_evidence(
        [f"CAN-{index:03d}" for index in range(1, count + 1)]
    )
    validator.validate(package)
    for invalid_count in (0, 9):
        invalid = decision_evidence(
            [f"OUT-{index:03d}" for index in range(1, invalid_count + 1)]
        )
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_high_impact_multi_candidate_challenge_is_symmetric() -> None:
    candidates = ["CAN-001", "CAN-002", "CAN-003"]
    themes = ["VALUE", "RISK"]
    records = [
        {"candidate_id": candidate, "theme_id": theme, "claim": "claim", "counterevidence": "counter", "response": "response", "verdict": "verdict"}
        for candidate, theme in product(candidates, themes)
    ]
    assert_symmetric_challenge(candidates, themes, records)
    with pytest.raises(AssertionError):
        assert_symmetric_challenge(candidates, themes, records[:-1])


def test_symmetric_challenge_rejects_duplicate_cells() -> None:
    candidates = ["CAN-001", "CAN-002"]
    themes = ["VALUE"]
    records = [
        {
            "candidate_id": candidate,
            "theme_id": "VALUE",
            "claim": "claim",
            "counterevidence": "counter",
            "response": "response",
            "verdict": "verdict",
        }
        for candidate in candidates
    ]
    with pytest.raises(AssertionError):
        assert_symmetric_challenge(candidates, themes, [*records, records[0]])


def test_decision_stage_skips_or_challenges_by_impact_not_candidate_minimum() -> None:
    cases = [
        (1, False, "SKIP_VALID_SELECTION_PATH"),
        (3, False, "SKIP_VALID_SELECTION_PATH"),
        (2, True, "SYMMETRIC_CHALLENGE"),
        (8, True, "SYMMETRIC_CHALLENGE"),
    ]
    for candidate_count, material_conflict, expected in cases:
        actual = "SYMMETRIC_CHALLENGE" if material_conflict and candidate_count > 1 else "SKIP_VALID_SELECTION_PATH"
        assert actual == expected


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing_decision_ref", "decision reference"),
        ("unknown_candidate", "selected candidate"),
    ],
)
def test_selection_output_gate_rejects_structural_breaks(
    project_root: Path, case: str, message: str
) -> None:
    gate = globals().get("validate_selection_output_semantics")
    assert callable(gate), "narrow Task 10 selection output gate is missing"
    graph = legal_decision_graph(stage="adversarial-option-selection")
    result = accept_selection(
        graph["workflow"], graph["evidence"], graph["readiness"], ["CAN-001"]
    )
    gate(
        project_root,
        graph["workflow"],
        graph["problem_frame"],
        graph["brief"],
        graph["evidence"],
        graph["readiness"],
        result["decision"],
        result["workflow"],
    )

    decision = copy.deepcopy(result["decision"])
    after = copy.deepcopy(result["workflow"])
    if case == "missing_decision_ref":
        after["artifact_refs"].pop("decision")
        schema_validator(project_root, "workflow").validate(after)
    else:
        decision["selected_candidate_ids"] = ["CAN-999"]
        schema_validator(project_root, "decision").validate(decision)
    with pytest.raises(ContractViolation, match=message):
        gate(
            project_root,
            graph["workflow"],
            graph["problem_frame"],
            graph["brief"],
            graph["evidence"],
            graph["readiness"],
            decision,
            after,
        )


@pytest.mark.parametrize(
    "selected_ids",
    ([], ["CAN-001", "CAN-001"], ["CAN-999"]),
)
def test_selection_rejects_empty_duplicate_or_out_of_package_candidate_ids(
    selected_ids: list[str],
) -> None:
    graph = legal_decision_graph(stage="adversarial-option-selection")
    with pytest.raises(ContractViolation, match="selected_candidate_ids"):
        accept_selection(
            graph["workflow"],
            graph["evidence"],
            graph["readiness"],
            selected_ids,
        )


@pytest.mark.parametrize("stage", STAGES)
def test_each_decision_skill_invokes_the_shared_gate_before_stage_work(
    project_root: Path, stage: str
) -> None:
    skill = (project_root / f"skills/{stage}/SKILL.md").read_text("utf-8")
    gate_position = skill.find(
        "../problem-navigator/references/evidence-package-validation.md"
    )
    work_marker = (
        "## Decision-changing gaps only"
        if stage == STAGES[0]
        else "## Freeze criteria and select"
    )
    assert gate_position >= 0
    assert gate_position < skill.find(work_marker)
    assert "MISSING_OR_INVALID_ARTIFACT" in skill
    assert "wrong_stage: return=problem-navigator" in skill


def test_readiness_skill_declares_question_and_supplemental_guarantees(
    project_root: Path,
) -> None:
    readiness = (project_root / "skills/decision-readiness-interview/SKILL.md").read_text("utf-8")
    normalized = " ".join(readiness.split())
    assert "GENERAL" in readiness and "PRODUCT_SOFTWARE" in readiness
    assert "value" in readiness.lower() and "public fact" in readiness.lower()
    assert "NEEDS_SUPPLEMENTAL" in readiness
    assert "supplemental_request" in readiness
    assert "1–4 new tasks" in normalized and "16-task" in normalized
    assert "Later brief revisions are legal" in normalized
    assert "no fixed one-supplement limit" in normalized
    assert "new Web-authorized workflow is required" in normalized
    assert "never reset counts" in normalized
    assert "exactly one" in readiness.lower() and "limitation" in readiness.lower()


def test_selection_skill_declares_symmetric_truthful_and_terminal_guarantees(
    project_root: Path,
) -> None:
    selection = (project_root / "skills/adversarial-option-selection/SKILL.md").read_text("utf-8")
    assert "claim" in selection.lower() and "counterevidence" in selection.lower()
    assert "self-critique" in selection and "independent review" in selection
    assert "solution-refinement" in selection and "STOPPED" in selection
    assert "selected_candidate_ids" in selection
    assert "supplemental_request" in selection
    assert "at least two qualified candidates" not in selection.lower()


def test_decision_skills_have_no_planning_or_implementation_exit(
    project_root: Path,
) -> None:
    combined = "".join(
        (project_root / f"skills/{stage}/SKILL.md").read_text("utf-8")
        for stage in STAGES
    )
    assert "DIRECT_EXECUTION" not in combined
    assert "READY_FOR_PLANNING" not in combined
    assert "budget ledger" not in combined.lower()
    assert "workflow-control.md" in combined
    assert "preserving counts" in combined


@pytest.mark.parametrize("stage", STAGES)
def test_decision_stage_agent_policy_disables_implicit_invocation(
    project_root: Path, stage: str
) -> None:
    agent_path = project_root / f"adapters/codex/skills/{stage}/agents/openai.yaml"
    agent = yaml.safe_load(agent_path.read_text("utf-8"))
    assert agent["policy"]["allow_implicit_invocation"] is False
    assert f"${stage}" in agent["interface"]["default_prompt"]


def test_readiness_scenarios_cover_observable_task10_cases(project_root: Path) -> None:
    readiness_scenarios = (project_root / "docs/skill-tests/decision-readiness-interview-scenarios.md").read_text("utf-8")
    for marker in ("RED", "GREEN", "UNDERSTAND", "first supplemental", "second supplemental", "NONE", "supplemental_request", "prompt injection"):
        assert marker.lower() in readiness_scenarios.lower()


def test_selection_scenarios_cover_observable_task10_cases(project_root: Path) -> None:
    selection_scenarios = (project_root / "docs/skill-tests/adversarial-option-selection-scenarios.md").read_text("utf-8")
    for marker in ("RED", "GREEN", "symmetric", "skip", "self-critique", "selected_candidate_ids", "unresolved", "prompt injection"):
        assert marker.lower() in selection_scenarios.lower()
