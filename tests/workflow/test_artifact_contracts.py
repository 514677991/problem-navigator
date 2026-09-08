from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


SCHEMA_PATH = Path("skills/problem-navigator/references/artifacts.schema.json")
REQUIRED_DEFINITIONS = {
    "workflow",
    "problem_frame",
    "research_brief",
    "evidence_draft",
    "evidence_package",
    "supplemental_request",
    "readiness_pack",
    "decision",
    "refined_solution",
    "solution_document",
    "solution_spec_package",
}
WORKFLOW_ID = "550e8400-e29b-41d4-a716-446655440000"


def load_schema(project_root: Path) -> dict[str, object]:
    schema = json.loads((project_root / SCHEMA_PATH).read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_definition(
    schema: dict[str, object], definition: str, payload: dict[str, object]
) -> None:
    instance_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    Draft202012Validator(instance_schema).validate(payload)


def minimal_payloads() -> dict[str, dict[str, object]]:
    receipt = {
        "task_id": "RES-001",
        "outcome": "WITH_RESULTS",
        "quality_met": True,
        "call_refs": ["call-001"],
        "source_ids": ["SRC-001"],
        "external_source_ids": [],
    }
    source = {
        "source_id": "SRC-001",
        "call_ref": "call-001",
        "title": "Primary source",
        "normalized_url": "https://example.com/source",
        "provider": "brave",
        "source_type": "web",
        "retrieved_at": "2026-09-05T00:00:00Z",
    }
    evidence = {
        "evidence_item_id": "EVI-001",
        "task_id": "RES-001",
        "kind": "FACT",
        "statement": "A supported fact.",
        "web_source_ids": ["SRC-001"],
        "external_source_ids": [],
    }
    return {
        "workflow": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "next_stage": "problem-framing",
            "selected_backend": "NONE",
            "native_fallback_approved": False,
            "research_state": "NOT_STARTED",
            "call_counts": {},
            "artifact_refs": {},
        },
        "problem_frame": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "problem_frame_id": "PF-001",
            "problem_frame_version": 1,
            "analysis_goal": "DECIDE",
            "content_profile": "PRODUCT_SOFTWARE",
            "clarified_problem": "Choose a bounded product direction.",
            "goal": "Produce an evidence-backed solution definition.",
            "scope": ["Product and technical feasibility"],
            "non_goals": ["Implementation code"],
            "constraints": ["No implementation work"],
            "assumptions": [],
            "delivery_endpoint": "FINAL_SPEC_PACKAGE",
            "user_confirmation_status": "ACCEPTED",
        },
        "research_brief": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "revision": 1,
            "analysis_goal": "UNDERSTAND",
            "tasks": [
                {
                    "task_id": "RES-001",
                    "theme_id": "THEME-001",
                    "question": "What does the supplied material establish?",
                    "task_kind": "PROVIDED_MATERIAL",
                    "material_refs": [
                        ".problem-navigator/artifacts/"
                        f"{WORKFLOW_ID}/problem-frame.yaml"
                    ],
                    "quality_bar": "Extract only directly supported claims.",
                    "stop_condition": "All relevant supplied material is covered.",
                }
            ],
        },
        "evidence_draft": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "brief_revision": 1,
            "base_evidence_revision": 0,
            "completed_receipts": [],
            "sources": [],
            "evidence_items": [],
            "limitations": [],
            "external_sources": [],
            "unfinished_task_ids": ["RES-001"],
        },
        "evidence_package": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "brief_revision": 1,
            "evidence_revision": 1,
            "analysis_goal": "UNDERSTAND",
            "research_state": "RESEARCH_COMPLETE",
            "neutral_synthesis": "The available evidence supports a bounded finding.",
            "execution_receipts": [receipt],
            "sources": [source],
            "evidence_items": [evidence],
            "limitations": [],
            "external_sources": [],
        },
        "supplemental_request": {
            "request_id": "SUP-001",
            "gap_kind": "PUBLIC_FACT",
            "question": "What current public fact could change the choice?",
            "decision_impact": "The answer can change candidate eligibility.",
            "affected_candidate_ids": ["CAND-001"],
        },
        "readiness_pack": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "readiness_pack_id": "READY-001",
            "readiness_pack_version": 1,
            "brief_revision": 1,
            "evidence_revision": 1,
            "status": "READY",
            "limitation_dispositions": [],
            "value_conditions": [],
        },
        "decision": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "decision_id": "DEC-001",
            "decision_version": 1,
            "readiness_pack_id": "READY-001",
            "readiness_pack_version": 1,
            "evidence_revision": 1,
            "selected_candidate_ids": ["CAND-001"],
            "rationale": "The selected direction best meets the frozen criteria.",
            "status": "SELECTED",
        },
        "refined_solution": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "refined_solution_id": "SOL-001",
            "refined_solution_version": 1,
            "decision_id": "DEC-001",
            "decision_version": 1,
            "definition": "A complete solution definition.",
            "scope": ["Accepted direction"],
            "constraints": ["Preserve evidence boundaries"],
            "acceptance_criteria": ["The solution is reviewable"],
            "user_confirmation_status": "ACCEPTED",
        },
        "solution_document": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "document_id": "DOC-001",
            "document_version": 1,
            "refined_solution_id": "SOL-001",
            "refined_solution_version": 1,
            "content_profile": "GENERAL",
            "members": ["formal-solution-report.md"],
            "acceptance_status": "ACCEPTED",
        },
        "solution_spec_package": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "package_id": "PKG-001",
            "package_version": 1,
            "document_id": "DOC-001",
            "document_version": 1,
            "content_profile": "GENERAL",
            "units": ["specs/solution-unit.md"],
            "acceptance_status": "ACCEPTED",
        },
    }


