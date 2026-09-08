from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

from web_research.config import ConfigSnapshot, StatusResult, configuration_status
from web_research.core import FETCH_ROUTES, MAP_ROUTES, SEARCH_ROUTES
from web_research.models import Direction, Route as CoreRoute
from web_research.security import UnsafeUrlError, normalize_public_url


WORKFLOW_ID = "550e8400-e29b-41d4-a716-446655440000"
# These two fixtures retain the 2.0 per-operation/terminal-state model only for
# compatibility coverage of the old instruction oracles below.  Live 2.1 budget,
# recovery, and stop behavior is exercised through workflow_control.py.
LEGACY_2_0_BUDGETS = {"search": 4, "fetch": 3, "map": 2}
LEGACY_2_0_STOP_CODES = {
    "MISSING_OR_INVALID_ARTIFACT",
    "PUBLIC_WEB_REQUIRES_NEW_WORKFLOW",
    "SUPPLEMENTAL_LIMIT_REACHED",
    "RESEARCH_EXHAUSTED",
    "USER_CANCELLED",
}


class ContractViolation(AssertionError):
    """A test-only signal for a violated research-stage contract."""


def load_schema(project_root: Path) -> dict[str, object]:
    schema = json.loads(
        (
            project_root
            / "skills/problem-navigator/references/artifacts.schema.json"
        ).read_text("utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return schema


def validate_definition(
    schema: dict[str, object], definition: str, payload: dict[str, object]
) -> None:
    Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    ).validate(payload)


def public_web_task(
    task_id: str,
    *,
    direction: str = "auto",
    domains: list[str] | None = None,
    freshness: str = "",
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "theme_id": "THEME-001",
        "question": f"What evidence answers {task_id}?",
        "task_kind": "PUBLIC_WEB",
        "direction": direction,
        "domains": [] if domains is None else domains,
        "freshness": freshness,
        "quality_bar": "Retain a directly supported answer or disclose the gap.",
        "stop_condition": "The quality bar is met or every allowed path is terminal.",
    }


def provided_material_task(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "theme_id": "THEME-001",
        "question": f"What does the supplied material establish for {task_id}?",
        "task_kind": "PROVIDED_MATERIAL",
        "material_refs": [
            f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml"
        ],
        "quality_bar": "Retain only claims directly supported by accessible material.",
        "stop_condition": "The material is exhausted and gaps are disclosed.",
    }


def brief(
    tasks: list[dict[str, object]],
    revision: int = 1,
    *,
    goal: str = "DECIDE",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "revision": revision,
        "analysis_goal": goal,
        "tasks": tasks,
    }


def problem_frame(*, goal: str = "DECIDE") -> dict[str, object]:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "problem_frame_id": "PF-001",
        "problem_frame_version": 1,
        "analysis_goal": goal,
        "content_profile": "GENERAL",
        "clarified_problem": "Choose between bounded alternatives.",
        "goal": "Produce a supported decision.",
        "scope": ["Public evidence"],
        "non_goals": ["Implementation"],
        "constraints": ["Use the selected backend"],
        "assumptions": [],
        "delivery_endpoint": "DECISION",
        "user_confirmation_status": "ACCEPTED",
    }


def receipt(
    task_id: str,
    outcome: str,
    *,
    quality_met: bool = False,
    call_refs: list[str] | None = None,
    source_ids: list[str] | None = None,
    external_source_ids: list[str] | None = None,
    **extra: object,
) -> dict[str, object]:
    value: dict[str, object] = {
        "task_id": task_id,
        "outcome": outcome,
        "quality_met": quality_met,
        "call_refs": [] if call_refs is None else call_refs,
        "source_ids": [] if source_ids is None else source_ids,
        "external_source_ids": (
            [] if external_source_ids is None else external_source_ids
        ),
    }
    value.update(extra)
    return value


def zero_counts(task_ids: list[str]) -> dict[str, dict[str, int]]:
    return {
        task_id: {"search": 0, "fetch": 0, "map": 0}
        for task_id in task_ids
    }


def supplemental_request(backend: str = "RESEARCH_CORE") -> dict[str, object]:
    request: dict[str, object] = {
        "request_id": "SUP-001",
        "gap_kind": "PROVIDED_MATERIAL" if backend == "NONE" else "PUBLIC_FACT",
        "question": "What bounded evidence can change candidate eligibility?",
        "decision_impact": "The answer can reverse the candidate decision.",
        "affected_candidate_ids": ["CAN-001"],
    }
    if backend == "NONE":
        request["material_refs"] = ["inputs/new-evidence.md"]
    return request


def supplemental_task(
    task: dict[str, object], request_id: str = "SUP-001"
) -> dict[str, object]:
    return {**task, "supplemental_request_id": request_id}


