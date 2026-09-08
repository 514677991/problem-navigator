from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
import yaml
from jsonschema import Draft202012Validator


Mode = Literal["CREATE", "RESUME"]
Reply = Literal["APPROVE", "REJECT", "SILENT", "NOT_ASKED"]
WORKFLOW_ID = "550e8400-e29b-41d4-a716-446655440000"


@dataclass(frozen=True)
class EntryScenario:
    name: str
    mode: Mode
    needs_web: bool
    existing: dict[str, object] | None = None
    mcp_reachable: bool = False
    search_configured: bool = False
    config_state: str = "NOT_CONFIGURED"
    native_reply: Reply = "NOT_ASKED"
    revoke_native: bool = False


def base_workflow(**overrides: object) -> dict[str, object]:
    workflow: dict[str, object] = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "next_stage": "problem-framing",
        "selected_backend": "UNSET",
        "native_fallback_approved": False,
        "research_state": "NOT_STARTED",
        "call_counts": {},
        "artifact_refs": {},
    }
    workflow.update(overrides)
    return workflow


def entry_transition(
    scenario: EntryScenario,
) -> tuple[dict[str, object], dict[str, object]]:
    """Deterministic contract fixture; this is not Plugin runtime code."""
    calls: dict[str, object] = {"reachability": 0, "status": 0, "warning": False}
    if scenario.mode == "CREATE":
        state = base_workflow(
            selected_backend="UNSET" if scenario.needs_web else "NONE"
        )
        if not scenario.needs_web:
            return state, calls
    else:
        assert scenario.existing is not None
        state = copy.deepcopy(scenario.existing)
        backend = state["selected_backend"]
        if backend == "NONE":
            return state, calls
        if backend == "HOST_NATIVE" and not scenario.revoke_native:
            return state, calls
        if backend == "HOST_NATIVE" and scenario.revoke_native:
            state["selected_backend"] = "UNSET"
            state["native_fallback_approved"] = False

        # A stored Web backend is checked only at a Web-required boundary.
        # Pure-analysis downstream work consumes already accepted evidence.
        if not scenario.needs_web:
            return state, calls

    calls["reachability"] = 1
    if scenario.mcp_reachable:
        calls["status"] = 1
        calls["warning"] = scenario.config_state == "INVALID"
    core_ready = scenario.mcp_reachable and scenario.search_configured
    if core_ready:
        state["selected_backend"] = "RESEARCH_CORE"
        state["native_fallback_approved"] = False
        if is_entry_preflight_block(state):
            state["research_state"] = "NOT_STARTED"
            state.pop("blocking_reason", None)
        return state, calls

    if scenario.native_reply == "APPROVE":
        state["selected_backend"] = "HOST_NATIVE"
        state["native_fallback_approved"] = True
        if scenario.mode == "CREATE" or is_entry_preflight_block(state):
            state["research_state"] = "NOT_STARTED"
            state.pop("blocking_reason", None)
        return state, calls

    state["research_state"] = "RESEARCH_BLOCKED"
    existing_reason = state.get("blocking_reason")
    preserves_existing_block = (
        scenario.mode == "RESUME"
        and isinstance(existing_reason, dict)
        and isinstance(existing_reason.get("task_ids"), list)
    )
    if not preserves_existing_block:
        state["blocking_reason"] = {
            "code": "NO_AUTHORIZED_WEB_BACKEND",
            "task_ids": [],
        }
    return state, calls


def is_entry_preflight_block(state: dict[str, object]) -> bool:
    blocking_reason = state.get("blocking_reason")
    return (
        state["research_state"] == "RESEARCH_BLOCKED"
        and state.get("next_stage") == "problem-framing"
        and isinstance(blocking_reason, dict)
        and blocking_reason.get("task_ids") == []
        and sum(
            sum(operation_counts.values())
            for operation_counts in state["call_counts"].values()
        )
        == 0
    )


class SemanticGateViolation(AssertionError):
    """A test-only signal that a cross-artifact invariant is broken."""