def test_schema_is_draft_2020_12_defs_only(project_root: Path) -> None:
    schema = load_schema(project_root)

    assert set(schema) == {"$schema", "$id", "$defs"}
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert REQUIRED_DEFINITIONS <= set(schema["$defs"])


@pytest.mark.parametrize("definition", sorted(REQUIRED_DEFINITIONS))
def test_each_artifact_has_a_strict_minimal_valid_instance(
    project_root: Path, definition: str
) -> None:
    schema = load_schema(project_root)
    payload = minimal_payloads()[definition]

    validate_definition(schema, definition, payload)

    with pytest.raises(ValidationError):
        validate_definition(schema, definition, {**payload, "unknown_field": True})


def test_workflow_backend_approval_invariant(project_root: Path) -> None:
    schema = load_schema(project_root)
    workflow = minimal_payloads()["workflow"]

    for backend in ("NONE", "UNSET", "RESEARCH_CORE"):
        validate_definition(
            schema,
            "workflow",
            {**workflow, "selected_backend": backend, "native_fallback_approved": False},
        )
        with pytest.raises(ValidationError):
            validate_definition(
                schema,
                "workflow",
                {
                    **workflow,
                    "selected_backend": backend,
                    "native_fallback_approved": True,
                },
            )

    validate_definition(
        schema,
        "workflow",
        {**workflow, "selected_backend": "HOST_NATIVE", "native_fallback_approved": True},
    )
    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "workflow",
            {
                **workflow,
                "selected_backend": "HOST_NATIVE",
                "native_fallback_approved": False,
            },
        )