def validate_brief_semantics(
    current_brief: dict[str, object],
    backend: str,
    *,
    prior_brief: dict[str, object] | None = None,
    supplemental_request: dict[str, object] | None = None,
    existing: bool = False,
) -> None:
    tasks = current_brief["tasks"]
    task_ids = [task["task_id"] for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ContractViolation("task IDs must be stable and unique")
    if any(not re.fullmatch(r"RES-[0-9]{3}", str(task_id)) for task_id in task_ids):
        raise ContractViolation("task IDs must use the stable RES-NNN form")
    if backend == "NONE" and any(
        task["task_kind"] != "PROVIDED_MATERIAL" for task in tasks
    ):
        raise ContractViolation("NONE permits only provided-material tasks")
    if backend != "NONE" and any(
        task["task_kind"] not in {"PROVIDED_MATERIAL", "PUBLIC_WEB"}
        for task in tasks
    ):
        raise ContractViolation("Web workflows contain an unknown task kind")

    if prior_brief is None:
        if existing:
            if current_brief["revision"] < 1 or not 1 <= len(tasks) <= 16:
                raise ContractViolation("an existing brief must stay within 16 tasks")
            return
        if current_brief["revision"] != 1 or not 1 <= len(tasks) <= 12:
            raise ContractViolation("initial brief must contain 1-12 tasks at revision 1")
        if any("supplemental_request_id" in task for task in tasks):
            raise ContractViolation("revision-1 tasks cannot reference a supplemental")
        return

    if current_brief["revision"] != prior_brief["revision"] + 1:
        raise ContractViolation("an appended brief must increment the prior revision")
    old_list = prior_brief["tasks"]
    if len(tasks) < len(old_list):
        raise ContractViolation("supplemental brief dropped an existing task")
    if tasks[: len(old_list)] != old_list:
        raise ContractViolation(
            "supplemental brief changed an existing task or reordered existing tasks"
        )
    new_tasks = tasks[len(old_list) :]
    if not 1 <= len(new_tasks) <= 4:
        raise ContractViolation("supplemental brief must add one to four tasks")
    if len(tasks) > 16:
        raise ContractViolation("the workflow may contain at most 16 research tasks")
    if supplemental_request is None:
        if any("supplemental_request_id" in task for task in new_tasks):
            raise ContractViolation("direct append tasks cannot cite a missing request")
        return
    expected_task_kind = (
        "PROVIDED_MATERIAL"
        if supplemental_request["gap_kind"] == "PROVIDED_MATERIAL"
        else "PUBLIC_WEB"
    )
    if any(task["task_kind"] != expected_task_kind for task in new_tasks):
        raise ContractViolation("request kind and appended task kinds do not match")
    if backend == "NONE" and supplemental_request["gap_kind"] != "PROVIDED_MATERIAL":
        raise ContractViolation("NONE requires a provided-material request")
    request_id = supplemental_request["request_id"]
    if any(task.get("supplemental_request_id") != request_id for task in new_tasks):
        raise ContractViolation("new tasks must carry the matching supplemental request ID")
    if supplemental_request["gap_kind"] == "PROVIDED_MATERIAL":
        carrier_refs = set(supplemental_request["material_refs"])
        task_ref_sets = [set(task["material_refs"]) for task in new_tasks]
        if any(not refs & carrier_refs for refs in task_ref_sets):
            raise ContractViolation(
                "each appended task must reference carrier material"
            )
        if not carrier_refs <= set().union(*task_ref_sets):
            raise ContractViolation(
                "appended tasks must cover every carrier material ref"
            )


Route = tuple[str, str, str]


def route_plan(
    operation: Literal["search", "fetch", "map"],
    *,
    direction: str = "auto",
    freshness: str = "",
    domains: tuple[str, ...] = (),
    query: str = "",
) -> list[Route]:
    """Execution-layer compatibility filter over Task 7's actual route tables."""
    if operation == "map":
        provider, _operation = MAP_ROUTES[CoreRoute.PRIMARY]
        return [("map", "primary", provider)]
    if operation == "fetch":
        routes = [
            ("fetch", route.value, FETCH_ROUTES[route][0])
            for route in (CoreRoute.PRIMARY, CoreRoute.ALTERNATE)
        ]
        return routes[1:] if query else routes

    selected_direction = Direction(direction)
    routes = [
        ("search", route.value, SEARCH_ROUTES[(selected_direction, route)][0])
        for route in (CoreRoute.PRIMARY, CoreRoute.ALTERNATE)
        if (selected_direction, route) in SEARCH_ROUTES
    ]

    def compatible(route: Route) -> bool:
        provider = route[2]
        if provider == "brave" and (
            domains or len(query) > 400 or len(query.split()) > 50
        ):
            return False
        if direction == "academic" and provider == "firecrawl":
            return not domains and not freshness
        return True

    return [route for route in routes if compatible(route)]


@dataclass
class CallLedger:
    """Legacy 2.0 count-cap fixture, not the live 2.1 shared-budget runtime."""

    counts: dict[str, dict[str, int]]

    def before_call(self, task_id: str, operation: str) -> None:
        if self.counts[task_id][operation] >= LEGACY_2_0_BUDGETS[operation]:
            raise ContractViolation(f"{operation} budget exhausted")
        # This mutation represents the required atomic YAML replacement.
        self.counts[task_id][operation] += 1


def execute_chain(
    task_id: str,
    operation: str,
    paths: list[Route],
    scripted_results: list[str],
    ledger: CallLedger,
) -> list[tuple[Route, str]]:
    calls: list[tuple[Route, str]] = []
    for path, result in zip(paths, scripted_results, strict=False):
        ledger.before_call(task_id, operation)
        calls.append((path, result))
        if result == "INVALID_REQUEST":
            break
        if result in {"SUCCESS", "QUALITY_MET"}:
            break
    return calls


def extend_counts_for_supplemental(
    workflow: dict[str, object],
    prior_brief: dict[str, object],
    current_brief: dict[str, object],
    request: dict[str, object],
) -> dict[str, dict[str, int]]:
    validate_brief_semantics(
        current_brief,
        workflow["selected_backend"],
        prior_brief=prior_brief,
        supplemental_request=request,
    )
    prior_counts = workflow["call_counts"]
    old_task_ids = [task["task_id"] for task in prior_brief["tasks"]]
    if set(prior_counts) != set(old_task_ids):
        raise ContractViolation("old call-count keys must exactly match old tasks")
    result = copy.deepcopy(prior_counts)
    for task in current_brief["tasks"]:
        if task["task_id"] not in old_task_ids:
            result[task["task_id"]] = {"search": 0, "fetch": 0, "map": 0}
    return result


def validate_recovery_partition(
    current_brief: dict[str, object],
    draft: dict[str, object],
    counts: dict[str, dict[str, int]],
    *,
    backend: str,
) -> None:
    brief_ids = [task["task_id"] for task in current_brief["tasks"]]
    completed_ids = [item["task_id"] for item in draft["completed_receipts"]]
    unfinished_ids = draft["unfinished_task_ids"]
    if len(completed_ids) != len(set(completed_ids)):
        raise ContractViolation("a task has more than one completed receipt")
    if set(completed_ids) & set(unfinished_ids):
        raise ContractViolation("completed and unfinished task sets overlap")
    if sorted(completed_ids + unfinished_ids) != sorted(brief_ids):
        raise ContractViolation("draft does not partition every brief task exactly once")
    if set(counts) != set(brief_ids):
        raise ContractViolation("call-count keys do not match the current brief")
    if backend == "NONE" and any(
        value != 0 for operations in counts.values() for value in operations.values()
    ):
        raise ContractViolation("NONE workflow contains a network count")


def blocked_workflow(
    workflow: dict[str, object], draft_ref: str, unfinished: list[str]
) -> dict[str, object]:
    result = copy.deepcopy(workflow)
    refs = result["artifact_refs"]
    refs.pop("evidence_package", None)
    refs["evidence_draft"] = draft_ref
    result["research_state"] = "RESEARCH_BLOCKED"
    result["next_stage"] = "research-execution"
    result["blocking_reason"] = {
        "code": "NO_AUTHORIZED_WEB_BACKEND",
        "task_ids": unfinished,
    }
    return result


def supplemental_draft(
    prior_package: dict[str, object], current_brief: dict[str, object]
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 1,
        "workflow_id": prior_package["workflow_id"],
        "brief_revision": current_brief["revision"],
        "base_evidence_revision": prior_package["evidence_revision"],
        "completed_receipts": copy.deepcopy(prior_package["execution_receipts"]),
        "sources": copy.deepcopy(prior_package["sources"]),
        "evidence_items": copy.deepcopy(prior_package["evidence_items"]),
        "limitations": copy.deepcopy(prior_package["limitations"]),
        "external_sources": copy.deepcopy(prior_package["external_sources"]),
        "unfinished_task_ids": [
            task["task_id"]
            for task in current_brief["tasks"]
            if task["task_id"]
            not in {
                item["task_id"] for item in prior_package["execution_receipts"]
            }
        ],
    }
    if "candidate_basis" in prior_package:
        value["candidate_basis"] = prior_package["candidate_basis"]
        value["candidates"] = copy.deepcopy(prior_package["candidates"])
    return value


def empty_evidence_draft(task_ids: list[str]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "brief_revision": 1,
        "base_evidence_revision": 0,
        "completed_receipts": [],
        "sources": [],
        "evidence_items": [],
        "limitations": [],
        "external_sources": [],
        "unfinished_task_ids": task_ids,
    }


def native_result_args(**overrides: str) -> dict[str, str]:
    return {
        "operation": "search",
        "stable_result_ref": "native-result-001",
        "url": "https://example.com/result",
        "fallback_reason": "Core routes were exhausted.",
    } | overrides


@dataclass(frozen=True)
class NativeApproval:
    serial: int
    task_ids: frozenset[str]


def begin_native_call(
    task_id: str,
    workflow: dict[str, object],
    approval: NativeApproval | None,
    consumed_approval_serials: set[int],
    ledger: CallLedger,
    operation: str,
) -> None:
    backend_pair = (
        workflow["selected_backend"],
        workflow["native_fallback_approved"],
    )
    if backend_pair == ("HOST_NATIVE", True):
        pass
    elif backend_pair == ("RESEARCH_CORE", False):
        if approval is None or task_id not in approval.task_ids:
            raise ContractViolation("task is outside the disclosed approval scope")
        # A current task-scoped authorization survives an interruption.  The serial
        # set is retained only so older fixtures can observe which consent was used.
        consumed_approval_serials.add(approval.serial)
    elif workflow["selected_backend"] == "HOST_NATIVE" or workflow[
        "native_fallback_approved"
    ]:
        raise ContractViolation("entry-level host approval pair is inconsistent or revoked")
    else:
        raise ContractViolation("workflow has no host-native path")
    ledger.before_call(task_id, operation)


def record_native_result_in_draft(
    schema: dict[str, object],
    workflow: dict[str, object],
    draft: dict[str, object],
    task_id: str,
    approval: NativeApproval | None,
    consumed_approval_serials: set[int],
    *,
    operation: str,
    stable_result_ref: str,
    url: str,
    fallback_reason: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object] | None]:
    """Count, persist, and validate one terminal native outcome."""
    updated = copy.deepcopy(draft)
    if task_id not in updated["unfinished_task_ids"] or any(
        item["task_id"] == task_id for item in updated["completed_receipts"]
    ):
        raise ContractViolation("native outcome must close one unfinished task once")
    if not fallback_reason.strip():
        raise ContractViolation("native result needs a non-empty approval reason")
    begin_native_call(
        task_id,
        workflow,
        approval,
        consumed_approval_serials,
        CallLedger(workflow["call_counts"]),
        operation,
    )
    try:
        normalized_url = normalize_public_url(url) if stable_result_ref.strip() else None
    except UnsafeUrlError:
        normalized_url = None
    if normalized_url is None:
        result_source = None
        result_receipt = receipt(
            task_id,
            "FAILED",
            error_code="INVALID_REQUEST",
            fallback_authorization="USER_APPROVED",
            fallback_reason=fallback_reason,
        )
        updated["limitations"].append(
            {
                "limitation_id": f"LIM-{task_id}-HOST-RESULT",
                "affected_task_ids": [task_id],
                "affected_candidate_ids": [],
                "summary": (
                    "Host-native result lacked a stable reference or accepted public URL."
                ),
                "may_change_decision": True,
            }
        )
    else:
        source_id = f"SRC-{task_id}"
        result_source = {
            "source_id": source_id,
            "call_ref": stable_result_ref,
            "title": "Host-native public result",
            "normalized_url": normalized_url,
            "provider": "host_native",
            "source_type": "web",
            "retrieved_at": "2026-09-06T00:00:00Z",
        }
        result_receipt = receipt(
            task_id,
            "WITH_RESULTS",
            quality_met=True,
            call_refs=[stable_result_ref],
            source_ids=[source_id],
            fallback_authorization="USER_APPROVED",
            fallback_reason=fallback_reason,
        )
        updated["sources"].append(result_source)
        updated["evidence_items"].append(
            fact(f"EVI-{task_id}-HOST-RESULT", task_id, source_id)
        )
    updated["completed_receipts"].append(result_receipt)
    updated["unfinished_task_ids"].remove(task_id)
    task_map = {
        current_task_id: public_web_task(current_task_id)
        for current_task_id in workflow["call_counts"]
    }
    validate_definition(schema, "evidence_draft", updated)
    validate_recovery_partition(
        brief(list(task_map.values()), goal=workflow["analysis_goal"]),
        updated,
        workflow["call_counts"],
        backend=workflow["selected_backend"],
    )
    validate_evidence_semantics(
        updated,
        receipt_field="completed_receipts",
        task_map=task_map,
        analysis_goal=workflow["analysis_goal"],
    )
    return updated, result_receipt, result_source


def stopped_workflow(
    workflow: dict[str, object],
    *,
    research_state: str,
    code: str,
    task_ids: list[str],
) -> dict[str, object]:
    """Legacy 2.0 stop-pair oracle retained for schema compatibility cases."""
    if code not in LEGACY_2_0_STOP_CODES:
        raise ContractViolation("STOPPED transition requires a fixed blocking code")
    expected_state = {
        "PUBLIC_WEB_REQUIRES_NEW_WORKFLOW": "RESEARCH_CANCELLED",
        "USER_CANCELLED": "RESEARCH_CANCELLED",
        "RESEARCH_EXHAUSTED": "RESEARCH_FAILED",
        "SUPPLEMENTAL_LIMIT_REACHED": "RESEARCH_PARTIAL",
        "MISSING_OR_INVALID_ARTIFACT": workflow["research_state"],
    }[code]
    if research_state != expected_state or (
        code == "SUPPLEMENTAL_LIMIT_REACHED"
        and workflow["research_state"] != "RESEARCH_PARTIAL"
    ):
        raise ContractViolation("blocking reason does not match research state")
    result = copy.deepcopy(workflow)
    result["research_state"] = research_state
    result["next_stage"] = "STOPPED"
    result["blocking_reason"] = {"code": code, "task_ids": task_ids}
    return result


def base_workflow(
    *,
    backend: str = "RESEARCH_CORE",
    goal: str = "DECIDE",
    task_ids: list[str] | None = None,
) -> dict[str, object]:
    task_ids = ["RES-001"] if task_ids is None else task_ids
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "analysis_goal": goal,
        "next_stage": "research-execution",
        "selected_backend": backend,
        "native_fallback_approved": backend == "HOST_NATIVE",
        "research_state": "RESEARCH_IN_PROGRESS",
        "call_counts": zero_counts(task_ids),
        "artifact_refs": {
            "problem_frame": f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml",
            "research_brief": f".problem-navigator/artifacts/{WORKFLOW_ID}/research-brief.yaml",
            "evidence_draft": f".problem-navigator/artifacts/{WORKFLOW_ID}/evidence-draft.yaml",
        },
    }


def source(source_id: str, call_ref: str, url: str = "https://example.com/a") -> dict[str, object]:
    return {
        "source_id": source_id,
        "call_ref": call_ref,
        "title": "Source",
        "normalized_url": url,
        "provider": "exa",
        "source_type": "web",
        "retrieved_at": "2026-09-06T00:00:00Z",
    }


def external_source(
    external_source_id: str, task_id: str, artifact_ref: str,
    producer: str = "external",
) -> dict[str, object]:
    return {
        "external_source_id": external_source_id,
        "task_id": task_id,
        "kind": "document",
        "producer": producer,
        "artifact_ref": artifact_ref,
        "limitations": [],
    }


def fact(
    evidence_item_id: str,
    task_id: str,
    source_id: str,
    *,
    candidate_ids: list[str] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "evidence_item_id": evidence_item_id,
        "task_id": task_id,
        "kind": "FACT",
        "statement": f"Supported fact for {task_id}.",
        "web_source_ids": [source_id],
        "external_source_ids": [],
    }
    if candidate_ids is not None:
        value["candidate_ids"] = candidate_ids
    return value