def validate_semantic_graph(graph: dict[str, dict[str, object]]) -> None:
    """Evaluate cross-artifact rules without consulting the prose under test."""

    def index_unique_tasks(
        brief: dict[str, object], artifact_name: str
    ) -> dict[str, dict[str, object]]:
        tasks: dict[str, dict[str, object]] = {}
        for task in brief["tasks"]:
            task_id = task["task_id"]
            if task_id in tasks:
                raise SemanticGateViolation(
                    f"{artifact_name} has duplicate task_id {task_id}"
                )
            tasks[task_id] = task
        return tasks

    def validate_receipt_evidence_scope(
        artifact: dict[str, object], receipt_field: str
    ) -> None:
        receipts = {
            receipt["task_id"]: receipt for receipt in artifact[receipt_field]
        }
        sources = {source["source_id"]: source for source in artifact["sources"]}
        limitations = artifact["limitations"]
        for receipt in receipts.values():
            for source_id in receipt["source_ids"]:
                source = sources.get(source_id)
                if source is None:
                    raise SemanticGateViolation(
                        f"receipt for {receipt['task_id']} cites unknown source {source_id}"
                    )
                if source["call_ref"] not in receipt["call_refs"]:
                    raise SemanticGateViolation(
                        f"source {source_id} call_ref is not owned by receipt for "
                        f"{receipt['task_id']}"
                    )
        for evidence in artifact["evidence_items"]:
            receipt = receipts.get(evidence["task_id"])
            if receipt is None:
                raise SemanticGateViolation(
                    f"evidence task {evidence['task_id']} has no receipt"
                )
            if not set(evidence["web_source_ids"]).issubset(receipt["source_ids"]):
                raise SemanticGateViolation(
                    f"evidence {evidence['evidence_item_id']} launders a Web source"
                )
            if not set(evidence["external_source_ids"]).issubset(
                receipt["external_source_ids"]
            ):
                raise SemanticGateViolation(
                    f"evidence {evidence['evidence_item_id']} launders an external source"
                )

        for receipt in receipts.values():
            needs_limitation = (
                receipt["outcome"] == "WITH_RESULTS"
                and receipt["quality_met"] is False
            )
            affects_task = any(
                receipt["task_id"] in limitation["affected_task_ids"]
                for limitation in limitations
            )
            if needs_limitation and not affects_task:
                raise SemanticGateViolation(
                    f"quality shortfall for {receipt['task_id']} has no limitation"
                )

    current_brief = graph["current_brief"]
    current_draft = graph["current_draft"]
    prior_brief = graph.get("prior_brief")
    prior_package = graph.get("prior_package")

    current_tasks = index_unique_tasks(current_brief, "current brief")
    if prior_brief is not None:
        prior_tasks = index_unique_tasks(prior_brief, "prior brief")
    else:
        prior_tasks = None

    validate_receipt_evidence_scope(current_draft, "completed_receipts")
    if prior_brief is None and prior_package is None:
        return
    if prior_brief is None or prior_package is None:
        raise SemanticGateViolation(
            "supplemental graph must contain both prior brief and prior package"
        )

    assert prior_tasks is not None
    validate_receipt_evidence_scope(prior_package, "execution_receipts")
    missing_task_ids = set(prior_tasks) - set(current_tasks)
    if missing_task_ids:
        raise SemanticGateViolation(
            f"supplemental brief dropped or renamed tasks: {sorted(missing_task_ids)}"
        )
    for task_id, prior_task in prior_tasks.items():
        if current_tasks[task_id] != prior_task:
            raise SemanticGateViolation(
                f"supplemental brief changed existing task {task_id}"
            )
    if len(current_tasks) - len(prior_tasks) > 4:
        raise SemanticGateViolation("supplemental brief added more than four tasks")

    inherited_collections = (
        ("execution_receipts", "completed_receipts"),
        ("sources", "sources"),
        ("evidence_items", "evidence_items"),
    )
    for prior_field, draft_field in inherited_collections:
        for prior_member in prior_package[prior_field]:
            if prior_member not in current_draft[draft_field]:
                raise SemanticGateViolation(
                    f"supplemental draft omitted inherited {prior_field} member"
                )


def _web_task(task_id: str, question: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "theme_id": "THEME-MARKET",
        "question": question,
        "task_kind": "PUBLIC_WEB",
        "direction": "auto",
        "domains": ["example.com"],
        "freshness": "month",
        "quality_bar": "Retain a directly supported current fact.",
        "stop_condition": "One authoritative source supports the claim.",
    }


def base_revision_semantic_graph() -> dict[str, dict[str, object]]:
    tasks = [
        _web_task("RES-BASE-001", "What evidence supports the base claim?"),
        _web_task("RES-BASE-002", "What evidence remains to be collected?"),
    ]
    receipt = {
        "task_id": "RES-BASE-001",
        "outcome": "WITH_RESULTS",
        "quality_met": True,
        "call_refs": ["call-base-001"],
        "source_ids": ["SRC-BASE-001"],
        "external_source_ids": [],
    }
    source = {
        "source_id": "SRC-BASE-001",
        "call_ref": "call-base-001",
        "title": "Base source",
        "normalized_url": "https://example.com/base",
        "provider": "brave",
        "source_type": "web",
        "retrieved_at": "2026-09-05T00:00:00Z",
    }
    evidence = {
        "evidence_item_id": "EVI-BASE-001",
        "task_id": "RES-BASE-001",
        "kind": "FACT",
        "statement": "The base claim has direct support.",
        "web_source_ids": ["SRC-BASE-001"],
        "external_source_ids": [],
    }
    return {
        "workflow": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "analysis_goal": "UNDERSTAND",
            "next_stage": "research-execution",
            "selected_backend": "RESEARCH_CORE",
            "native_fallback_approved": False,
            "research_state": "RESEARCH_IN_PROGRESS",
            "call_counts": {
                "RES-BASE-001": {"search": 1, "fetch": 0, "map": 0},
                "RES-BASE-002": {"search": 0, "fetch": 0, "map": 0},
            },
            "artifact_refs": {
                "problem_frame": ".problem-navigator/artifacts/wf/problem-frame.yaml",
                "research_brief": ".problem-navigator/artifacts/wf/research-brief.yaml",
                "evidence_draft": ".problem-navigator/artifacts/wf/evidence-draft.yaml",
            },
        },
        "problem_frame": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "problem_frame_id": "PF-BASE-001",
            "problem_frame_version": 1,
            "analysis_goal": "UNDERSTAND",
            "content_profile": "GENERAL",
            "clarified_problem": "Assess a bounded claim.",
            "goal": "Produce an evidence-backed research report.",
            "scope": ["Base claim"],
            "non_goals": ["Implementation"],
            "constraints": ["Use public evidence only"],
            "assumptions": [],
            "delivery_endpoint": "REPORT",
            "user_confirmation_status": "ACCEPTED",
        },
        "current_brief": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "revision": 1,
            "analysis_goal": "UNDERSTAND",
            "tasks": tasks,
        },
        "current_draft": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "brief_revision": 1,
            "base_evidence_revision": 0,
            "completed_receipts": [receipt],
            "sources": [source],
            "evidence_items": [evidence],
            "limitations": [],
            "external_sources": [],
            "unfinished_task_ids": ["RES-BASE-002"],
        },
    }