def test_workflow_stage_goal_and_content_profile_contract(project_root: Path) -> None:
    schema = load_schema(project_root)
    workflow = minimal_payloads()["workflow"]
    compatible_stage_states = (
        ("problem-framing", "NOT_STARTED", None, None),
        ("research-design-kickoff", "NOT_STARTED", "UNDERSTAND", None),
        ("research-execution", "RESEARCH_IN_PROGRESS", "UNDERSTAND", None),
        ("decision-readiness-interview", "RESEARCH_COMPLETE", "DECIDE", None),
        ("adversarial-option-selection", "RESEARCH_COMPLETE", "DECIDE", None),
        ("solution-refinement", "RESEARCH_COMPLETE", "DECIDE", None),
        ("solution-documentation", "RESEARCH_COMPLETE", "DECIDE", None),
        ("solution-decomposition", "RESEARCH_COMPLETE", "DECIDE", None),
        ("DONE", "RESEARCH_COMPLETE", "UNDERSTAND", None),
        (
            "STOPPED",
            "NOT_STARTED",
            None,
            {"code": "MISSING_OR_INVALID_ARTIFACT", "task_ids": []},
        ),
    )

    for stage, state, goal, reason in compatible_stage_states:
        staged = {**workflow, "next_stage": stage, "research_state": state}
        if goal is not None:
            staged["analysis_goal"] = goal
        if reason is not None:
            staged["blocking_reason"] = reason
        validate_definition(schema, "workflow", staged)
    with pytest.raises(ValidationError):
        validate_definition(schema, "workflow", {**workflow, "next_stage": "planning"})

    # CREATE may persist before framing has selected a goal.
    validate_definition(schema, "workflow", workflow)
    for goal in ("UNDERSTAND", "DECIDE"):
        validate_definition(schema, "workflow", {**workflow, "analysis_goal": goal})
    with pytest.raises(ValidationError):
        validate_definition(schema, "workflow", {**workflow, "analysis_goal": "EXECUTE"})
    with pytest.raises(ValidationError):
        validate_definition(schema, "workflow", {**workflow, "content_profile": "GENERAL"})


@pytest.mark.parametrize(
    "stage",
    [
        "research-design-kickoff",
        "research-execution",
        "decision-readiness-interview",
        "adversarial-option-selection",
        "solution-refinement",
        "solution-documentation",
        "solution-decomposition",
        "DONE",
    ],
)
def test_workflow_requires_analysis_goal_after_framing(
    project_root: Path, stage: str
) -> None:
    schema = load_schema(project_root)
    workflow = {**minimal_payloads()["workflow"], "next_stage": stage}
    if stage in (
        "decision-readiness-interview",
        "adversarial-option-selection",
        "solution-refinement",
        "solution-documentation",
        "solution-decomposition",
        "DONE",
    ):
        workflow["research_state"] = "RESEARCH_COMPLETE"

    with pytest.raises(ValidationError):
        validate_definition(schema, "workflow", workflow)

    valid = {**workflow, "analysis_goal": "DECIDE"}
    if stage == "DONE":
        valid["research_state"] = "RESEARCH_COMPLETE"
    validate_definition(schema, "workflow", valid)


def _workflow_transition(
    state: str,
    stage: str,
    *,
    goal: str | None = None,
    reason: bool = False,
) -> dict[str, object]:
    workflow = {
        **minimal_payloads()["workflow"],
        "research_state": state,
        "next_stage": stage,
    }
    if goal is not None:
        workflow["analysis_goal"] = goal
    if reason:
        workflow["blocking_reason"] = {
            "code": "MISSING_OR_INVALID_ARTIFACT",
            "task_ids": [],
        }
    return workflow