def validate_evidence_semantics(
    artifact: dict[str, object],
    *,
    receipt_field: str,
    task_map: dict[str, dict[str, object]],
    analysis_goal: str,
    declared_state: str | None = None,
) -> str | None:
    """Shared package/draft closure oracle used by the Task 9 handoff tests."""

    def unique_index(
        members: list[dict[str, object]], key: str
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for member in members:
            member_id = member[key]
            if member_id in result:
                raise ContractViolation(f"duplicate stable identifier {member_id}")
            result[member_id] = member
        return result

    receipts = unique_index(artifact[receipt_field], "task_id")
    if not set(receipts).issubset(task_map):
        raise ContractViolation("receipt cites a task outside the brief")
    sources = unique_index(artifact["sources"], "source_id")
    external_sources = unique_index(
        artifact["external_sources"], "external_source_id"
    )
    evidence_items = unique_index(artifact["evidence_items"], "evidence_item_id")
    limitations = unique_index(artifact["limitations"], "limitation_id")
    candidates = unique_index(artifact.get("candidates", []), "candidate_id")

    evidence_by_task: dict[str, list[dict[str, object]]] = {
        task_id: [] for task_id in receipts
    }
    for item in evidence_items.values():
        task_id = item["task_id"]
        if task_id not in receipts:
            raise ContractViolation("evidence cites a task without a terminal receipt")
        item_receipt = receipts[task_id]
        if not set(item["web_source_ids"]).issubset(item_receipt["source_ids"]):
            raise ContractViolation("evidence Web source is outside its task receipt")
        if not set(item["external_source_ids"]).issubset(
            item_receipt["external_source_ids"]
        ):
            raise ContractViolation("external evidence is outside its task receipt")
        if not set(item.get("candidate_ids", [])).issubset(candidates):
            raise ContractViolation("evidence cites an unknown candidate")
        evidence_by_task[task_id].append(item)

    limited_tasks: set[str] = set()
    comparison_coverage: set[tuple[str, str]] = set()
    for limitation in limitations.values():
        affected_tasks = set(limitation["affected_task_ids"])
        affected_candidates = set(limitation["affected_candidate_ids"])
        if not affected_tasks.issubset(task_map):
            raise ContractViolation("limitation cites a task outside the brief")
        if not affected_candidates.issubset(candidates):
            raise ContractViolation("limitation cites an unknown candidate")
        limited_tasks.update(affected_tasks)
        comparison_coverage.update(
            (candidate_id, task_map[task_id]["theme_id"])
            for candidate_id in affected_candidates
            for task_id in affected_tasks
        )

    for task_id, item_receipt in receipts.items():
        if item_receipt["outcome"] != "WITH_RESULTS" and (
            item_receipt["source_ids"]
            or item_receipt["external_source_ids"]
            or evidence_by_task[task_id]
        ):
            raise ContractViolation(
                "non-result receipt cannot retain sources or evidence"
            )
        for source_id in item_receipt["source_ids"]:
            if source_id not in sources:
                raise ContractViolation("receipt cites a missing Web source")
            if sources[source_id]["call_ref"] not in item_receipt["call_refs"]:
                raise ContractViolation("Web source call ref is outside its receipt")
        for external_id in item_receipt["external_source_ids"]:
            if external_id not in external_sources:
                raise ContractViolation("receipt cites a missing external source")
            if external_sources[external_id]["task_id"] != task_id:
                raise ContractViolation("external source belongs to another task")
        if item_receipt["outcome"] == "WITH_RESULTS" and not evidence_by_task[task_id]:
            raise ContractViolation("successful receipt has no evidence item")
        if (
            item_receipt["outcome"] != "WITH_RESULTS"
            or item_receipt["quality_met"] is False
        ) and task_id not in limited_tasks:
            raise ContractViolation("task shortfall has no same-task limitation")

    for item in evidence_items.values():
        task_id = item["task_id"]
        if item["kind"] in {"UNKNOWN", "ASSUMPTION"} and task_id not in limited_tasks:
            raise ContractViolation("uncertain evidence has no applicable limitation")
        comparison_coverage.update(
            (candidate_id, task_map[task_id]["theme_id"])
            for candidate_id in item.get("candidate_ids", [])
        )

    for source_id, item in sources.items():
        owners = [entry for entry in receipts.values() if source_id in entry["source_ids"]]
        if not owners:
            raise ContractViolation("Web source has no terminal receipt owner")
        if item["provider"] == "host_native" and any(
            entry.get("fallback_authorization") != "USER_APPROVED"
            or not str(entry.get("fallback_reason", "")).strip()
            for entry in owners
        ):
            raise ContractViolation("host-native source lacks same-task approval metadata")

    for external_id, item in external_sources.items():
        item_receipt = receipts.get(item["task_id"])
        if item_receipt is None or external_id not in item_receipt["external_source_ids"]:
            raise ContractViolation("external source has no same-task receipt owner")

    if analysis_goal == "DECIDE":
        required_comparisons = {
            (candidate_id, task["theme_id"])
            for candidate_id in candidates
            for task in task_map.values()
        }
        if not required_comparisons.issubset(comparison_coverage):
            raise ContractViolation("DECIDE candidate comparison coverage is incomplete")

    has_retainable_evidence = any(
        item["kind"] in {"FACT", "INFERENCE"}
        and receipts[item["task_id"]]["outcome"] == "WITH_RESULTS"
        for item in evidence_items.values()
    )
    has_shortfall = any(
        item["outcome"] != "WITH_RESULTS" or item["quality_met"] is False
        for item in receipts.values()
    ) or any(
        item["kind"] in {"UNKNOWN", "ASSUMPTION"}
        for item in evidence_items.values()
    )
    derived_state = (
        "RESEARCH_PARTIAL"
        if has_retainable_evidence and has_shortfall
        else "RESEARCH_COMPLETE"
        if has_retainable_evidence
        else None
    )
    if declared_state is not None and declared_state != derived_state:
        raise ContractViolation("declared research state does not match receipts/evidence")
    return derived_state


def validate_supplemental_input_semantics(
    workflow: dict[str, object],
    current_frame: dict[str, object],
    prior_brief: dict[str, object],
    prior_package: dict[str, object],
    readiness: dict[str, object],
) -> None:
    """Independent oracle for the shared semantic gate plus supplemental status."""
    task_ids = [task["task_id"] for task in prior_brief["tasks"]]
    validate_brief_semantics(
        prior_brief, workflow["selected_backend"], existing=True
    )
    if workflow["next_stage"] != "research-design-kickoff":
        raise ContractViolation("supplemental handoff starts at the wrong stage")
    if readiness["status"] != "NEEDS_SUPPLEMENTAL":
        raise ContractViolation("readiness does not authorize supplementation")
    request = readiness["supplemental_request"]

    artifacts = {
        "problem_frame": "problem-frame.yaml",
        "research_brief": "research-brief.yaml",
        "evidence_package": "evidence-package.yaml",
        "readiness_pack": "readiness-pack.yaml",
    }
    artifact_root = f".problem-navigator/artifacts/{WORKFLOW_ID}"
    for ref_name, filename in artifacts.items():
        if workflow["artifact_refs"].get(ref_name) != f"{artifact_root}/{filename}":
            raise ContractViolation(f"current {ref_name} reference is missing or stale")
    if "evidence_draft" in workflow["artifact_refs"]:
        raise ContractViolation("old package and draft cannot both be current")

    if len(
        {
            workflow["workflow_id"],
            current_frame["workflow_id"],
            prior_brief["workflow_id"],
            prior_package["workflow_id"],
            readiness["workflow_id"],
        }
    ) != 1:
        raise ContractViolation("supplemental inputs use different workflows")
    if len(
        {
            workflow["analysis_goal"],
            current_frame["analysis_goal"],
            prior_brief["analysis_goal"],
            prior_package["analysis_goal"],
        }
    ) != 1:
        raise ContractViolation("supplemental inputs use different analysis goals")
    if prior_package["research_state"] != workflow["research_state"]:
        raise ContractViolation("workflow and package research states disagree")
    if not (
        prior_brief["revision"]
        == prior_package["brief_revision"]
        == readiness["brief_revision"]
    ):
        raise ContractViolation("supplemental inputs disagree on brief revision")
    if prior_package["evidence_revision"] != readiness["evidence_revision"]:
        raise ContractViolation("readiness does not reference the current package")
    candidate_ids = {item["candidate_id"] for item in prior_package["candidates"]}
    if not set(request["affected_candidate_ids"]) <= candidate_ids:
        raise ContractViolation("supplemental request cites an unknown candidate")
    if (
        workflow["selected_backend"] == "NONE"
        and request["gap_kind"] != "PROVIDED_MATERIAL"
    ):
        raise ContractViolation("NONE requires a provided-material request")
    if set(workflow["call_counts"]) != set(task_ids):
        raise ContractViolation("old call-count keys must exactly match old tasks")
    if workflow["selected_backend"] == "NONE" and any(
        value
        for counts in workflow["call_counts"].values()
        for value in counts.values()
    ):
        raise ContractViolation("NONE supplemental input has a network count")

    receipts: dict[str, dict[str, object]] = {}
    for item in prior_package["execution_receipts"]:
        if item["task_id"] in receipts:
            raise ContractViolation("old package has a duplicate terminal receipt")
        receipts[item["task_id"]] = item
    if set(receipts) != set(task_ids):
        raise ContractViolation("old package needs exactly one receipt per old task")

    task_map = {task["task_id"]: task for task in prior_brief["tasks"]}
    validate_evidence_semantics(
        prior_package,
        receipt_field="execution_receipts",
        task_map=task_map,
        analysis_goal=prior_package["analysis_goal"],
        declared_state=prior_package["research_state"],
    )

    disposition_ids = [
        disposition["limitation_id"]
        for disposition in readiness["limitation_dispositions"]
    ]
    limitation_ids = [item["limitation_id"] for item in prior_package["limitations"]]
    if len(disposition_ids) != len(set(disposition_ids)):
        raise ContractViolation("readiness has duplicate limitation dispositions")
    if set(disposition_ids) != set(limitation_ids):
        raise ContractViolation("readiness needs exactly one disposition per limitation")


def validate_supplemental_output_semantics(
    old_workflow: dict[str, object],
    prior_brief: dict[str, object],
    current_brief: dict[str, object],
    draft: dict[str, object],
    new_workflow: dict[str, object],
) -> None:
    old_ids = [task["task_id"] for task in prior_brief["tasks"]]
    all_ids = [task["task_id"] for task in current_brief["tasks"]]
    new_ids = all_ids[len(old_ids) :]
    if all_ids[: len(old_ids)] != old_ids:
        raise ContractViolation("supplemental output reordered an old task")
    if set(new_workflow["call_counts"]) != set(all_ids):
        raise ContractViolation("supplemental output has missing or extra count keys")
    for task_id in old_ids:
        if new_workflow["call_counts"][task_id] != old_workflow["call_counts"][task_id]:
            raise ContractViolation("supplemental output changed an old count value")
    if any(
        new_workflow["call_counts"][task_id] != {"search": 0, "fetch": 0, "map": 0}
        for task_id in new_ids
    ):
        raise ContractViolation("new supplemental tasks must start with zero counts")
    if draft["unfinished_task_ids"] != new_ids:
        raise ContractViolation("only newly appended tasks may be unfinished")


def partial_supplemental_inputs(
    backend: str = "RESEARCH_CORE",
) -> dict[str, dict[str, object]]:
    task_factory = provided_material_task if backend == "NONE" else public_web_task
    prior_brief = brief([task_factory("RES-001"), task_factory("RES-002")])
    result_receipt = (
        receipt(
            "RES-001",
            "WITH_RESULTS",
            quality_met=True,
            external_source_ids=["EXT-001"],
        )
        if backend == "NONE"
        else receipt(
            "RES-001",
            "WITH_RESULTS",
            quality_met=True,
            call_refs=["a" * 16],
            source_ids=["SRC-001"],
        )
    )
    empty_receipt = receipt("RES-002", "NO_RESULTS")
    limitation = {
        "limitation_id": "LIM-001",
        "affected_task_ids": ["RES-002"],
        "affected_candidate_ids": [],
        "summary": "No usable result was returned.",
        "may_change_decision": True,
    }
    package = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "brief_revision": 1,
        "evidence_revision": 4,
        "analysis_goal": "DECIDE",
        "research_state": "RESEARCH_PARTIAL",
        "neutral_synthesis": "One retained result and one material gap.",
        "candidate_basis": "The frame names one bounded candidate.",
        "candidates": [
            {"candidate_id": "CAN-001", "name": "A", "definition": "Candidate A"}
        ],
        "execution_receipts": [result_receipt, empty_receipt],
        "sources": [] if backend == "NONE" else [source("SRC-001", "a" * 16)],
        "evidence_items": [
            fact("EVI-001", "RES-001", "SRC-001", candidate_ids=["CAN-001"])
        ],
        "limitations": [limitation],
        "external_sources": (
            [
                external_source(
                    "EXT-001",
                    "RES-001",
                    f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml",
                    producer="user",
                )
            ]
            if backend == "NONE"
            else []
        ),
    }
    if backend == "NONE":
        package["evidence_items"][0].update(
            {"web_source_ids": [], "external_source_ids": ["EXT-001"]}
        )
    readiness = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "readiness_pack_id": "READY-001",
        "readiness_pack_version": 1,
        "brief_revision": 1,
        "evidence_revision": 4,
        "status": "NEEDS_SUPPLEMENTAL",
        "limitation_dispositions": [
            {
                "limitation_id": "LIM-001",
                "disposition": "CORRECTION_REQUESTED",
                "reason": "One public fact may change the decision.",
            }
        ],
        "value_conditions": [],
        "supplemental_request": supplemental_request(backend),
    }
    workflow = base_workflow(backend=backend, task_ids=["RES-001", "RES-002"])
    workflow.update(
        {
            "next_stage": "research-design-kickoff",
            "research_state": "RESEARCH_PARTIAL",
            "call_counts": zero_counts(["RES-001", "RES-002"])
            if backend == "NONE"
            else {
                "RES-001": {"search": 1, "fetch": 1, "map": 0},
                "RES-002": {"search": 2, "fetch": 0, "map": 0},
            },
            "artifact_refs": {
                "problem_frame": f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml",
                "research_brief": f".problem-navigator/artifacts/{WORKFLOW_ID}/research-brief.yaml",
                "evidence_package": f".problem-navigator/artifacts/{WORKFLOW_ID}/evidence-package.yaml",
                "readiness_pack": f".problem-navigator/artifacts/{WORKFLOW_ID}/readiness-pack.yaml",
            },
        }
    )
    return {
        "workflow": workflow,
        "problem_frame": problem_frame(),
        "prior_brief": prior_brief,
        "prior_package": package,
        "readiness": readiness,
    }