def supplemental_semantic_graph() -> dict[str, dict[str, object]]:
    prior_tasks = [
        _web_task("RES-001", "What evidence supports the demand claim?"),
        _web_task("RES-002", "What evidence supports the feasibility claim?"),
        _web_task("RES-003", "Do the remaining allowed routes return results?"),
    ]
    supplemental_task = _web_task(
        "RES-004", "What new public fact could change the decision?"
    )
    receipts = [
        {
            "task_id": "RES-001",
            "outcome": "WITH_RESULTS",
            "quality_met": False,
            "call_refs": ["call-res-001"],
            "source_ids": ["SRC-001"],
            "external_source_ids": [],
        },
        {
            "task_id": "RES-002",
            "outcome": "WITH_RESULTS",
            "quality_met": True,
            "call_refs": ["call-res-002"],
            "source_ids": ["SRC-002"],
            "external_source_ids": [],
        },
        {
            "task_id": "RES-003",
            "outcome": "NO_RESULTS",
            "quality_met": False,
            "call_refs": ["call-res-003"],
            "source_ids": [],
            "external_source_ids": [],
        },
    ]
    sources = [
        {
            "source_id": "SRC-001",
            "call_ref": "call-res-001",
            "title": "Demand source",
            "normalized_url": "https://example.com/demand",
            "provider": "brave",
            "source_type": "web",
            "retrieved_at": "2026-09-05T00:00:00Z",
        },
        {
            "source_id": "SRC-002",
            "call_ref": "call-res-002",
            "title": "Feasibility source",
            "normalized_url": "https://example.com/feasibility",
            "provider": "exa",
            "source_type": "web",
            "retrieved_at": "2026-09-05T00:01:00Z",
        },
    ]
    evidence_items = [
        {
            "evidence_item_id": "EVI-001",
            "task_id": "RES-001",
            "kind": "FACT",
            "statement": "The demand signal is measurable but incomplete.",
            "web_source_ids": ["SRC-001"],
            "external_source_ids": [],
        },
        {
            "evidence_item_id": "EVI-002",
            "task_id": "RES-002",
            "kind": "FACT",
            "statement": "The proposed approach is technically feasible.",
            "web_source_ids": ["SRC-002"],
            "external_source_ids": [],
        },
    ]
    limitations = [
        {
            "limitation_id": "LIM-001",
            "affected_task_ids": ["RES-001"],
            "affected_candidate_ids": [],
            "summary": "The demand source does not meet the full quality bar.",
            "may_change_decision": True,
        },
        {
            "limitation_id": "LIM-002",
            "affected_task_ids": ["RES-003"],
            "affected_candidate_ids": [],
            "summary": "The allowed routes returned no results for this task.",
            "may_change_decision": False,
        },
    ]
    prior_package = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "brief_revision": 1,
        "evidence_revision": 1,
        "analysis_goal": "UNDERSTAND",
        "research_state": "RESEARCH_PARTIAL",
        "neutral_synthesis": "Demand is promising and feasibility is supported.",
        "execution_receipts": copy.deepcopy(receipts),
        "sources": copy.deepcopy(sources),
        "evidence_items": copy.deepcopy(evidence_items),
        "limitations": copy.deepcopy(limitations),
        "external_sources": [],
    }
    return {
        "workflow": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "analysis_goal": "UNDERSTAND",
            "next_stage": "research-execution",
            "selected_backend": "RESEARCH_CORE",
            "native_fallback_approved": False,
            "research_state": "RESEARCH_IN_PROGRESS",
            "call_counts": {
                task_id: {"search": 0, "fetch": 0, "map": 0}
                for task_id in ("RES-001", "RES-002", "RES-003", "RES-004")
            },
            "artifact_refs": {
                "problem_frame": ".problem-navigator/artifacts/wf/problem-frame.yaml",
                "research_brief": ".problem-navigator/artifacts/wf/research-brief.yaml",
                "evidence_draft": ".problem-navigator/artifacts/wf/evidence-draft.yaml",
            },
        },
        "problem_frame": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "problem_frame_id": "PF-001",
            "problem_frame_version": 1,
            "analysis_goal": "UNDERSTAND",
            "content_profile": "GENERAL",
            "clarified_problem": "Assess demand and feasibility for a bounded idea.",
            "goal": "Produce an evidence-backed research report.",
            "scope": ["Demand", "Feasibility"],
            "non_goals": ["Implementation"],
            "constraints": ["Use public evidence only"],
            "assumptions": [],
            "delivery_endpoint": "REPORT",
            "user_confirmation_status": "ACCEPTED",
        },
        "prior_brief": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "revision": 1,
            "analysis_goal": "UNDERSTAND",
            "tasks": copy.deepcopy(prior_tasks),
        },
        "current_brief": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "revision": 2,
            "analysis_goal": "UNDERSTAND",
            "tasks": copy.deepcopy(prior_tasks) + [supplemental_task],
        },
        "prior_package": prior_package,
        "current_draft": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "brief_revision": 2,
            "base_evidence_revision": 1,
            "completed_receipts": copy.deepcopy(receipts),
            "sources": copy.deepcopy(sources),
            "evidence_items": copy.deepcopy(evidence_items),
            "limitations": copy.deepcopy(limitations),
            "external_sources": [],
            "unfinished_task_ids": ["RES-004"],
        },
    }


def validate_graph_shapes(
    project_root: Path, graph: dict[str, dict[str, object]]
) -> None:
    schema = json.loads(
        (
            project_root
            / "skills/problem-navigator/references/artifacts.schema.json"
        ).read_text("utf-8")
    )
    Draft202012Validator.check_schema(schema)
    definitions = {
        "workflow": "workflow",
        "problem_frame": "problem_frame",
        "prior_brief": "research_brief",
        "current_brief": "research_brief",
        "prior_package": "evidence_package",
        "current_draft": "evidence_draft",
    }
    for artifact_name, definition in definitions.items():
        if artifact_name not in graph:
            continue
        Draft202012Validator(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": schema["$defs"],
                "$ref": f"#/$defs/{definition}",
            }
        ).validate(graph[artifact_name])