@pytest.mark.parametrize(
    ("state", "stage", "goal", "reason"),
    [
        ("NOT_STARTED", "problem-framing", None, False),
        ("NOT_STARTED", "research-design-kickoff", "UNDERSTAND", False),
        ("NOT_STARTED", "research-execution", "DECIDE", False),
        ("NOT_STARTED", "STOPPED", None, True),
        ("RESEARCH_IN_PROGRESS", "research-design-kickoff", "DECIDE", False),
        ("RESEARCH_IN_PROGRESS", "research-execution", "UNDERSTAND", False),
        ("RESEARCH_IN_PROGRESS", "STOPPED", "DECIDE", True),
        ("RESEARCH_BLOCKED", "problem-framing", None, True),
        ("RESEARCH_BLOCKED", "research-execution", "DECIDE", True),
        ("RESEARCH_BLOCKED", "STOPPED", None, True),
        ("RESEARCH_FAILED", "STOPPED", "UNDERSTAND", True),
        ("RESEARCH_CANCELLED", "STOPPED", "DECIDE", True),
        ("RESEARCH_COMPLETE", "research-design-kickoff", "UNDERSTAND", False),
        ("RESEARCH_PARTIAL", "research-design-kickoff", "DECIDE", False),
        ("RESEARCH_COMPLETE", "decision-readiness-interview", "DECIDE", False),
        ("RESEARCH_PARTIAL", "solution-refinement", "DECIDE", False),
        ("RESEARCH_COMPLETE", "DONE", "UNDERSTAND", False),
        ("RESEARCH_PARTIAL", "STOPPED", "DECIDE", True),
    ],
)
def test_workflow_state_to_allowed_stage_positive_matrix(
    project_root: Path,
    state: str,
    stage: str,
    goal: str | None,
    reason: bool,
) -> None:
    schema = load_schema(project_root)

    validate_definition(
        schema,
        "workflow",
        _workflow_transition(state, stage, goal=goal, reason=reason),
    )


@pytest.mark.parametrize(
    ("state", "stage", "goal", "reason"),
    [
        ("NOT_STARTED", "DONE", "UNDERSTAND", False),
        ("NOT_STARTED", "solution-refinement", "DECIDE", False),
        ("NOT_STARTED", "STOPPED", None, False),
        ("RESEARCH_IN_PROGRESS", "problem-framing", "DECIDE", False),
        ("RESEARCH_IN_PROGRESS", "DONE", "UNDERSTAND", False),
        ("RESEARCH_BLOCKED", "research-design-kickoff", "DECIDE", True),
        ("RESEARCH_BLOCKED", "research-execution", "DECIDE", False),
        ("RESEARCH_FAILED", "research-execution", "UNDERSTAND", True),
        ("RESEARCH_CANCELLED", "STOPPED", None, True),
        ("RESEARCH_COMPLETE", "problem-framing", "DECIDE", False),
        ("RESEARCH_PARTIAL", "research-execution", "DECIDE", False),
        ("RESEARCH_COMPLETE", "solution-documentation", "UNDERSTAND", False),
        ("RESEARCH_PARTIAL", "STOPPED", "DECIDE", False),
    ],
)
def test_workflow_state_to_allowed_stage_negative_matrix(
    project_root: Path,
    state: str,
    stage: str,
    goal: str | None,
    reason: bool,
) -> None:
    schema = load_schema(project_root)

    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "workflow",
            _workflow_transition(state, stage, goal=goal, reason=reason),
        )


def test_blocking_reason_only_appears_for_blocked_or_stopped_workflow(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    invalid = _workflow_transition(
        "NOT_STARTED", "problem-framing", reason=True
    )

    with pytest.raises(ValidationError):
        validate_definition(schema, "workflow", invalid)

    validate_definition(
        schema,
        "workflow",
        _workflow_transition("NOT_STARTED", "STOPPED", reason=True),
    )


def test_workflow_research_blocked_shape_is_recoverable_only_at_web_boundaries(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    workflow = {
        **minimal_payloads()["workflow"],
        "selected_backend": "UNSET",
        "research_state": "RESEARCH_BLOCKED",
    }

    for stage in ("problem-framing", "research-execution"):
        validate_definition(
            schema,
            "workflow",
            {
                **workflow,
                "next_stage": stage,
                "blocking_reason": {
                    "code": "NO_AUTHORIZED_WEB_BACKEND",
                    "task_ids": [],
                },
                **({"analysis_goal": "DECIDE"} if stage != "problem-framing" else {}),
            },
        )

    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "workflow",
            {**workflow, "next_stage": "problem-framing"},
        )
    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "workflow",
            {
                **workflow,
                "next_stage": "solution-refinement",
                "analysis_goal": "DECIDE",
                "blocking_reason": {"code": "BLOCKED", "task_ids": []},
            },
        )