def supplemental_handoff(
    schema: dict[str, object],
    workflow: dict[str, object],
    current_frame: dict[str, object],
    prior_brief: dict[str, object],
    prior_package: dict[str, object],
    readiness: dict[str, object],
    new_tasks: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    for definition, payload in (
        ("workflow", workflow),
        ("problem_frame", current_frame),
        ("research_brief", prior_brief),
        ("evidence_package", prior_package),
        ("readiness_pack", readiness),
    ):
        validate_definition(schema, definition, payload)
    validate_supplemental_input_semantics(
        workflow, current_frame, prior_brief, prior_package, readiness
    )
    if not 1 <= len(new_tasks) <= 4:
        raise ContractViolation("supplemental handoff needs one to four new tasks")

    current_brief = brief(
        [*copy.deepcopy(prior_brief["tasks"]), *copy.deepcopy(new_tasks)],
        revision=prior_brief["revision"] + 1,
        goal=prior_brief["analysis_goal"],
    )
    validate_brief_semantics(
        current_brief,
        workflow["selected_backend"],
        prior_brief=prior_brief,
        supplemental_request=readiness["supplemental_request"],
    )
    draft = supplemental_draft(prior_package, current_brief)
    counts = extend_counts_for_supplemental(
        workflow, prior_brief, current_brief, readiness["supplemental_request"]
    )
    after = copy.deepcopy(workflow)
    after["call_counts"] = counts
    after["research_state"] = "RESEARCH_IN_PROGRESS"
    after["next_stage"] = "research-execution"
    after.pop("blocking_reason", None)
    after["artifact_refs"].pop("evidence_package", None)
    after["artifact_refs"].pop("readiness_pack", None)
    after["artifact_refs"]["evidence_draft"] = (
        f".problem-navigator/artifacts/{WORKFLOW_ID}/evidence-draft.yaml"
    )

    for definition, payload in (
        ("research_brief", current_brief),
        ("evidence_draft", draft),
        ("workflow", after),
    ):
        validate_definition(schema, definition, payload)
    validate_recovery_partition(
        current_brief, draft, counts, backend=workflow["selected_backend"]
    )
    validate_supplemental_output_semantics(
        workflow, prior_brief, current_brief, draft, after
    )
    return {"workflow": after, "brief": current_brief, "draft": draft}


def invalid_supplemental_handoff(
    schema: dict[str, object], inputs: dict[str, dict[str, object]]
) -> dict[str, object]:
    try:
        supplemental_handoff(
            schema,
            inputs["workflow"],
            inputs["problem_frame"],
            inputs["prior_brief"],
            inputs["prior_package"],
            inputs["readiness"],
            [public_web_task("RES-003")],
        )
    except (ContractViolation, ValidationError):
        known_task_ids = [
            task["task_id"]
            for task in inputs.get("prior_brief", {}).get("tasks", [])
            if re.fullmatch(r"RES-[0-9]{3}", str(task.get("task_id", "")))
        ]
        stopped = stopped_workflow(
            inputs["workflow"],
            research_state=inputs["workflow"]["research_state"],
            code="MISSING_OR_INVALID_ARTIFACT",
            task_ids=known_task_ids,
        )
        validate_definition(schema, "workflow", stopped)
        return stopped
    raise AssertionError("invalid supplemental input was accepted")


def publication_bundle(
    *, goal: str = "UNDERSTAND", partial: bool = False
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    task_ids = ["RES-001", "RES-002"] if partial else ["RES-001"]
    workflow = base_workflow(goal=goal, task_ids=task_ids)
    result_receipt = receipt(
        "RES-001",
        "WITH_RESULTS",
        quality_met=True,
        call_refs=["b" * 16],
        source_ids=["SRC-001"],
    )
    current_brief = brief(
        [public_web_task(task_id) for task_id in task_ids], goal=goal
    )
    draft: dict[str, object] = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "brief_revision": 1,
        "base_evidence_revision": 0,
        "completed_receipts": [result_receipt],
        "sources": [source("SRC-001", "b" * 16)],
        "evidence_items": [fact("EVI-001", "RES-001", "SRC-001")],
        "limitations": [],
        "external_sources": [],
        "unfinished_task_ids": [],
    }
    if goal == "DECIDE":
        draft["candidate_basis"] = "The frame names one bounded candidate."
        draft["candidates"] = [
            {"candidate_id": "CAN-001", "name": "A", "definition": "Candidate A"}
        ]
        draft["evidence_items"][0]["candidate_ids"] = ["CAN-001"]
    if partial:
        draft["completed_receipts"].append(receipt("RES-002", "NO_RESULTS"))
        draft["limitations"].append(
            {
                "limitation_id": "LIM-002",
                "affected_task_ids": ["RES-002"],
                "affected_candidate_ids": [],
                "summary": "No usable result was returned for RES-002.",
                "may_change_decision": True,
            }
        )
    return workflow, current_brief, draft


def render_understand_report(draft: dict[str, object]) -> str:
    outcomes = ", ".join(
        f"{item['task_id']}={item['outcome']}"
        for item in draft["completed_receipts"]
    )
    limitations = "; ".join(item["summary"] for item in draft["limitations"])
    return f"Research results: {outcomes}. Limitations: {limitations or 'none recorded'}."


def publish_evidence(
    schema: dict[str, object],
    workflow: dict[str, object],
    current_brief: dict[str, object],
    draft: dict[str, object],
    *,
    accepted: bool,
) -> tuple[dict[str, object], dict[str, object] | None]:
    validate_definition(schema, "workflow", workflow)
    validate_definition(schema, "research_brief", current_brief)
    validate_definition(schema, "evidence_draft", draft)
    if "neutral_synthesis" in draft:
        raise ContractViolation("draft cannot store neutral_synthesis")
    report = render_understand_report(draft)
    if workflow["analysis_goal"] == "UNDERSTAND" and not accepted:
        return copy.deepcopy(workflow), None

    state = validate_evidence_semantics(
        draft,
        receipt_field="completed_receipts",
        task_map={task["task_id"]: task for task in current_brief["tasks"]},
        analysis_goal=workflow["analysis_goal"],
    )
    if state is None:
        raise ContractViolation("no retainable evidence can be published")
    package = {
        "schema_version": 1,
        "workflow_id": draft["workflow_id"],
        "brief_revision": draft["brief_revision"],
        "evidence_revision": draft["base_evidence_revision"] + 1,
        "analysis_goal": workflow["analysis_goal"],
        "research_state": state,
        "neutral_synthesis": report,
        "execution_receipts": copy.deepcopy(draft["completed_receipts"]),
        "sources": copy.deepcopy(draft["sources"]),
        "evidence_items": copy.deepcopy(draft["evidence_items"]),
        "limitations": copy.deepcopy(draft["limitations"]),
        "external_sources": copy.deepcopy(draft["external_sources"]),
    }
    if workflow["analysis_goal"] == "DECIDE":
        package["candidate_basis"] = draft["candidate_basis"]
        package["candidates"] = copy.deepcopy(draft["candidates"])
    after = copy.deepcopy(workflow)
    after["research_state"] = state
    after["next_stage"] = (
        "DONE"
        if workflow["analysis_goal"] == "UNDERSTAND"
        else "decision-readiness-interview"
    )
    after.pop("blocking_reason", None)
    after["artifact_refs"].pop("evidence_draft", None)
    after["artifact_refs"]["evidence_package"] = (
        f".problem-navigator/artifacts/{WORKFLOW_ID}/evidence-package.yaml"
    )
    validate_definition(schema, "evidence_package", package)
    validate_definition(schema, "workflow", after)
    return after, package


def resume_unfinished_task_ids(
    current_brief: dict[str, object],
    draft: dict[str, object],
    counts: dict[str, dict[str, int]],
    *,
    backend: str,
) -> list[str]:
    validate_recovery_partition(current_brief, draft, counts, backend=backend)
    call_log: list[str] = []
    for task_id in draft["unfinished_task_ids"]:
        call_log.append(task_id)
    return call_log


def core_execution_boundary(
    workflow: dict[str, object],
    task: dict[str, object],
    status: StatusResult,
) -> tuple[dict[str, object], list[tuple[str, object]]]:
    result = copy.deepcopy(workflow)
    log: list[tuple[str, object]] = [("web_research_status", status.model_dump())]
    task_id = task["task_id"]
    if status.capabilities.search != "CONFIGURED":
        result["research_state"] = "RESEARCH_BLOCKED"
        result["next_stage"] = "research-execution"
        result["blocking_reason"] = {
            "code": "NO_AUTHORIZED_WEB_BACKEND",
            "task_ids": [task_id],
        }
        return result, log

    providers = status.providers.model_dump()
    paths = [
        path
        for path in route_plan(
            "search",
            direction=task["direction"],
            freshness=task["freshness"],
            domains=tuple(task["domains"]),
            query=task["question"],
        )
        if providers[path[2]] == "CONFIGURED"
    ]
    if not paths:
        result["research_state"] = "RESEARCH_BLOCKED"
        result["next_stage"] = "research-execution"
        result["blocking_reason"] = {
            "code": "NO_AUTHORIZED_TASK_ROUTE",
            "task_ids": [task_id],
        }
        return result, log
    CallLedger(result["call_counts"]).before_call(task_id, "search")
    log.append(("web_search", paths[0]))
    return result, log


@pytest.mark.parametrize(
    ("operation", "direction", "freshness", "domains", "query", "first_route"),
    [
        ("search", "academic", "week", (), "papers", ("search", "alternate", "exa")),
        ("search", "academic", "", ("example.com",), "papers", ("search", "alternate", "exa")),
        ("search", "auto", "", ("example.com",), "facts", ("search", "alternate", "exa")),
        ("search", "news", "day", ("example.com",), "news", ("search", "alternate", "exa")),
        ("fetch", "auto", "", (), "passage", ("fetch", "alternate", "exa")),
    ],
)
def test_route_planner_skips_incompatible_primary_without_counting_call(
    operation: str,
    direction: str,
    freshness: str,
    domains: tuple[str, ...],
    query: str,
    first_route: Route,
) -> None:
    ledger = CallLedger(zero_counts(["RES-001"]))
    paths = route_plan(
        operation,
        direction=direction,
        freshness=freshness,
        domains=domains,
        query=query,
    )
    assert paths[0] == first_route
    assert ledger.counts["RES-001"] == {"search": 0, "fetch": 0, "map": 0}


def test_actual_invalid_request_stops_task_without_fallback() -> None:
    ledger = CallLedger(zero_counts(["RES-001"]))
    paths = route_plan("search", direction="auto")
    calls = execute_chain(
        "RES-001",
        "search",
        paths,
        ["INVALID_REQUEST", "SUCCESS"],
        ledger,
    )
    assert calls == [(paths[0], "INVALID_REQUEST")]
    assert ledger.counts["RES-001"]["search"] == 1


def test_legacy_2_0_budget_fixture_counts_failed_and_native_calls() -> None:
    """Keep the old cap oracle explicit; live 2.1 totals use workflow_control."""
    for operation, cap in LEGACY_2_0_BUDGETS.items():
        workflow = base_workflow(task_ids=["RES-001", "RES-002"])
        ledger = CallLedger(zero_counts(["RES-001", "RES-002"]))
        # One failed Core call counts, as do every subsequent native attempt.
        ledger.before_call("RES-001", operation)
        consumed: set[int] = set()
        for serial in range(1, cap):
            begin_native_call(
                "RES-001",
                workflow,
                NativeApproval(serial, frozenset({"RES-001"})),
                consumed,
                ledger,
                operation,
            )
        assert ledger.counts["RES-001"][operation] == cap
        assert ledger.counts["RES-002"][operation] == 0
        with pytest.raises(ContractViolation, match="budget exhausted"):
            begin_native_call(
                "RES-001",
                workflow,
                NativeApproval(cap + 1, frozenset({"RES-001"})),
                consumed,
                ledger,
                operation,
            )


def test_supplemental_adds_zero_counts_only_for_new_task_ids() -> None:
    old_brief = brief([public_web_task("RES-001"), public_web_task("RES-002")])
    new_brief = brief(
        [
            *copy.deepcopy(old_brief["tasks"]),
            supplemental_task(public_web_task("RES-003")),
        ],
        revision=2,
    )
    old_counts = zero_counts(["RES-001", "RES-002"])
    old_counts["RES-001"] = {"search": 3, "fetch": 1, "map": 1}
    workflow = base_workflow(task_ids=["RES-001", "RES-002"])
    workflow["call_counts"] = old_counts
    updated = extend_counts_for_supplemental(
        workflow, old_brief, new_brief, supplemental_request()
    )
    assert updated == {
        "RES-001": {"search": 3, "fetch": 1, "map": 1},
        "RES-002": {"search": 0, "fetch": 0, "map": 0},
        "RES-003": {"search": 0, "fetch": 0, "map": 0},
    }


def test_none_supplemental_keeps_provided_material_backend_and_zero_counts(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs("NONE")
    new_task = supplemental_task(provided_material_task("RES-003"))
    new_task["material_refs"].append("inputs/new-evidence.md")
    result = supplemental_handoff(
        schema,
        inputs["workflow"],
        inputs["problem_frame"],
        inputs["prior_brief"],
        inputs["prior_package"],
        inputs["readiness"],
        [new_task],
    )
    assert result["workflow"]["selected_backend"] == "NONE"
    assert [task["task_kind"] for task in result["brief"]["tasks"]] == [
        "PROVIDED_MATERIAL",
        "PROVIDED_MATERIAL",
        "PROVIDED_MATERIAL",
    ]
    assert result["workflow"]["call_counts"] == zero_counts(
        ["RES-001", "RES-002", "RES-003"]
    )


@pytest.mark.parametrize(
    ("carrier_refs", "task_ref_sets"),
    [
        (
            ["inputs/new-a.md"],
            [
                ["inputs/new-a.md"],
                [f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml"],
            ],
        ),
        (
            ["inputs/new-a.md", "inputs/new-b.md"],
            [
                [
                    "inputs/new-a.md",
                    f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml",
                ],
            ],
        ),
    ],
)
def test_none_supplemental_rejects_unbound_or_uncovered_carrier_material(
    project_root: Path,
    carrier_refs: list[str],
    task_ref_sets: list[list[str]],
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs("NONE")
    inputs["readiness"]["supplemental_request"]["material_refs"] = carrier_refs
    new_tasks = []
    for index, task_refs in enumerate(task_ref_sets, start=3):
        new_task = supplemental_task(provided_material_task(f"RES-{index:03d}"))
        new_task["material_refs"] = task_refs
        new_tasks.append(new_task)

    with pytest.raises(ContractViolation, match="carrier material"):
        supplemental_handoff(
            schema,
            inputs["workflow"],
            inputs["problem_frame"],
            inputs["prior_brief"],
            inputs["prior_package"],
            inputs["readiness"],
            new_tasks,
        )


def test_supplemental_handoff_requires_a_durable_request_carrier(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs()
    inputs["readiness"].pop("supplemental_request")
    with pytest.raises((ContractViolation, ValidationError)):
        supplemental_handoff(
            schema,
            inputs["workflow"],
            inputs["problem_frame"],
            inputs["prior_brief"],
            inputs["prior_package"],
            inputs["readiness"],
            [public_web_task("RES-003")],
        )


def test_supplemental_handoff_binds_every_new_task_to_the_current_request(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs()
    inputs["readiness"]["supplemental_request"] = supplemental_request()
    new_task = {
        **public_web_task("RES-003"),
        "supplemental_request_id": "SUP-001",
    }
    result = supplemental_handoff(
        schema,
        inputs["workflow"],
        inputs["problem_frame"],
        inputs["prior_brief"],
        inputs["prior_package"],
        inputs["readiness"],
        [new_task],
    )
    assert result["brief"]["tasks"][:2] == inputs["prior_brief"]["tasks"]
    assert result["brief"]["tasks"][2]["supplemental_request_id"] == "SUP-001"


@pytest.mark.parametrize(
    "case",
    ("missing_id", "wrong_id", "old_task_tagged", "unknown_candidate", "wrong_kind"),
)
def test_supplemental_handoff_rejects_request_binding_mismatches(
    project_root: Path, case: str
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs()
    inputs["readiness"]["supplemental_request"] = supplemental_request()
    new_task = {
        **public_web_task("RES-003"),
        "supplemental_request_id": "SUP-001",
    }
    if case == "missing_id":
        new_task.pop("supplemental_request_id")
    elif case == "wrong_id":
        new_task["supplemental_request_id"] = "SUP-999"
    elif case == "old_task_tagged":
        inputs["prior_brief"]["tasks"][0]["supplemental_request_id"] = "SUP-001"
    elif case == "unknown_candidate":
        inputs["readiness"]["supplemental_request"]["affected_candidate_ids"] = [
            "CAN-999"
        ]
    else:
        inputs["readiness"]["supplemental_request"]["gap_kind"] = (
            "PROVIDED_MATERIAL"
        )
        inputs["readiness"]["supplemental_request"]["material_refs"] = [
            "inputs/new-evidence.md"
        ]

    with pytest.raises((ContractViolation, ValidationError)):
        supplemental_handoff(
            schema,
            inputs["workflow"],
            inputs["problem_frame"],
            inputs["prior_brief"],
            inputs["prior_package"],
            inputs["readiness"],
            [new_task],
        )


def test_blocked_draft_is_the_only_current_evidence_reference() -> None:
    workflow = base_workflow()
    workflow["artifact_refs"]["evidence_package"] = "old/evidence-package.yaml"
    result = blocked_workflow(
        workflow, "current/evidence-draft.yaml", ["RES-001"]
    )
    assert result["artifact_refs"] == {
        "problem_frame": f".problem-navigator/artifacts/{WORKFLOW_ID}/problem-frame.yaml",
        "research_brief": f".problem-navigator/artifacts/{WORKFLOW_ID}/research-brief.yaml",
        "evidence_draft": "current/evidence-draft.yaml",
    }
    assert result["research_state"] == "RESEARCH_BLOCKED"
    assert result["next_stage"] == "research-execution"


def test_resume_partitions_every_task_exactly_once() -> None:
    current_brief = brief(
        [public_web_task("RES-001"), public_web_task("RES-002")]
    )
    draft = {
        "completed_receipts": [receipt("RES-001", "NO_RESULTS")],
        "unfinished_task_ids": ["RES-002"],
    }
    counts = zero_counts(["RES-001", "RES-002"])
    validate_recovery_partition(current_brief, draft, counts, backend="RESEARCH_CORE")

    draft["unfinished_task_ids"].append("RES-001")
    with pytest.raises(ContractViolation, match="overlap"):
        validate_recovery_partition(current_brief, draft, counts, backend="RESEARCH_CORE")


def test_supplemental_draft_inherits_package_and_base_revision() -> None:
    inputs = partial_supplemental_inputs()
    prior_package = inputs["prior_package"]
    current_brief = brief(
        [
            *copy.deepcopy(inputs["prior_brief"]["tasks"]),
            supplemental_task(public_web_task("RES-003")),
        ],
        revision=2,
    )
    draft = supplemental_draft(prior_package, current_brief)
    assert draft["base_evidence_revision"] == 4
    assert draft["brief_revision"] == 2
    assert draft["completed_receipts"] == prior_package["execution_receipts"]
    for field in (
        "sources",
        "evidence_items",
        "limitations",
        "external_sources",
        "candidate_basis",
        "candidates",
    ):
        assert draft[field] == prior_package[field]
    assert draft["unfinished_task_ids"] == ["RES-003"]
    assert draft["base_evidence_revision"] + 1 == 5


def test_none_draft_has_zero_network_counts() -> None:
    current_brief = brief([provided_material_task("RES-001")])
    counts = zero_counts(["RES-001"])
    draft = {
        "completed_receipts": [],
        "unfinished_task_ids": ["RES-001"],
    }
    validate_recovery_partition(current_brief, draft, counts, backend="NONE")
    counts["RES-001"]["fetch"] = 1
    with pytest.raises(ContractViolation, match="NONE workflow"):
        validate_recovery_partition(current_brief, draft, counts, backend="NONE")


def test_research_core_host_native_source_requires_scoped_user_approval(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    approved = NativeApproval(1, frozenset({"RES-001"}))
    with pytest.raises(ContractViolation, match="approval scope"):
        record_native_result_in_draft(
            schema,
            base_workflow(goal="UNDERSTAND"),
            empty_evidence_draft(["RES-001"]),
            "RES-001", None, set(), **native_result_args(),
        )
    with pytest.raises(ContractViolation, match="approval scope"):
        record_native_result_in_draft(
            schema,
            base_workflow(goal="UNDERSTAND", task_ids=["RES-002"]),
            empty_evidence_draft(["RES-002"]),
            "RES-002", approved, set(), **native_result_args(),
        )
    with pytest.raises(ContractViolation, match="non-empty approval reason"):
        record_native_result_in_draft(
            schema, base_workflow(goal="UNDERSTAND"),
            empty_evidence_draft(["RES-001"]), "RES-001", approved, set(),
            **native_result_args(fallback_reason=""),
        )


def test_task_level_native_fallback_keeps_global_research_core_backend(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    workflow = base_workflow(goal="UNDERSTAND", task_ids=["RES-001", "RES-002"])
    approval = NativeApproval(1, frozenset({"RES-001"}))
    updated, result_receipt, _source = record_native_result_in_draft(
        schema, workflow, empty_evidence_draft(["RES-001", "RES-002"]),
        "RES-001", approval, set(), **native_result_args(),
    )
    assert workflow["call_counts"]["RES-001"]["search"] == 1
    assert workflow["selected_backend"] == "RESEARCH_CORE"
    assert workflow["native_fallback_approved"] is False
    assert result_receipt["fallback_authorization"] == "USER_APPROVED"
    assert updated["evidence_items"][0]["task_id"] == "RES-001"


def test_entry_authorized_resume_uses_only_the_durable_workflow_pair(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    workflow = base_workflow(backend="HOST_NATIVE", goal="UNDERSTAND")
    validate_definition(schema, "workflow", workflow)
    assert "fallback_reason" not in workflow
    assert "entry_approval_reason" not in workflow

    updated, result_receipt, result_source = record_native_result_in_draft(
        schema,
        workflow,
        empty_evidence_draft(["RES-001"]),
        "RES-001",
        None,
        set(),
        **native_result_args(
            fallback_reason=(
                "Current entry authorization permits host-native research."
            )
        ),
    )

    assert workflow["call_counts"]["RES-001"]["search"] == 1
    assert result_receipt["fallback_authorization"] == "USER_APPROVED"
    assert result_receipt["fallback_reason"] == (
        "Current entry authorization permits host-native research."
    )
    assert result_source is not None
    assert updated["completed_receipts"] == [result_receipt]


@pytest.mark.parametrize(
    ("selected_backend", "native_fallback_approved"),
    (("HOST_NATIVE", False), ("RESEARCH_CORE", True)),
)
def test_entry_authorized_call_stops_when_durable_pair_is_revoked_or_inconsistent(
    project_root: Path,
    selected_backend: str,
    native_fallback_approved: bool,
) -> None:
    workflow = base_workflow(backend="HOST_NATIVE", goal="UNDERSTAND")
    workflow["selected_backend"] = selected_backend
    workflow["native_fallback_approved"] = native_fallback_approved

    with pytest.raises(ContractViolation, match="inconsistent or revoked"):
        record_native_result_in_draft(
            load_schema(project_root),
            workflow,
            empty_evidence_draft(["RES-001"]),
            "RES-001",
            None,
            set(),
            **native_result_args(),
        )
    assert workflow["call_counts"]["RES-001"] == {
        "search": 0,
        "fetch": 0,
        "map": 0,
    }


def test_execution_skill_declares_resumable_entry_authorization_contract(
    project_root: Path,
) -> None:
    execution = (
        project_root / "skills/research-execution/SKILL.md"
    ).read_text("utf-8")
    normalized = " ".join(execution.split())

    assert "Use already authorized host tools directly" in normalized
    assert "Every host receipt records fallback_authorization: USER_APPROVED" in normalized
    assert "Recheck scope/revocation" in normalized
    assert "interruptions alone do not require renewed consent" in normalized
    assert "globally HOST_NATIVE workflow preserves HOST_NATIVE + true" in normalized


@pytest.mark.parametrize(
    ("backend", "fallback_reason"),
    [
        ("RESEARCH_CORE", "Core fetch routes were exhausted."),
        ("HOST_NATIVE", "Entry disclosure approved host-native research."),
    ],
)
def test_native_receipt_records_task_reason_stable_ref_url_and_count(
    project_root: Path, backend: str, fallback_reason: str,
) -> None:
    workflow = base_workflow(backend=backend, goal="UNDERSTAND")
    approval = (
        None
        if backend == "HOST_NATIVE"
        else NativeApproval(1, frozenset({"RES-001"}))
    )
    updated, result_receipt, result_source = record_native_result_in_draft(
        load_schema(project_root), workflow, empty_evidence_draft(["RES-001"]),
        "RES-001", approval, set(),
        **native_result_args(
            operation="fetch",
            url="HTTPS://Example.COM:443/result#private-fragment",
            fallback_reason=fallback_reason,
        ),
    )
    assert result_source is not None
    assert workflow["call_counts"]["RES-001"]["fetch"] == 1
    assert result_receipt["task_id"] == "RES-001"
    assert result_receipt["fallback_authorization"] == "USER_APPROVED"
    assert result_receipt["fallback_reason"] == fallback_reason
    assert result_receipt["call_refs"] == ["native-result-001"]
    assert result_source["call_ref"] == "native-result-001"
    assert result_source["normalized_url"] == "https://example.com/result"
    assert result_source["provider"] == "host_native"
    assert updated["evidence_items"][0]["web_source_ids"] == ["SRC-RES-001"]


@pytest.mark.parametrize(
    ("stable_ref", "url"),
    [
        ("", "https://example.com/result"),
        ("native-result-001", "result-only"),
        ("native-result-001", "http://localhost/result"),
        ("native-result-001", "http://127.0.0.1/result"),
        ("native-result-001", "http://2130706433/result"),
        ("native-result-001", "https://user:pass@example.com/result"),
        ("native-result-001", "https://example.com:8443/result"),
        ("native-result-001", "https://example.com/result?access_token=secret"),
    ],
)
def test_native_result_without_stable_ref_or_accessible_url_is_only_a_limitation(
    project_root: Path, stable_ref: str, url: str
) -> None:
    schema = load_schema(project_root)
    workflow = base_workflow(goal="UNDERSTAND")
    updated, result_receipt, result_source = record_native_result_in_draft(
        schema, workflow, empty_evidence_draft(["RES-001"]), "RES-001",
        NativeApproval(1, frozenset({"RES-001"})), set(),
        **native_result_args(
            operation="fetch", stable_result_ref=stable_ref, url=url,
            fallback_reason="Core paths exhausted.",
        ),
    )
    assert result_receipt == receipt(
        "RES-001",
        "FAILED",
        error_code="INVALID_REQUEST",
        fallback_authorization="USER_APPROVED",
        fallback_reason="Core paths exhausted.",
    )
    assert result_source is None
    assert updated["completed_receipts"] == [result_receipt]
    assert updated["sources"] == []
    assert updated["external_sources"] == []
    assert updated["evidence_items"] == []
    assert updated["unfinished_task_ids"] == []
    assert updated["limitations"] == [{
        "limitation_id": "LIM-RES-001-HOST-RESULT",
        "affected_task_ids": ["RES-001"],
        "affected_candidate_ids": [],
        "summary": "Host-native result lacked a stable reference or accepted public URL.",
        "may_change_decision": True,
    }]


def test_interrupted_native_call_reuses_current_scoped_authorization() -> None:
    workflow = base_workflow()
    ledger = CallLedger(zero_counts(["RES-001"]))
    first_approval = NativeApproval(1, frozenset({"RES-001"}))
    consumed: set[int] = set()
    begin_native_call(
        "RES-001", workflow, first_approval, consumed, ledger, "search"
    )
    # Interruption alone does not revoke current workflow/task consent.
    begin_native_call(
        "RES-001", workflow, first_approval, consumed, ledger, "search"
    )
    assert ledger.counts["RES-001"]["search"] == 2


def test_research_brief_schema_enforces_task_field_oneof(project_root: Path) -> None:
    schema = load_schema(project_root)
    material = brief([provided_material_task("RES-001")])
    web = brief([public_web_task("RES-001")])
    validate_definition(schema, "research_brief", material)
    validate_definition(schema, "research_brief", web)

    mixed_fields = copy.deepcopy(material)
    mixed_fields["tasks"][0]["direction"] = "auto"
    mixed_fields["tasks"][0]["domains"] = []
    mixed_fields["tasks"][0]["freshness"] = ""
    with pytest.raises(ValidationError):
        validate_definition(schema, "research_brief", mixed_fields)


def test_initial_and_supplemental_brief_limits_and_stable_ids() -> None:
    initial = brief([public_web_task(f"RES-{index:03}") for index in range(1, 13)])
    validate_brief_semantics(initial, "RESEARCH_CORE")
    too_many = brief([public_web_task(f"RES-{index:03}") for index in range(1, 14)])
    with pytest.raises(ContractViolation, match="1-12"):
        validate_brief_semantics(too_many, "RESEARCH_CORE")

    supplemental = brief(
        [
            *copy.deepcopy(initial["tasks"]),
            *[
                supplemental_task(public_web_task(f"RES-{index:03}"))
                for index in range(13, 17)
            ],
        ],
        revision=2,
    )
    validate_brief_semantics(
        supplemental,
        "RESEARCH_CORE",
        prior_brief=initial,
        supplemental_request=supplemental_request(),
    )
    supplemental["tasks"][0]["question"] = "Silently changed question?"
    with pytest.raises(ContractViolation, match="changed an existing task"):
        validate_brief_semantics(
            supplemental,
            "RESEARCH_CORE",
            prior_brief=initial,
            supplemental_request=supplemental_request(),
        )


def test_later_brief_revisions_append_without_rewriting_prior_tasks() -> None:
    initial = brief([public_web_task("RES-001")])
    second = brief(
        [
            *copy.deepcopy(initial["tasks"]),
            supplemental_task(public_web_task("RES-002"), "SUP-001"),
        ],
        revision=2,
    )
    validate_brief_semantics(
        second,
        "RESEARCH_CORE",
        prior_brief=initial,
        supplemental_request=supplemental_request(),
    )
    third = brief(
        [
            *copy.deepcopy(second["tasks"]),
            supplemental_task(provided_material_task("RES-003"), "SUP-002"),
        ],
        revision=3,
    )
    material_request = supplemental_request()
    material_request.update(
        request_id="SUP-002",
        gap_kind="PROVIDED_MATERIAL",
        material_refs=third["tasks"][-1]["material_refs"],
    )
    validate_brief_semantics(
        third,
        "RESEARCH_CORE",
        prior_brief=second,
        supplemental_request=material_request,
    )

    direct_fourth = brief(
        [*copy.deepcopy(third["tasks"]), provided_material_task("RES-004")],
        revision=4,
    )
    validate_brief_semantics(
        direct_fourth,
        "RESEARCH_CORE",
        prior_brief=third,
    )


def test_web_backends_allow_mixed_material_and_public_tasks_but_none_stays_offline() -> None:
    mixed = brief(
        [public_web_task("RES-001"), provided_material_task("RES-002")]
    )
    for backend in ("RESEARCH_CORE", "HOST_NATIVE"):
        validate_brief_semantics(mixed, backend)
    with pytest.raises(ContractViolation, match="NONE permits only"):
        validate_brief_semantics(mixed, "NONE")


def test_none_path_receipt_closes_only_through_external_material() -> None:
    result = receipt(
        "RES-001",
        "WITH_RESULTS",
        quality_met=True,
        external_source_ids=["EXT-001"],
    )
    assert result["call_refs"] == []
    assert result["source_ids"] == []
    assert result["external_source_ids"] == ["EXT-001"]


@pytest.mark.parametrize(
    ("goal", "partial", "expected_state", "expected_stage"),
    [
        ("UNDERSTAND", False, "RESEARCH_COMPLETE", "DONE"),
        ("UNDERSTAND", True, "RESEARCH_PARTIAL", "DONE"),
        ("DECIDE", False, "RESEARCH_COMPLETE", "decision-readiness-interview"),
        ("DECIDE", True, "RESEARCH_PARTIAL", "decision-readiness-interview"),
    ],
)
def test_canonical_publication_replaces_draft_for_complete_and_partial(
    project_root: Path,
    goal: str,
    partial: bool,
    expected_state: str,
    expected_stage: str,
) -> None:
    schema = load_schema(project_root)
    workflow, current_brief, draft = publication_bundle(goal=goal, partial=partial)
    transitioned, package = publish_evidence(
        schema, workflow, current_brief, draft, accepted=True
    )
    assert package is not None
    assert transitioned["research_state"] == expected_state
    assert transitioned["next_stage"] == expected_stage
    assert "evidence_draft" not in transitioned["artifact_refs"]
    assert "evidence_package" in transitioned["artifact_refs"]
    assert package["research_state"] == expected_state
    if partial:
        assert package["evidence_items"]
        assert package["limitations"]


def test_supplemental_handoff_is_one_schema_valid_transition(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs()
    result = supplemental_handoff(
        schema,
        inputs["workflow"],
        inputs["problem_frame"],
        inputs["prior_brief"],
        inputs["prior_package"],
        inputs["readiness"],
        [supplemental_task(public_web_task("RES-003"))],
    )
    assert [task["task_id"] for task in result["brief"]["tasks"]] == [
        "RES-001",
        "RES-002",
        "RES-003",
    ]
    assert result["draft"]["base_evidence_revision"] == 4
    assert result["draft"]["completed_receipts"] == inputs["prior_package"][
        "execution_receipts"
    ]
    assert result["draft"]["unfinished_task_ids"] == ["RES-003"]
    assert result["workflow"]["call_counts"] == {
        "RES-001": {"search": 1, "fetch": 1, "map": 0},
        "RES-002": {"search": 2, "fetch": 0, "map": 0},
        "RES-003": {"search": 0, "fetch": 0, "map": 0},
    }
    assert result["workflow"]["research_state"] == "RESEARCH_IN_PROGRESS"
    assert result["workflow"]["next_stage"] == "research-execution"
    assert "evidence_package" not in result["workflow"]["artifact_refs"]
    assert "readiness_pack" not in result["workflow"]["artifact_refs"]
    assert "evidence_draft" in result["workflow"]["artifact_refs"]


@pytest.mark.parametrize("case", ("missing", "extra", "changed"))
def test_supplemental_output_gate_rejects_old_call_counts_mutation(
    project_root: Path, case: str
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs()
    result = supplemental_handoff(
        schema,
        inputs["workflow"],
        inputs["problem_frame"],
        inputs["prior_brief"],
        inputs["prior_package"],
        inputs["readiness"],
        [supplemental_task(public_web_task("RES-003"))],
    )
    if case == "missing":
        result["workflow"]["call_counts"].pop("RES-002")
    elif case == "extra":
        result["workflow"]["call_counts"]["RES-999"] = zero_counts(["RES-999"])[
            "RES-999"
        ]
    else:
        result["workflow"]["call_counts"]["RES-001"]["search"] = 0

    validate_definition(schema, "workflow", result["workflow"])
    with pytest.raises(ContractViolation, match="count"):
        validate_supplemental_output_semantics(
            inputs["workflow"],
            inputs["prior_brief"],
            result["brief"],
            result["draft"],
            result["workflow"],
        )


@pytest.mark.parametrize(
    "case",
    (
        "readiness_status",
        "goal_mismatch",
        "backend_boundary",
        "interrupted_prepublication",
        "stale_brief_ref",
        "missing_brief_ref",
        "stale_package_ref",
        "missing_package_ref",
        "stale_readiness_ref",
        "missing_readiness_ref",
        "missing_old_receipt",
        "duplicate_old_receipt",
        "missing_old_count",
        "extra_old_count",
        "source_closure",
        "evidence_closure",
        "limitation_closure",
        "derived_state",
        "unknown_without_limitation",
        "assumption_without_limitation",
        "unknown_evidence_candidate",
        "duplicate_candidate_id",
        "candidate_without_comparison_coverage",
        "no_results_retains_fact",
        "failed_retains_inference",
        "orphan_external_no_results",
        "orphan_external_failed",
        "orphan_external_not_run",
        "missing_readiness_disposition",
        "duplicate_readiness_disposition",
        "unknown_readiness_disposition",
    ),
)
def test_supplemental_semantic_gate_rejects_schema_valid_input_graph_defects(
    project_root: Path, case: str
) -> None:
    schema = load_schema(project_root)
    inputs = partial_supplemental_inputs()
    workflow = inputs["workflow"]
    package = inputs["prior_package"]

    if case == "readiness_status":
        inputs["readiness"]["status"] = "READY"
        inputs["readiness"].pop("supplemental_request")
    elif case == "goal_mismatch":
        inputs["prior_brief"]["analysis_goal"] = "UNDERSTAND"
    elif case == "backend_boundary":
        workflow["selected_backend"] = "NONE"
    elif case == "interrupted_prepublication":
        inputs["prior_brief"]["revision"] = 2
        inputs["prior_brief"]["tasks"].append(public_web_task("RES-003"))
    elif case.endswith("_ref"):
        artifact = case.removesuffix("_ref").removeprefix("stale_").removeprefix("missing_")
        ref_name = {
            "brief": "research_brief",
            "package": "evidence_package",
            "readiness": "readiness_pack",
        }[artifact]
        if case.startswith("stale_"):
            workflow["artifact_refs"][ref_name] = f"stale/{ref_name}.yaml"
        else:
            workflow["artifact_refs"].pop(ref_name)
    elif case == "missing_old_receipt":
        package["execution_receipts"].pop()
    elif case == "duplicate_old_receipt":
        package["execution_receipts"].append(receipt("RES-001", "NO_RESULTS"))
    elif case == "missing_old_count":
        workflow["call_counts"].pop("RES-002")
    elif case == "extra_old_count":
        workflow["call_counts"]["RES-999"] = {"search": 0, "fetch": 0, "map": 0}
    elif case == "source_closure":
        package["execution_receipts"][0]["source_ids"] = ["SRC-MISSING"]
    elif case == "evidence_closure":
        package["evidence_items"][0]["task_id"] = "RES-002"
    elif case == "limitation_closure":
        package["limitations"][0]["affected_task_ids"] = ["RES-999"]
    elif case == "derived_state":
        workflow["research_state"] = "RESEARCH_COMPLETE"
        package["research_state"] = "RESEARCH_COMPLETE"
    elif case in {"unknown_without_limitation", "assumption_without_limitation"}:
        package["evidence_items"][0]["kind"] = (
            "UNKNOWN" if case.startswith("unknown") else "ASSUMPTION"
        )
    elif case == "unknown_evidence_candidate":
        package["evidence_items"][0]["candidate_ids"] = ["CAN-999"]
    elif case == "duplicate_candidate_id":
        package["candidates"].append(
            {"candidate_id": "CAN-001", "name": "Duplicate", "definition": "B"}
        )
    elif case == "candidate_without_comparison_coverage":
        inputs["prior_brief"]["tasks"][1]["theme_id"] = "THEME-002"
    elif case == "no_results_retains_fact":
        package["execution_receipts"][1].update(
            {"call_refs": ["c" * 16], "source_ids": ["SRC-002"]}
        )
        package["sources"].append(source("SRC-002", "c" * 16))
        package["evidence_items"].append(
            fact("EVI-002", "RES-002", "SRC-002")
        )
    elif case == "failed_retains_inference":
        package["execution_receipts"][1].update(
            {
                "outcome": "FAILED",
                "error_code": "PROVIDER_ERROR",
                "external_source_ids": ["EXT-002"],
            }
        )
        package["external_sources"].append(
            external_source("EXT-002", "RES-002", "inputs/failed-result.yaml")
        )
        retained_inference = fact("EVI-002", "RES-002", "SRC-UNUSED")
        retained_inference.update(
            {
                "kind": "INFERENCE",
                "web_source_ids": [],
                "external_source_ids": ["EXT-002"],
            }
        )
        package["evidence_items"].append(retained_inference)
    elif case.startswith("orphan_external_"):
        outcome = case.removeprefix("orphan_external_").upper()
        orphan_receipt = package["execution_receipts"][1]
        orphan_receipt["outcome"] = outcome
        orphan_receipt.update(
            {"FAILED": {"error_code": "PROVIDER_ERROR"},
             "NOT_RUN": {"not_run_reason": "Task was intentionally not run."}}.get(
                outcome, {}
            )
        )
        package["external_sources"].append(
            external_source("EXT-002", "RES-002", "inputs/orphan-result.yaml")
        )
    elif case == "missing_readiness_disposition":
        inputs["readiness"]["limitation_dispositions"] = []
    elif case == "duplicate_readiness_disposition":
        inputs["readiness"]["limitation_dispositions"].append(
            {
                "limitation_id": "LIM-001",
                "disposition": "ACCEPTED",
                "reason": "Duplicate disposition must not be accepted.",
            }
        )
    elif case == "unknown_readiness_disposition":
        inputs["readiness"]["limitation_dispositions"][0]["limitation_id"] = (
            "LIM-999"
        )

    for definition, payload in (
        ("workflow", workflow),
        ("problem_frame", inputs["problem_frame"]),
        ("research_brief", inputs["prior_brief"]),
        ("evidence_package", package),
        ("readiness_pack", inputs["readiness"]),
    ):
        validate_definition(schema, definition, payload)

    stopped = invalid_supplemental_handoff(schema, inputs)
    assert stopped["research_state"] == workflow["research_state"]
    assert stopped["next_stage"] == "STOPPED"
    assert stopped["blocking_reason"] == {
        "code": "MISSING_OR_INVALID_ARTIFACT",
        "task_ids": [task["task_id"] for task in inputs["prior_brief"]["tasks"]],
    }


def test_supplemental_rejects_reordered_or_malformed_stable_task_ids() -> None:
    initial = brief([public_web_task("RES-001"), public_web_task("RES-002")])
    reordered = brief(list(reversed(copy.deepcopy(initial["tasks"]))), revision=2)
    with pytest.raises(ContractViolation, match="reordered"):
        validate_brief_semantics(reordered, "RESEARCH_CORE", prior_brief=initial)
    malformed = brief([public_web_task("WEB-001")])
    with pytest.raises(ContractViolation, match="RES-NNN"):
        validate_brief_semantics(malformed, "RESEARCH_CORE")


def test_understand_preview_and_publication_use_schema_allowed_fields(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    workflow, current_brief, draft = publication_bundle()
    validate_definition(schema, "workflow", workflow)
    validate_definition(schema, "evidence_draft", draft)
    assert "neutral_synthesis" not in draft
    report = render_understand_report(draft)
    assert "RES-001=WITH_RESULTS" in report

    waiting, rejected_package = publish_evidence(
        schema, workflow, current_brief, draft, accepted=False
    )
    assert waiting == workflow
    assert rejected_package is None
    assert "evidence_draft" in waiting["artifact_refs"]
    assert "evidence_package" not in waiting["artifact_refs"]

    accepted, package = publish_evidence(
        schema, workflow, current_brief, draft, accepted=True
    )
    assert package is not None
    assert package["neutral_synthesis"] == report
    assert accepted["research_state"] == "RESEARCH_COMPLETE"
    assert accepted["next_stage"] == "DONE"
    assert "evidence_draft" not in accepted["artifact_refs"]
    assert "evidence_package" in accepted["artifact_refs"]


@pytest.mark.parametrize(
    ("state", "code", "task_ids"),
    [
        ("RESEARCH_FAILED", "RESEARCH_EXHAUSTED", ["RES-001"]),
        ("RESEARCH_CANCELLED", "USER_CANCELLED", ["RES-001"]),
        ("RESEARCH_CANCELLED", "PUBLIC_WEB_REQUIRES_NEW_WORKFLOW", ["RES-001"]),
        ("RESEARCH_PARTIAL", "SUPPLEMENTAL_LIMIT_REACHED", ["RES-001"]),
        ("RESEARCH_IN_PROGRESS", "MISSING_OR_INVALID_ARTIFACT", []),
    ],
)
def test_every_stopped_transition_has_schema_valid_blocking_reason(
    project_root: Path, state: str, code: str, task_ids: list[str]
) -> None:
    schema = load_schema(project_root)
    workflow = base_workflow(
        backend="NONE" if code == "PUBLIC_WEB_REQUIRES_NEW_WORKFLOW" else "RESEARCH_CORE"
    )
    if code == "SUPPLEMENTAL_LIMIT_REACHED":
        workflow["research_state"] = "RESEARCH_PARTIAL"
        workflow["next_stage"] = "research-design-kickoff"
    stopped = stopped_workflow(
        workflow, research_state=state, code=code, task_ids=task_ids
    )
    validate_definition(schema, "workflow", stopped)
    assert stopped["blocking_reason"] == {"code": code, "task_ids": task_ids}


@pytest.mark.parametrize(
    ("source_state", "state", "code"),
    [
        ("RESEARCH_IN_PROGRESS", "RESEARCH_FAILED", "PUBLIC_WEB_REQUIRES_NEW_WORKFLOW"),
        ("RESEARCH_IN_PROGRESS", "RESEARCH_FAILED", "USER_CANCELLED"),
        ("RESEARCH_IN_PROGRESS", "RESEARCH_CANCELLED", "RESEARCH_EXHAUSTED"),
        ("RESEARCH_PARTIAL", "RESEARCH_CANCELLED", "SUPPLEMENTAL_LIMIT_REACHED"),
        ("RESEARCH_PARTIAL", "RESEARCH_IN_PROGRESS", "SUPPLEMENTAL_LIMIT_REACHED"),
        ("RESEARCH_IN_PROGRESS", "RESEARCH_PARTIAL", "SUPPLEMENTAL_LIMIT_REACHED"),
        ("RESEARCH_IN_PROGRESS", "RESEARCH_CANCELLED", "MISSING_OR_INVALID_ARTIFACT"),
    ],
)
def test_stopped_transition_rejects_semantically_wrong_state_reason_pair(
    source_state: str, state: str, code: str
) -> None:
    workflow = base_workflow()
    workflow["research_state"] = source_state
    with pytest.raises(ContractViolation, match="does not match research state"):
        stopped_workflow(
            workflow,
            research_state=state,
            code=code,
            task_ids=["RES-001"],
        )


def test_resume_dispatches_only_unfinished_tasks_and_never_repeats_receipted_calls() -> None:
    current_brief = brief(
        [
            public_web_task("RES-001"),
            public_web_task("RES-002"),
            public_web_task("RES-003"),
        ]
    )
    draft = {
        "completed_receipts": [
            receipt("RES-001", "NO_RESULTS"),
            receipt("RES-003", "FAILED", error_code="NETWORK_ERROR"),
        ],
        "unfinished_task_ids": ["RES-002"],
    }
    counts = {
        "RES-001": {"search": 2, "fetch": 0, "map": 0},
        "RES-002": {"search": 1, "fetch": 0, "map": 0},
        "RES-003": {"search": 1, "fetch": 0, "map": 0},
    }
    before = copy.deepcopy(counts)
    call_log = resume_unfinished_task_ids(
        current_brief, draft, counts, backend="RESEARCH_CORE"
    )
    assert call_log == ["RES-002"]
    assert counts == before


def test_core_execution_boundary_reads_status_before_counted_task_call(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    workflow = base_workflow()
    task = public_web_task(
        "RES-001", direction="auto", domains=["example.com"]
    )
    status = configuration_status(ConfigSnapshot(exa_api_key="exa-key"))
    result, call_log = core_execution_boundary(workflow, task, status)
    validate_definition(schema, "workflow", result)
    assert [entry[0] for entry in call_log] == [
        "web_research_status",
        "web_search",
    ]
    assert call_log[1][1] == ("search", "alternate", "exa")
    assert result["call_counts"]["RES-001"] == {
        "search": 1,
        "fetch": 0,
        "map": 0,
    }


def test_core_not_ready_blocks_through_existing_gate_without_count_or_host_use(
    project_root: Path,
) -> None:
    schema = load_schema(project_root)
    workflow = base_workflow()
    status = configuration_status(ConfigSnapshot())
    result, call_log = core_execution_boundary(
        workflow, public_web_task("RES-001"), status
    )
    validate_definition(schema, "workflow", result)
    assert [entry[0] for entry in call_log] == ["web_research_status"]
    assert result["selected_backend"] == "RESEARCH_CORE"
    assert result["call_counts"] == zero_counts(["RES-001"])
    assert result["research_state"] == "RESEARCH_BLOCKED"
    assert result["blocking_reason"] == {
        "code": "NO_AUTHORIZED_WEB_BACKEND",
        "task_ids": ["RES-001"],
    }


def test_research_skill_paths_and_agent_policies_are_installed(
    project_root: Path,
) -> None:
    expected = (
        "skills/research-design-kickoff/SKILL.md",
        "adapters/codex/skills/research-design-kickoff/agents/openai.yaml",
        "skills/research-execution/SKILL.md",
        "adapters/codex/skills/research-execution/agents/openai.yaml",
        "docs/skill-tests/research-design-kickoff-scenarios.md",
        "docs/skill-tests/research-execution-scenarios.md",
    )
    for relative in expected:
        assert (project_root / relative).is_file(), relative
    assert not (project_root / "skills/web-research-execution/SKILL.md").exists()
    assert not (
        project_root / "docs/skill-tests/web-research-execution-scenarios.md"
    ).exists()

    for relative, skill_name in (
        ("adapters/codex/skills/research-design-kickoff/agents/openai.yaml", "$research-design-kickoff"),
        ("adapters/codex/skills/research-execution/agents/openai.yaml", "$research-execution"),
    ):
        agent = yaml.safe_load((project_root / relative).read_text("utf-8"))
        assert agent["policy"] == {"allow_implicit_invocation": False}
        assert skill_name in agent["interface"]["default_prompt"]


def test_research_design_skill_declares_provider_neutral_brief_contract(
    project_root: Path,
) -> None:
    text = (project_root / "skills/research-design-kickoff/SKILL.md").read_text(
        "utf-8"
    )
    normalized = " ".join(text.split())
    for phrase in (
        "1–12",
        "PROVIDED_MATERIAL",
        "PUBLIC_WEB",
        "产品形态",
        "关键资源",
        "开源生态",
        "候选实现路径",
    ):
        assert phrase in text
    assert "no Provider name, route, recommendation or selection" in normalized
    for forbidden in (
        "READY_FOR_RESEARCH_DESIGN",
        "READY_FOR_RESEARCH_EXECUTION",
        "required_capabilities",
        "recommended_provider",
        "recommended_route",
    ):
        assert forbidden not in text


def test_shared_gate_and_research_design_bind_the_supplemental_request(
    project_root: Path,
) -> None:
    shared = (
        project_root
        / "skills/problem-navigator/references/evidence-package-validation.md"
    ).read_text("utf-8")
    design = (project_root / "skills/research-design-kickoff/SKILL.md").read_text(
        "utf-8"
    )
    for phrase in ("supplemental_request", "affected_candidate_ids"):
        assert phrase in shared
    for phrase in (
        "supplemental_request_id",
        "matching request ID",
        "Revision-1 tasks",
    ):
        assert phrase in design
    assert "material tasks cover carrier refs" in " ".join(shared.split())
    assert "collectively cover every carrier material_ref" in " ".join(design.split())
    assert "PUBLIC_FACT" in design and "semantic-relevance engine" in design


def test_design_skill_delegates_recovery_and_publication_to_shared_control(
    project_root: Path,
) -> None:
    design = (project_root / "skills/research-design-kickoff/SKILL.md").read_text(
        "utf-8"
    )
    control = (
        project_root / "skills/problem-navigator/references/workflow-control.md"
    ).read_text("utf-8")
    for phrase in (
        "Read ../problem-navigator/references/workflow-control.md",
        "Use shared append",
        "Artifact files first and workflow last",
        "For an erroneous old claim use reopen",
        "initialize the draft, invalidate downstream refs",
        "Later revisions are allowed; no revision-2 stop",
    ):
        assert phrase in design
    for phrase in (
        "writes artifacts first and workflow last",
        "Single-file atomicity is not a multi-file transaction",
        "crash between replacements is detected",
        "regenerate the earliest invalid producer",
        "Every task has one terminal receipt",
        "16 tasks",
    ):
        assert phrase in control
    assert "Readers must never see" not in design


def test_execution_skill_declares_reviewed_boundary_contract(
    project_root: Path,
) -> None:
    execution = (project_root / "skills/research-execution/SKILL.md").read_text(
        "utf-8"
    )
    normalized = " ".join(execution.split())
    for phrase in (
        "ephemeral report",
        "status is not a per-task call",
        "ordinary resume execute only unfinished_task_ids",
        "Every host receipt records fallback_authorization: USER_APPROVED",
        "no per-task caps",
        "Failed, interrupted and host calls count",
        "At total limit retain partial evidence",
    ):
        assert phrase in normalized


def test_research_scenarios_record_red_green_observable_cases(
    project_root: Path,
) -> None:
    kickoff = (
        project_root / "docs/skill-tests/research-design-kickoff-scenarios.md"
    ).read_text("utf-8")
    execution = (
        project_root / "docs/skill-tests/research-execution-scenarios.md"
    ).read_text("utf-8")
    combined = kickoff + execution
    for text in (kickoff, execution):
        assert "RED" in text and "GREEN" in text
    for phrase in (
        "NONE",
        "RESEARCH_CORE",
        "entry authorization",
        "task-scoped authorization",
        "recovery",
        "NO_RESULTS",
        "RESEARCH_PARTIAL",
        "prompt injection",
        "PRODUCT_SOFTWARE",
        "product form",
        "critical resource",
        "open-source ecosystem",
        "implementation path",
    ):
        assert phrase in combined


def test_research_skills_are_concise_document_contracts(project_root: Path) -> None:
    for relative in (
        "skills/research-design-kickoff/SKILL.md",
        "skills/research-execution/SKILL.md",
    ):
        text = (project_root / relative).read_text("utf-8")
        lowered = text.lower()
        assert "validator cli" not in lowered
        assert "workflow engine" not in lowered
        assert "implementation plan" not in lowered
        assert len(text.splitlines()) <= 260