def validate_workflow_shape(project_root: Path, workflow: dict[str, object]) -> None:
    schema = json.loads(
        (
            project_root
            / "skills/problem-navigator/references/artifacts.schema.json"
        ).read_text("utf-8")
    )
    Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": schema["$defs"],
            "$ref": "#/$defs/workflow",
        }
    ).validate(workflow)


SCENARIOS = [
    (
        EntryScenario("create-no-web", "CREATE", False),
        {"selected_backend": "NONE", "native_fallback_approved": False, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 0, "status": 0},
    ),
    (
        EntryScenario("create-web-core-ready", "CREATE", True, mcp_reachable=True, search_configured=True),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario("create-web-rejected", "CREATE", True, mcp_reachable=True, native_reply="REJECT"),
        {"selected_backend": "UNSET", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "problem-framing", "blocking_reason": {"code": "NO_AUTHORIZED_WEB_BACKEND", "task_ids": []}},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario("create-web-silent", "CREATE", True, mcp_reachable=False, native_reply="SILENT"),
        {"selected_backend": "UNSET", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "problem-framing", "blocking_reason": {"code": "NO_AUTHORIZED_WEB_BACKEND", "task_ids": []}},
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "resume-none",
            "RESUME",
            False,
            existing=base_workflow(
                selected_backend="NONE",
                next_stage="research-design-kickoff",
                research_state="RESEARCH_PARTIAL",
                call_counts={"RES-001": {"search": 0, "fetch": 0, "map": 0}},
                artifact_refs={"problem_frame": ".problem-navigator/artifacts/id/problem-frame.yaml"},
            ),
            mcp_reachable=True,
            search_configured=True,
        ),
        {"selected_backend": "NONE", "native_fallback_approved": False, "research_state": "RESEARCH_PARTIAL", "next_stage": "research-design-kickoff"},
        {"reachability": 0, "status": 0},
    ),
    (
        EntryScenario(
            "resume-core-lost",
            "RESUME",
            True,
            existing=base_workflow(
                selected_backend="RESEARCH_CORE",
                next_stage="research-execution",
                research_state="RESEARCH_IN_PROGRESS",
                call_counts={"RES-001": {"search": 2, "fetch": 0, "map": 0}},
            ),
            mcp_reachable=True,
            native_reply="SILENT",
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution"},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario(
            "resume-entry-block-core-restored",
            "RESUME",
            True,
            existing=base_workflow(
                research_state="RESEARCH_BLOCKED",
                blocking_reason={"code": "NO_AUTHORIZED_WEB_BACKEND", "task_ids": []},
            ),
            mcp_reachable=True,
            search_configured=True,
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario(
            "resume-entry-block-native-approved",
            "RESUME",
            True,
            existing=base_workflow(
                research_state="RESEARCH_BLOCKED",
                blocking_reason={"code": "NO_AUTHORIZED_WEB_BACKEND", "task_ids": []},
            ),
            native_reply="APPROVE",
        ),
        {"selected_backend": "HOST_NATIVE", "native_fallback_approved": True, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "resume-task-block-zero-counts-does-not-reset",
            "RESUME",
            True,
            existing=base_workflow(
                next_stage="research-execution",
                research_state="RESEARCH_BLOCKED",
                blocking_reason={"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]},
                call_counts={"RES-001": {"search": 0, "fetch": 0, "map": 0}},
            ),
            mcp_reachable=True,
            search_configured=True,
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution", "blocking_reason": {"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]}},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario(
            "resume-unset-core-ready",
            "RESUME",
            True,
            existing=base_workflow(selected_backend="UNSET"),
            mcp_reachable=True,
            search_configured=True,
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario(
            "resume-unset-core-down-silent",
            "RESUME",
            True,
            existing=base_workflow(selected_backend="UNSET", next_stage="research-execution", analysis_goal="DECIDE"),
            native_reply="SILENT",
        ),
        {"selected_backend": "UNSET", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution", "blocking_reason": {"code": "NO_AUTHORIZED_WEB_BACKEND", "task_ids": []}},
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "resume-unset-pure-analysis-downstream",
            "RESUME",
            False,
            existing=base_workflow(
                selected_backend="UNSET",
                next_stage="solution-refinement",
                research_state="RESEARCH_COMPLETE",
                analysis_goal="DECIDE",
                call_counts={"RES-001": {"search": 1, "fetch": 0, "map": 0}},
            ),
            mcp_reachable=True,
            search_configured=True,
        ),
        {"selected_backend": "UNSET", "native_fallback_approved": False, "research_state": "RESEARCH_COMPLETE", "next_stage": "solution-refinement"},
        {"reachability": 0, "status": 0},
    ),
    (
        EntryScenario(
            "resume-unset-task-block-silent-preserves-task-ids",
            "RESUME",
            True,
            existing=base_workflow(
                selected_backend="UNSET",
                next_stage="research-execution",
                research_state="RESEARCH_BLOCKED",
                analysis_goal="DECIDE",
                blocking_reason={"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]},
                call_counts={"RES-001": {"search": 1, "fetch": 0, "map": 0}},
            ),
            native_reply="SILENT",
        ),
        {"selected_backend": "UNSET", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution", "blocking_reason": {"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]}},
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "resume-unset-problem-framing-task-block-silent-preserves-task-ids",
            "RESUME",
            True,
            existing=base_workflow(
                selected_backend="UNSET",
                next_stage="problem-framing",
                research_state="RESEARCH_BLOCKED",
                blocking_reason={
                    "code": "NO_AUTHORIZED_TASK_ROUTE",
                    "task_ids": ["RES-001"],
                },
                call_counts={"RES-001": {"search": 0, "fetch": 0, "map": 0}},
            ),
            native_reply="SILENT",
        ),
        {
            "selected_backend": "UNSET",
            "native_fallback_approved": False,
            "research_state": "RESEARCH_BLOCKED",
            "next_stage": "problem-framing",
            "blocking_reason": {
                "code": "NO_AUTHORIZED_TASK_ROUTE",
                "task_ids": ["RES-001"],
            },
        },
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "resume-execution-zero-empty-block-is-not-entry-preflight",
            "RESUME",
            True,
            existing=base_workflow(
                selected_backend="UNSET",
                next_stage="research-execution",
                research_state="RESEARCH_BLOCKED",
                analysis_goal="DECIDE",
                blocking_reason={"code": "MISSING_OR_INVALID_ARTIFACT", "task_ids": []},
                call_counts={"RES-001": {"search": 0, "fetch": 0, "map": 0}},
            ),
            mcp_reachable=True,
            search_configured=True,
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution", "blocking_reason": {"code": "MISSING_OR_INVALID_ARTIFACT", "task_ids": []}},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario(
            "resume-core-execution-block-native-approved",
            "RESUME",
            True,
            existing=base_workflow(
                selected_backend="RESEARCH_CORE",
                next_stage="research-execution",
                research_state="RESEARCH_BLOCKED",
                analysis_goal="DECIDE",
                blocking_reason={"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]},
                call_counts={"RES-001": {"search": 2, "fetch": 0, "map": 0}},
            ),
            native_reply="APPROVE",
        ),
        {"selected_backend": "HOST_NATIVE", "native_fallback_approved": True, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution", "blocking_reason": {"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]}},
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "resume-core-execution-block-silent-preserves-task-ids",
            "RESUME",
            True,
            existing=base_workflow(
                selected_backend="RESEARCH_CORE",
                next_stage="research-execution",
                research_state="RESEARCH_BLOCKED",
                analysis_goal="DECIDE",
                blocking_reason={"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]},
                call_counts={"RES-001": {"search": 2, "fetch": 0, "map": 0}},
            ),
            native_reply="SILENT",
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution", "blocking_reason": {"code": "NO_AUTHORIZED_TASK_ROUTE", "task_ids": ["RES-001"]}},
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "resume-native-still-authorized",
            "RESUME",
            True,
            existing=base_workflow(selected_backend="HOST_NATIVE", native_fallback_approved=True),
            mcp_reachable=True,
            search_configured=True,
        ),
        {"selected_backend": "HOST_NATIVE", "native_fallback_approved": True, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 0, "status": 0},
    ),
    (
        EntryScenario(
            "resume-native-revoked-core-restored",
            "RESUME",
            True,
            existing=base_workflow(selected_backend="HOST_NATIVE", native_fallback_approved=True),
            mcp_reachable=True,
            search_configured=True,
            revoke_native=True,
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 1, "status": 1},
    ),
    (
        EntryScenario(
            "resume-native-revoked-core-down",
            "RESUME",
            True,
            existing=base_workflow(
                selected_backend="HOST_NATIVE",
                native_fallback_approved=True,
                next_stage="research-execution",
                research_state="RESEARCH_IN_PROGRESS",
                call_counts={"RES-001": {"search": 1, "fetch": 0, "map": 0}},
            ),
            mcp_reachable=False,
            native_reply="SILENT",
            revoke_native=True,
        ),
        {"selected_backend": "UNSET", "native_fallback_approved": False, "research_state": "RESEARCH_BLOCKED", "next_stage": "research-execution"},
        {"reachability": 1, "status": 0},
    ),
    (
        EntryScenario(
            "create-invalid-file-valid-env",
            "CREATE",
            True,
            mcp_reachable=True,
            search_configured=True,
            config_state="INVALID",
        ),
        {"selected_backend": "RESEARCH_CORE", "native_fallback_approved": False, "research_state": "NOT_STARTED", "next_stage": "problem-framing"},
        {"reachability": 1, "status": 1, "warning": True},
    ),
]