@pytest.mark.parametrize("research_state", ["RESEARCH_FAILED", "RESEARCH_CANCELLED"])
def test_failed_or_cancelled_workflow_must_stop(
    project_root: Path, research_state: str
) -> None:
    schema = load_schema(project_root)
    workflow = {
        **minimal_payloads()["workflow"],
        "analysis_goal": "DECIDE",
        "research_state": research_state,
    }

    validate_definition(
        schema,
        "workflow",
        {
            **workflow,
            "next_stage": "STOPPED",
            "blocking_reason": {"code": "TERMINATED", "task_ids": []},
        },
    )
    with pytest.raises(ValidationError):
        validate_definition(
            schema, "workflow", {**workflow, "next_stage": "solution-refinement"}
        )


@pytest.mark.parametrize(
    "research_state",
    [
        "NOT_STARTED",
        "RESEARCH_IN_PROGRESS",
        "RESEARCH_BLOCKED",
        "RESEARCH_FAILED",
        "RESEARCH_CANCELLED",
    ],
)
def test_done_requires_a_publishable_research_state(
    project_root: Path, research_state: str
) -> None:
    schema = load_schema(project_root)
    workflow = {
        **minimal_payloads()["workflow"],
        "analysis_goal": "UNDERSTAND",
        "next_stage": "DONE",
        "research_state": research_state,
    }
    if research_state == "RESEARCH_BLOCKED":
        workflow["blocking_reason"] = {"code": "BLOCKED", "task_ids": []}

    with pytest.raises(ValidationError):
        validate_definition(schema, "workflow", workflow)

    workflow.pop("blocking_reason", None)
    for publishable in ("RESEARCH_COMPLETE", "RESEARCH_PARTIAL"):
        validate_definition(
            schema, "workflow", {**workflow, "research_state": publishable}
        )


def test_stopped_preserves_missing_artifact_and_downstream_stop_space(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    create_stop = {
        **minimal_payloads()["workflow"],
        "next_stage": "STOPPED",
        "blocking_reason": {
            "code": "MISSING_OR_INVALID_ARTIFACT",
            "task_ids": [],
        },
    }
    downstream_stop = {
        **create_stop,
        "analysis_goal": "DECIDE",
        "research_state": "RESEARCH_COMPLETE",
    }

    validate_definition(schema, "workflow", create_stop)
    validate_definition(schema, "workflow", downstream_stop)


def _provided_material_task(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "theme_id": "THEME-001",
        "question": f"Question for {task_id}",
        "task_kind": "PROVIDED_MATERIAL",
        "material_refs": ["inputs/source.md"],
        "quality_bar": "Use direct support.",
        "stop_condition": "The source is covered.",
    }


def test_research_brief_revision_and_task_bounds(project_root: Path) -> None:
    schema = load_schema(project_root)
    brief = minimal_payloads()["research_brief"]

    validate_definition(
        schema,
        "research_brief",
        {**brief, "revision": 1, "tasks": [_provided_material_task(f"RES-{index:03}") for index in range(1, 13)]},
    )
    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "research_brief",
            {**brief, "revision": 1, "tasks": [_provided_material_task(f"RES-{index:03}") for index in range(1, 14)]},
        )
    validate_definition(
        schema,
        "research_brief",
        {**brief, "revision": 2, "tasks": [_provided_material_task(f"RES-{index:03}") for index in range(1, 17)]},
    )
    for later_revision in (3, 7):
        validate_definition(
            schema, "research_brief", {**brief, "revision": later_revision}
        )
    for invalid_revision in (0, -1):
        with pytest.raises(ValidationError):
            validate_definition(
                schema, "research_brief", {**brief, "revision": invalid_revision}
            )