@pytest.mark.parametrize(("scenario", "expected_state", "expected_calls"), SCENARIOS, ids=[case[0].name for case in SCENARIOS])
def test_entry_transition_matrix(
    scenario: EntryScenario,
    expected_state: dict[str, object],
    expected_calls: dict[str, object],
) -> None:
    original = copy.deepcopy(scenario.existing)

    state, calls = entry_transition(scenario)

    for key, value in expected_state.items():
        assert state[key] == value
    for key, value in expected_calls.items():
        assert calls[key] == value
    if scenario.existing is not None:
        assert scenario.existing == original
        assert state["call_counts"] == scenario.existing["call_counts"]
        assert state["artifact_refs"] == scenario.existing["artifact_refs"]


@pytest.mark.parametrize(
    ("name", "existing", "expected_state"),
    [
        (
            "all-predicates-hold",
            base_workflow(
                research_state="RESEARCH_BLOCKED",
                blocking_reason={
                    "code": "NO_AUTHORIZED_WEB_BACKEND",
                    "task_ids": [],
                },
            ),
            "NOT_STARTED",
        ),
        (
            "stage-is-not-problem-framing",
            base_workflow(
                next_stage="research-execution",
                analysis_goal="UNDERSTAND",
                research_state="RESEARCH_BLOCKED",
                blocking_reason={
                    "code": "NO_AUTHORIZED_WEB_BACKEND",
                    "task_ids": [],
                },
            ),
            "RESEARCH_BLOCKED",
        ),
        (
            "an-operation-count-is-nonzero",
            base_workflow(
                research_state="RESEARCH_BLOCKED",
                blocking_reason={
                    "code": "NO_AUTHORIZED_WEB_BACKEND",
                    "task_ids": [],
                },
                call_counts={"RES-001": {"search": 1, "fetch": 0, "map": 0}},
            ),
            "RESEARCH_BLOCKED",
        ),
        (
            "blocking-task-ids-are-not-empty",
            base_workflow(
                research_state="RESEARCH_BLOCKED",
                blocking_reason={
                    "code": "NO_AUTHORIZED_TASK_ROUTE",
                    "task_ids": ["RES-001"],
                },
                call_counts={"RES-001": {"search": 0, "fetch": 0, "map": 0}},
            ),
            "RESEARCH_BLOCKED",
        ),
    ],
)
def test_entry_preflight_recovery_requires_each_predicate_independently(
    project_root: Path,
    name: str,
    existing: dict[str, object],
    expected_state: str,
) -> None:
    scenario = EntryScenario(
        name,
        "RESUME",
        True,
        existing=existing,
        mcp_reachable=True,
        search_configured=True,
    )

    validate_workflow_shape(project_root, existing)
    state, calls = entry_transition(scenario)

    assert state["selected_backend"] == "RESEARCH_CORE"
    assert state["research_state"] == expected_state
    assert calls == {"reachability": 1, "status": 1, "warning": False}
    if expected_state == "NOT_STARTED":
        assert "blocking_reason" not in state
    else:
        assert state["blocking_reason"] == existing["blocking_reason"]


@pytest.mark.parametrize("reply", ["REJECT", "SILENT"])
def test_problem_framing_task_scoped_block_is_schema_valid_and_preserved(
    project_root: Path, reply: Reply
) -> None:
    existing = base_workflow(
        selected_backend="UNSET",
        next_stage="problem-framing",
        research_state="RESEARCH_BLOCKED",
        blocking_reason={
            "code": "NO_AUTHORIZED_TASK_ROUTE",
            "task_ids": ["RES-001"],
        },
        call_counts={"RES-001": {"search": 0, "fetch": 0, "map": 0}},
    )
    scenario = EntryScenario(
        f"problem-framing-task-block-{reply.lower()}",
        "RESUME",
        True,
        existing=existing,
        native_reply=reply,
    )

    validate_workflow_shape(project_root, existing)
    state, calls = entry_transition(scenario)

    assert state["blocking_reason"] == existing["blocking_reason"]
    assert state["research_state"] == "RESEARCH_BLOCKED"
    assert state["next_stage"] == "problem-framing"
    assert calls == {"reachability": 1, "status": 0, "warning": False}


def test_entry_skill_declares_the_same_hard_gates(project_root: Path) -> None:
    entry = (project_root / "skills/problem-navigator/SKILL.md").read_text("utf-8")
    control = (
        project_root / "skills/problem-navigator/references/workflow-control.md"
    ).read_text("utf-8")
    for phrase in (
        "CREATE",
        "RESUME",
        "references/workflow-control.md",
        "Pure reasoning/user materials",
        "Any relevant configured capability",
        "generic search is",
        "not a universal prerequisite",
        "RESEARCH_CORE + false",
        "HOST_NATIVE + true",
        "UNSET + false",
        "RESEARCH_BLOCKED",
        "blocking_reason",
        "task_ids: []",
    ):
        assert phrase in entry
    for backend in ("NONE", "UNSET", "RESEARCH_CORE", "HOST_NATIVE"):
        assert backend in entry
    for backend in ("NONE", "RESEARCH_CORE", "HOST_NATIVE"):
        assert backend in control

    assert entry.index("Pure reasoning/user materials") < entry.index("MCP reachability")
    text = entry
    assert "不运行 MCP" in text or "不得检查 MCP" in text
    assert "不 framing" in text or "不执行 framing" in text
    assert "不搜索" in text
    assert "不生成 evidence" in text or "不生成证据" in text


def test_framing_profile_mapping_is_declared_by_skill_and_schema(
    project_root: Path,
) -> None:
    import json

    from jsonschema import Draft202012Validator, ValidationError

    text = (project_root / "skills/problem-framing/SKILL.md").read_text("utf-8")
    schema = json.loads(
        (
            project_root
            / "skills/problem-navigator/references/artifacts.schema.json"
        ).read_text("utf-8")
    )
    frame_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": schema["$defs"],
        "$ref": "#/$defs/problem_frame",
    }
    base_frame = {
        "schema_version": 1,
        "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
        "problem_frame_id": "PF-001",
        "problem_frame_version": 1,
        "analysis_goal": "DECIDE",
        "content_profile": "GENERAL",
        "clarified_problem": "A confirmed problem.",
        "goal": "Reach a decision.",
        "scope": [],
        "non_goals": [],
        "constraints": [],
        "assumptions": [],
        "delivery_endpoint": "REPORT",
        "user_confirmation_status": "ACCEPTED",
    }

    assert "Both `PRODUCT` and `SOFTWARE` inputs map to the single `PRODUCT_SOFTWARE` profile" in text
    for profile in ("GENERAL", "PRODUCT_SOFTWARE"):
        Draft202012Validator(frame_schema).validate(
            {**base_frame, "content_profile": profile}
        )
    for forbidden_profile in ("PRODUCT", "SOFTWARE"):
        with pytest.raises(ValidationError):
            Draft202012Validator(frame_schema).validate(
                {**base_frame, "content_profile": forbidden_profile}
            )