def test_supplemental_request_shape_and_readiness_status_are_closed(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    public_request = minimal_payloads()["supplemental_request"]
    material_request = {
        **public_request,
        "gap_kind": "PROVIDED_MATERIAL",
        "material_refs": ["inputs/new-evidence.md"],
    }
    validate_definition(schema, "supplemental_request", public_request)
    validate_definition(schema, "supplemental_request", material_request)

    invalid_requests = (
        {**public_request, "gap_kind": "USER_VALUE"},
        {**public_request, "material_refs": ["inputs/not-allowed.md"]},
        {key: value for key, value in material_request.items() if key != "material_refs"},
        {**material_request, "material_refs": ["../outside.md"]},
        {**public_request, "affected_candidate_ids": []},
        {**public_request, "affected_candidate_ids": ["CAND-001", "CAND-001"]},
    )
    for invalid in invalid_requests:
        with pytest.raises(ValidationError):
            validate_definition(schema, "supplemental_request", invalid)

    readiness = minimal_payloads()["readiness_pack"]
    needs = {
        **readiness,
        "status": "NEEDS_SUPPLEMENTAL",
        "supplemental_request": public_request,
    }
    validate_definition(schema, "readiness_pack", needs)
    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "readiness_pack",
            {**readiness, "status": "NEEDS_SUPPLEMENTAL"},
        )
    for status in ("READY", "STOPPED"):
        validate_definition(schema, "readiness_pack", {**readiness, "status": status})
        with pytest.raises(ValidationError):
            validate_definition(
                schema,
                "readiness_pack",
                {**readiness, "status": status, "supplemental_request": public_request},
            )


def test_revision_one_tasks_forbid_supplemental_request_ids(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    task = {**_provided_material_task("RES-001"), "supplemental_request_id": "SUP-001"}
    brief = minimal_payloads()["research_brief"]
    with pytest.raises(ValidationError):
        validate_definition(schema, "research_brief", {**brief, "tasks": [task]})
    validate_definition(
        schema,
        "research_brief",
        {**brief, "revision": 2, "tasks": [task]},
    )


@pytest.mark.parametrize(
    "path",
    [
        "https://example.com/a.yaml",
        "file:///tmp/a.yaml",
        "/absolute/a.yaml",
        "C:/absolute/a.yaml",
        "C:\\absolute\\a.yaml",
        "folder\\a.yaml",
        "../a.yaml",
        "folder/../a.yaml",
        "./../a.yaml",
    ],
)
def test_artifact_relative_paths_are_project_local_forward_slash_paths(
    project_root: Path, path: str
) -> None:
    schema = load_schema(project_root)
    workflow = {
        **minimal_payloads()["workflow"],
        "artifact_refs": {"problem_frame": path},
    }

    with pytest.raises(ValidationError):
        validate_definition(schema, "workflow", workflow)

    validate_definition(
        schema,
        "workflow",
        {
            **minimal_payloads()["workflow"],
            "artifact_refs": {
                "problem_frame": ".problem-navigator/artifacts/id/problem-frame.yaml"
            },
        },
    )


def _receipt(outcome: str, **overrides: object) -> dict[str, object]:
    receipt: dict[str, object] = {
        "task_id": "RES-001",
        "outcome": outcome,
        "quality_met": outcome == "WITH_RESULTS",
        "call_refs": [],
        "source_ids": [],
        "external_source_ids": [],
    }
    receipt.update(overrides)
    return receipt


def test_receipt_outcome_specific_fields_and_result_support(project_root: Path) -> None:
    schema = load_schema(project_root)
    validate_definition(
        schema, "receipt", _receipt("WITH_RESULTS", source_ids=["SRC-001"])
    )
    with pytest.raises(ValidationError):
        validate_definition(schema, "receipt", _receipt("WITH_RESULTS"))
    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "receipt",
            _receipt("WITH_RESULTS", source_ids=["SRC-001"], quality_met=False, error_code="NETWORK_ERROR"),
        )

    validate_definition(
        schema, "receipt", _receipt("FAILED", quality_met=False, error_code="NETWORK_ERROR")
    )
    for invalid_code in (None, "SOMETHING_WENT_WRONG"):
        failed = _receipt("FAILED", quality_met=False)
        if invalid_code is not None:
            failed["error_code"] = invalid_code
        with pytest.raises(ValidationError):
            validate_definition(schema, "receipt", failed)

    validate_definition(
        schema,
        "receipt",
        _receipt("NOT_RUN", quality_met=False, not_run_reason="No authorized route."),
    )
    with pytest.raises(ValidationError):
        validate_definition(schema, "receipt", _receipt("NOT_RUN", quality_met=False))
    with pytest.raises(ValidationError):
        validate_definition(
            schema,
            "receipt",
            _receipt("NO_RESULTS", quality_met=False, not_run_reason="irrelevant"),
        )
    for invalid in (
        _receipt(
            "FAILED",
            quality_met=False,
            error_code="NETWORK_ERROR",
            not_run_reason="irrelevant",
        ),
        _receipt(
            "NOT_RUN",
            quality_met=False,
            not_run_reason="No authorized route.",
            error_code="NETWORK_ERROR",
        ),
        _receipt("FAILED", quality_met=True, error_code="NETWORK_ERROR"),
        _receipt(
            "NOT_RUN", quality_met=True, not_run_reason="No authorized route."
        ),
        _receipt("NO_RESULTS", quality_met=True),
    ):
        with pytest.raises(ValidationError):
            validate_definition(schema, "receipt", invalid)