def test_semantic_gate_covers_cross_artifact_invariants_without_relisting_enums(
    project_root: Path,
) -> None:
    text = (
        project_root
        / "skills/problem-navigator/references/evidence-package-validation.md"
    ).read_text("utf-8")
    required_phrases = (
        "analysis_goal",
        "Workflow/frame/brief/draft or package",
        "content_profile",
        "same task",
        "base_evidence_revision +1",
        "adds at most four tasks",
        "at most 16 overall",
        "later revisions are budget-bound",
        "reopen withdraws affected facts",
        "append preserves old definitions/counts",
        "UNDERSTAND",
        "WITH_RESULTS",
        "non-results and quality shortfalls",
        "Web workflows may",
        "PROVIDED_MATERIAL/PUBLIC_WEB",
    )
    for phrase in required_phrases:
        assert phrase in text

    assert "UNDERSTAND | DECIDE" not in text
    assert "PROVIDED_MATERIAL | PUBLIC_WEB" not in text


def _launder_source_across_tasks(graph: dict[str, dict[str, object]]) -> None:
    graph["prior_package"]["evidence_items"][0]["web_source_ids"] = ["SRC-002"]


def _launder_source_with_receipt_cover(
    graph: dict[str, dict[str, object]],
) -> None:
    for artifact_name, receipt_field in (
        ("prior_package", "execution_receipts"),
        ("current_draft", "completed_receipts"),
    ):
        artifact = graph[artifact_name]
        receipt = next(
            item for item in artifact[receipt_field] if item["task_id"] == "RES-001"
        )
        receipt["source_ids"] = ["SRC-001", "SRC-002"]
        evidence = next(
            item
            for item in artifact["evidence_items"]
            if item["evidence_item_id"] == "EVI-001"
        )
        evidence["web_source_ids"] = ["SRC-002"]


def _remove_task_quality_limitation(graph: dict[str, dict[str, object]]) -> None:
    graph["prior_package"]["limitations"] = []


def _drop_prior_task(graph: dict[str, dict[str, object]]) -> None:
    graph["current_brief"]["tasks"] = graph["current_brief"]["tasks"][1:]


def _rename_prior_task(graph: dict[str, dict[str, object]]) -> None:
    graph["current_brief"]["tasks"][0]["task_id"] = "RES-RENAMED"


def _add_more_than_four_supplemental_tasks(
    graph: dict[str, dict[str, object]],
) -> None:
    graph["current_brief"]["tasks"].extend(
        _web_task(f"RES-{index:03}", f"Supplemental question {index}?")
        for index in range(5, 9)
    )


def _duplicate_old_task_in_prior_brief(
    graph: dict[str, dict[str, object]],
) -> None:
    duplicate = _web_task("RES-001", "A structurally distinct old task duplicate?")
    graph["prior_brief"]["tasks"].append(copy.deepcopy(duplicate))
    graph["current_brief"]["tasks"][0] = copy.deepcopy(duplicate)


def _duplicate_old_task_in_current_brief(
    graph: dict[str, dict[str, object]],
) -> None:
    graph["current_brief"]["tasks"].append(
        _web_task("RES-001", "A current-only old task duplicate?")
    )


def _add_five_distinct_tasks_with_one_new_id(
    graph: dict[str, dict[str, object]],
) -> None:
    graph["current_brief"]["tasks"].extend(
        _web_task("RES-DUPLICATE", f"Distinct supplemental question {index}?")
        for index in range(1, 6)
    )


def test_base_revision_semantic_graph_is_structurally_valid_and_passes_oracle(
    project_root: Path,
) -> None:
    graph = base_revision_semantic_graph()
    assert "prior_brief" not in graph
    assert "prior_package" not in graph
    assert graph["current_brief"]["revision"] == 1
    assert graph["current_draft"]["brief_revision"] == 1
    assert graph["current_draft"]["base_evidence_revision"] == 0

    validate_graph_shapes(project_root, graph)
    validate_semantic_graph(graph)


def test_supplemental_semantic_graph_is_structurally_valid_and_passes_oracle(
    project_root: Path,
) -> None:
    graph = supplemental_semantic_graph()

    validate_graph_shapes(project_root, graph)
    validate_semantic_graph(graph)


def test_semantic_oracle_rejects_source_laundering_hidden_by_receipt(
    project_root: Path,
) -> None:
    graph = supplemental_semantic_graph()
    _launder_source_with_receipt_cover(graph)

    validate_graph_shapes(project_root, graph)
    with pytest.raises(SemanticGateViolation, match="call_ref"):
        validate_semantic_graph(graph)


@pytest.mark.parametrize(
    "mutate",
    [
        _duplicate_old_task_in_prior_brief,
        _duplicate_old_task_in_current_brief,
        _add_five_distinct_tasks_with_one_new_id,
    ],
    ids=[
        "duplicate-old-id-in-prior",
        "duplicate-old-id-in-current",
        "five-distinct-new-tasks-one-id",
    ],
)
def test_semantic_oracle_explicitly_rejects_duplicate_task_ids(
    project_root: Path, mutate
) -> None:
    graph = supplemental_semantic_graph()
    mutate(graph)

    validate_graph_shapes(project_root, graph)
    with pytest.raises(SemanticGateViolation, match="duplicate task_id"):
        validate_semantic_graph(graph)


@pytest.mark.parametrize(
    "mutate",
    [
        _launder_source_across_tasks,
        _remove_task_quality_limitation,
        _drop_prior_task,
        _rename_prior_task,
        _add_more_than_four_supplemental_tasks,
    ],
    ids=[
        "cross-task-source-laundering",
        "quality-false-without-task-limitation",
        "supplemental-drops-prior-task",
        "supplemental-renames-prior-task",
        "supplemental-adds-more-than-four",
    ],
)
def test_semantic_oracle_rejects_hostile_graph_mutations(
    project_root: Path, mutate
) -> None:
    graph = supplemental_semantic_graph()
    mutate(graph)

    validate_graph_shapes(project_root, graph)
    with pytest.raises(SemanticGateViolation):
        validate_semantic_graph(graph)


@pytest.mark.parametrize(
    ("prior_collection", "draft_collection"),
    [
        ("sources", "sources"),
        ("evidence_items", "evidence_items"),
    ],
    ids=["source", "evidence-item"],
)
def test_semantic_oracle_rejects_omitted_inherited_package_member(
    project_root: Path, prior_collection: str, draft_collection: str
) -> None:
    graph = supplemental_semantic_graph()
    assert graph["prior_package"][prior_collection]
    graph["current_draft"][draft_collection].pop()

    validate_graph_shapes(project_root, graph)
    with pytest.raises(SemanticGateViolation):
        validate_semantic_graph(graph)


def test_semantic_oracle_rejects_omitted_inherited_terminal_receipt_without_evidence(
    project_root: Path,
) -> None:
    graph = supplemental_semantic_graph()
    no_results_receipt = next(
        receipt
        for receipt in graph["current_draft"]["completed_receipts"]
        if receipt["task_id"] == "RES-003"
    )
    assert no_results_receipt["outcome"] == "NO_RESULTS"
    assert no_results_receipt["quality_met"] is False
    assert not any(
        evidence["task_id"] == "RES-003"
        for evidence in graph["current_draft"]["evidence_items"]
    )
    assert any(
        "RES-003" in limitation["affected_task_ids"]
        for limitation in graph["current_draft"]["limitations"]
    )
    graph["current_draft"]["completed_receipts"].remove(no_results_receipt)

    validate_graph_shapes(project_root, graph)
    with pytest.raises(
        SemanticGateViolation,
        match="supplemental draft omitted inherited execution_receipts member",
    ):
        validate_semantic_graph(graph)


def test_entry_skill_unset_resume_cannot_bypass_preflight(project_root: Path) -> None:
    text = (project_root / "skills/problem-navigator/SKILL.md").read_text("utf-8")
    normalized = " ".join(text.split())

    assert "For Web create UNSET first" in normalized
    assert "MCP reachability" in text
    assert "web_research_status" in text
    assert "Recheck Web only before new Web work" in normalized
    assert "entry-preflight" in text
    assert "restores NOT_STARTED only with zero calls" in normalized
    assert "empty blocking task IDs" in normalized
    assert "Execution blocks retain draft, counts and execution stage" in normalized


def test_entry_resume_uses_shared_control_and_preserves_recovery_boundaries(
    project_root: Path,
) -> None:
    entry = (project_root / "skills/problem-navigator/SKILL.md").read_text("utf-8")
    control = (
        project_root / "skills/problem-navigator/references/workflow-control.md"
    ).read_text("utf-8")
    for phrase in (
        "Preserve IDs/counts",
        "Valid unrevoked host consent persists",
        "Revocation first clears HOST_NATIVE authorization",
        "Execution blocks retain draft",
        "Never guess missing history",
    ):
        assert phrase in entry
    for phrase in (
        "regenerate the earliest invalid producer",
        "preserving counts",
        "Missing/corrupt evidence is not reconstructed from memory",
        "No stale accepted downstream binding survives upstream changes",
    ):
        assert phrase in control


def test_framing_skill_has_one_artifact_and_atomic_handoff(project_root: Path) -> None:
    text = (project_root / "skills/problem-framing/SKILL.md").read_text("utf-8")

    required_fields = (
        "workflow_id",
        "problem_frame_id",
        "problem_frame_version",
        "analysis_goal",
        "content_profile",
        "clarified_problem",
        "goal",
        "scope",
        "non_goals",
        "constraints",
        "assumptions",
        "delivery_endpoint",
        "user_confirmation_status",
    )
    for field in required_fields:
        assert field in text

    assert ".problem-navigator/artifacts/<workflow_id>/problem-frame.yaml" in text
    assert "PRODUCT" in text and "SOFTWARE" in text and "PRODUCT_SOFTWARE" in text
    assert "从零" in text and "DECIDE" in text
    assert "只问 `analysis_goal`" in text or "只询问 `analysis_goal`" in text
    assert text.index("原子写入 `problem-frame.yaml`") < text.index("更新 workflow YAML")
    assert "next_stage: research-design-kickoff" in text


def test_only_entry_allows_implicit_invocation(project_root: Path) -> None:
    entry = yaml.safe_load(
        (project_root / "adapters/codex/skills/problem-navigator/agents/openai.yaml").read_text("utf-8")
    )
    framing = yaml.safe_load(
        (project_root / "adapters/codex/skills/problem-framing/agents/openai.yaml").read_text("utf-8")
    )

    assert entry == {
        "interface": {
            "display_name": "Problem Navigator",
            "short_description": "Turn an idea into an evidence-backed report or spec",
            "default_prompt": "Use $problem-navigator to turn this idea into a researched, reviewed solution without implementation code.",
        },
        "policy": {"allow_implicit_invocation": True},
    }
    assert framing["interface"]["display_name"] == "Problem Framing"
    assert "$problem-framing" in framing["interface"]["default_prompt"]
    assert framing["policy"] == {"allow_implicit_invocation": False}


def test_skills_are_document_contracts_not_runtime_implementations(project_root: Path) -> None:
    for relative in (
        "skills/problem-navigator/SKILL.md",
        "skills/problem-framing/SKILL.md",
    ):
        text = (project_root / relative).read_text("utf-8").lower()
        assert "validator cli" not in text
        assert "version_graph:" not in text
        assert "versions:" not in text
        assert "artifact_id" not in text
        assert "implementation plan" not in text
        assert "tasks endpoint" not in text