def test_receipt_host_native_fields_are_paired(project_root: Path) -> None:
    schema = load_schema(project_root)
    receipt = _receipt("WITH_RESULTS", source_ids=["SRC-001"])

    validate_definition(
        schema,
        "receipt",
        {
            **receipt,
            "fallback_authorization": "USER_APPROVED",
            "fallback_reason": "Core routes exhausted.",
        },
    )
    for lone_field in (
        {"fallback_authorization": "USER_APPROVED"},
        {"fallback_reason": "Core routes exhausted."},
    ):
        with pytest.raises(ValidationError):
            validate_definition(schema, "receipt", {**receipt, **lone_field})


def test_fact_requires_a_source_reference(project_root: Path) -> None:
    schema = load_schema(project_root)
    fact = {
        "evidence_item_id": "EVI-001",
        "task_id": "RES-001",
        "kind": "FACT",
        "statement": "A fact.",
        "web_source_ids": [],
        "external_source_ids": [],
    }

    with pytest.raises(ValidationError):
        validate_definition(schema, "evidence_item", fact)
    validate_definition(
        schema, "evidence_item", {**fact, "external_source_ids": ["EXT-001"]}
    )


def test_limitation_requires_identity_and_an_affected_target(project_root: Path) -> None:
    schema = load_schema(project_root)
    limitation = {
        "limitation_id": "LIM-001",
        "affected_task_ids": ["RES-001"],
        "affected_candidate_ids": [],
        "summary": "A declared limitation.",
        "may_change_decision": False,
    }

    validate_definition(schema, "limitation", limitation)
    for invalid in (
        {key: value for key, value in limitation.items() if key != "limitation_id"},
        {**limitation, "affected_task_ids": [], "affected_candidate_ids": []},
    ):
        with pytest.raises(ValidationError):
            validate_definition(schema, "limitation", invalid)


def test_understand_evidence_package_rejects_candidate_fields(project_root: Path) -> None:
    schema = load_schema(project_root)
    package = minimal_payloads()["evidence_package"]

    for candidate_field in (
        {"candidate_basis": "Options supplied by the user."},
        {"candidates": [{"candidate_id": "CAND-001", "name": "A", "definition": "A direction."}]},
    ):
        with pytest.raises(ValidationError):
            validate_definition(
                schema, "evidence_package", {**package, **candidate_field}
            )


def test_product_solution_document_supports_full_prd_and_technical_endpoint_members(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    document = minimal_payloads()["solution_document"]

    validate_definition(
        schema,
        "solution_document",
        {
            **document,
            "content_profile": "PRODUCT_SOFTWARE",
            "members": ["01-prd.md", "02-technical-solution-spec.md"],
        },
    )
    # The one-member envelope is reserved by the workflow contract for an accepted
    # problem frame whose delivery_endpoint is PRD_ONLY.
    validate_definition(
        schema,
        "solution_document",
        {
            **document,
            "content_profile": "PRODUCT_SOFTWARE",
            "members": ["01-prd.md"],
        },
    )
    # A technical-only endpoint is a first-class one-member document and carries
    # no invented PRD binding in the envelope.
    validate_definition(
        schema,
        "solution_document",
        {
            **document,
            "content_profile": "PRODUCT_SOFTWARE",
            "members": ["01-technical-solution-spec.md"],
        },
    )
    for invalid_members in (
        [],
        ["02-technical-solution-spec.md", "01-prd.md"],
        ["01-prd.md", "02-technical-solution-spec.md", "03-extra.md"],
    ):
        with pytest.raises(ValidationError):
            validate_definition(
                schema,
                "solution_document",
                {
                    **document,
                    "content_profile": "PRODUCT_SOFTWARE",
                    "members": invalid_members,
                },
            )

    validate_definition(
        schema,
        "solution_document",
        {**document, "content_profile": "GENERAL", "members": ["custom-report.md"]},
    )


@pytest.mark.parametrize(
    ("definition", "required_fields", "forbidden_fields"),
    [
        ("problem_frame", {"problem_frame_id", "problem_frame_version"}, {"artifact_id", "revision"}),
        ("research_brief", {"revision"}, {"artifact_id", "brief_id", "brief_version"}),
        ("evidence_draft", {"brief_revision", "base_evidence_revision"}, {"artifact_id", "revision"}),
        ("evidence_package", {"brief_revision", "evidence_revision"}, {"artifact_id", "revision"}),
        ("readiness_pack", {"readiness_pack_id", "readiness_pack_version"}, {"artifact_id", "revision"}),
        ("decision", {"decision_id", "decision_version"}, {"artifact_id", "revision"}),
        ("refined_solution", {"refined_solution_id", "refined_solution_version"}, {"artifact_id", "revision"}),
        ("solution_document", {"document_id", "document_version"}, {"artifact_id", "revision"}),
        ("solution_spec_package", {"package_id", "package_version"}, {"artifact_id", "revision"}),
    ],
)
def test_artifacts_use_their_own_identity_and_revision_fields(
    project_root: Path,
    definition: str,
    required_fields: set[str],
    forbidden_fields: set[str],
) -> None:
    schema = load_schema(project_root)
    payload = minimal_payloads()[definition]

    assert required_fields <= payload.keys()
    for field in required_fields:
        invalid = copy.deepcopy(payload)
        invalid.pop(field)
        with pytest.raises(ValidationError):
            validate_definition(schema, definition, invalid)
    for field in forbidden_fields:
        with pytest.raises(ValidationError):
            validate_definition(schema, definition, {**payload, field: "legacy"})


def test_missing_or_invalid_artifact_has_one_stop_behavior(project_root: Path) -> None:
    framing = (project_root / "skills/problem-framing/SKILL.md").read_text("utf-8")

    assert "MISSING_OR_INVALID_ARTIFACT" in framing
    assert "next_stage: STOPPED" in framing
    assert "不得猜测" in framing or "do not guess" in framing.lower()


def test_shared_contract_does_not_restore_legacy_control_tokens(project_root: Path) -> None:
    production_text = "\n".join(
        path.read_text("utf-8")
        for path in (
            project_root / "skills/problem-navigator/SKILL.md",
            project_root / "skills/problem-framing/SKILL.md",
            project_root
            / "skills/problem-navigator/references/evidence-package-validation.md",
        )
    )
    legacy_tokens = {
        "READY_FOR_PLANNING",
        "DIRECT_EXECUTION",
        "selected_executor",
        "workflow_control",
        "WEB_RESEARCH_MCP",
        "NATIVE_WEB",
    }

    assert not (legacy_tokens & set(production_text.split()))
