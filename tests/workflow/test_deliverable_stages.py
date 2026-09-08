from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError


WORKFLOW_ID = "550e8400-e29b-41d4-a716-446655440000"
PRD_PATH = "docs/01-prd.md"
TECH_PATH = "docs/02-technical-solution-spec.md"
PACKAGE_PATH = "specs/package.yaml"


def _schema(root: Path) -> dict[str, object]:
    return json.loads(
        (
            root / "skills/problem-navigator/references/artifacts.schema.json"
        ).read_text("utf-8")
    )


def _validate(schema: dict[str, object], definition: str, payload: dict[str, object]) -> None:
    Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"}
    ).validate(payload)


def product_graph(endpoint: str = "FINAL_SPEC_PACKAGE") -> dict[str, object]:
    members = ["01-prd.md"] if endpoint == "PRD_ONLY" else ["01-prd.md", "02-technical-solution-spec.md"]
    document = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "document_id": "DOC-001",
        "document_version": 2,
        "refined_solution_id": "SOL-001",
        "refined_solution_version": 1,
        "content_profile": "PRODUCT_SOFTWARE",
        "members": members,
        "acceptance_status": "ACCEPTED",
    }
    graph: dict[str, object] = {
        "frame": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "problem_frame_id": "PF-001",
            "problem_frame_version": 1,
            "analysis_goal": "DECIDE",
            "content_profile": "PRODUCT_SOFTWARE",
            "clarified_problem": "Define a bounded product.",
            "goal": "Create accepted specifications.",
            "scope": ["Product contract"],
            "non_goals": ["Implementation"],
            "constraints": [],
            "assumptions": [],
            "delivery_endpoint": endpoint,
            "user_confirmation_status": "ACCEPTED",
        },
        "workflow": {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "analysis_goal": "DECIDE",
            "next_stage": "DONE",
            "selected_backend": "NONE",
            "native_fallback_approved": False,
            "research_state": "RESEARCH_COMPLETE",
            "call_counts": {},
            "artifact_refs": {
                "problem_frame": "artifacts/problem-frame.yaml",
                "solution_document": "artifacts/solution-document.yaml",
                **({} if endpoint == "PRD_ONLY" else {"solution_spec_package": PACKAGE_PATH}),
            },
        },
        "document": document,
        "document_ref": "artifacts/solution-document.yaml",
        "prd": {
            "prd_document_id": "DOC-001",
            "prd_document_version": 2,
            "requirement_ids": ["REQ-001", "REQ-002"],
            "acceptance_ids": ["ACC-001", "ACC-002"],
            "acceptance_requirement_links": {"ACC-001": "REQ-001", "ACC-002": "REQ-002"},
        },
    }
    if endpoint != "PRD_ONLY":
        graph.update(
            {
                "technical": {
                    "prd_document_id": "DOC-001",
                    "prd_document_version": 2,
                    "requirement_refs": ["REQ-001", "REQ-002"],
                    "acceptance_refs": ["ACC-001", "ACC-002"],
                    "design_ids": ["DES-001", "DES-002"],
                    "design_links": {"DES-001": ["REQ-001", "ACC-001"], "DES-002": ["REQ-002", "ACC-002"]},
                },
                "package": {
                    "schema_version": 1,
                    "workflow_id": WORKFLOW_ID,
                    "package_id": "PKG-001",
                    "package_version": 1,
                    "document_id": "DOC-001",
                    "document_version": 2,
                    "content_profile": "PRODUCT_SOFTWARE",
                    "units": ["specs/unit-a.md", "specs/unit-b.md"],
                    "acceptance_status": "ACCEPTED",
                },
                "trace": [
                    {"requirement_id": "REQ-001", "acceptance_id": "ACC-001", "design_id": "DES-001", "unit_id": "UNIT-A"},
                    {"requirement_id": "REQ-002", "acceptance_id": "ACC-002", "design_id": "DES-002", "unit_id": "UNIT-B"},
                ],
                "unit_records": [
                    {"unit_id": "UNIT-A", "path": "specs/unit-a.md", "content_id": "CONTENT-A"},
                    {"unit_id": "UNIT-B", "path": "specs/unit-b.md", "content_id": "CONTENT-B"},
                ],
                "package_ref": PACKAGE_PATH,
            }
        )
    return graph


def validate_product_graph(schema: dict[str, object], graph: dict[str, object]) -> None:
    frame = graph["frame"]
    workflow = graph["workflow"]
    document = graph["document"]
    prd = graph["prd"]
    assert isinstance(frame, dict) and isinstance(workflow, dict) and isinstance(document, dict) and isinstance(prd, dict)
    _validate(schema, "problem_frame", frame)
    _validate(schema, "workflow", workflow)
    _validate(schema, "solution_document", document)
    assert frame["content_profile"] == document["content_profile"] == "PRODUCT_SOFTWARE"
    assert prd["prd_document_id"] == document["document_id"]
    assert prd["prd_document_version"] == document["document_version"]
    assert workflow["artifact_refs"]["solution_document"] == graph["document_ref"]
    if frame["delivery_endpoint"] == "PRD_ONLY":
        assert document["members"] == ["01-prd.md"]
        assert workflow["next_stage"] == "DONE"
        assert "technical" not in graph and "package" not in graph and "trace" not in graph
        return
    assert document["members"] == ["01-prd.md", "02-technical-solution-spec.md"]
    technical = graph["technical"]
    package = graph["package"]
    trace = graph["trace"]
    units = graph["unit_records"]
    assert isinstance(technical, dict) and isinstance(package, dict) and isinstance(trace, list) and isinstance(units, list)
    _validate(schema, "solution_spec_package", package)
    assert technical["prd_document_id"] == document["document_id"]
    assert technical["prd_document_version"] == document["document_version"]
    assert package["document_id"] == document["document_id"]
    assert package["document_version"] == document["document_version"]
    assert workflow["next_stage"] == "DONE"
    assert workflow["artifact_refs"]["solution_spec_package"] == graph["package_ref"]
    sets = {
        "requirements": set(prd["requirement_ids"]),
        "acceptances": set(prd["acceptance_ids"]),
        "designs": set(technical["design_ids"]),
        "units": {unit["unit_id"] for unit in units},
    }
    assert all(len(values) == len(graph_values) for values, graph_values in (
        (sets["requirements"], prd["requirement_ids"]),
        (sets["acceptances"], prd["acceptance_ids"]),
        (sets["designs"], technical["design_ids"]),
        (sets["units"], [unit["unit_id"] for unit in units]),
    ))
    unit_paths = [unit["path"] for unit in units]
    content_ids = [unit["content_id"] for unit in units]
    assert len(unit_paths) == len(set(unit_paths))
    assert len(content_ids) == len(set(content_ids))
    assert set(unit_paths) == set(package["units"])
    assert set(technical["requirement_refs"]) == sets["requirements"]
    assert set(technical["acceptance_refs"]) == sets["acceptances"]
    assert {row["requirement_id"] for row in trace} == sets["requirements"]
    assert {row["acceptance_id"] for row in trace} == sets["acceptances"]
    assert {row["design_id"] for row in trace} == sets["designs"]
    assert {row["unit_id"] for row in trace} == sets["units"]
    for row in trace:
        assert row["acceptance_id"] in sets["acceptances"]
        assert prd["acceptance_requirement_links"][row["acceptance_id"]] == row["requirement_id"]
        assert row["design_id"] in sets["designs"]
        assert row["requirement_id"] in technical["design_links"][row["design_id"]]
        assert row["acceptance_id"] in technical["design_links"][row["design_id"]]


def test_prd_only_envelope_is_legal_only_for_accepted_prd_only_frame(project_root: Path) -> None:
    schema = _schema(project_root)
    graph = product_graph("PRD_ONLY")
    validate_product_graph(schema, graph)
    for mutation in (
        lambda g: g["frame"].update(delivery_endpoint="FINAL_SPEC_PACKAGE"),
        lambda g: g["workflow"].update(next_stage="solution-decomposition"),
        lambda g: g["document"].update(members=["01-prd.md", "02-technical-solution-spec.md"]),
    ):
        invalid = copy.deepcopy(graph)
        mutation(invalid)
        with pytest.raises((AssertionError, ValidationError)):
            validate_product_graph(schema, invalid)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda g: g["technical"].update(prd_document_id="DOC-FOREIGN"),
        lambda g: g["technical"].update(prd_document_version=1),
        lambda g: g["package"].update(document_id="DOC-STALE"),
        lambda g: g["package"].update(document_version=1),
        lambda g: g["prd"].update(requirement_ids=["REQ-001"]),
        lambda g: g["prd"].update(acceptance_ids=["ACC-001"]),
        lambda g: g["technical"].update(design_ids=["DES-001"]),
        lambda g: g.update(unit_records=g["unit_records"][:1]),
        lambda g: g["prd"].update(requirement_ids=["REQ-001", "REQ-001"]),
        lambda g: g["prd"].update(acceptance_ids=["ACC-001", "ACC-001"]),
        lambda g: g["technical"].update(design_ids=["DES-001", "DES-001"]),
        lambda g: g["unit_records"][1].update(unit_id="UNIT-A"),
        lambda g: g["unit_records"][1].update(path="specs/unit-a.md"),
        lambda g: g["unit_records"][1].update(content_id="CONTENT-A"),
        lambda g: g["package"].update(units=["specs/unit-a.md"]),
        lambda g: g["package"].update(units=["specs/unit-a.md", "specs/foreign.md"]),
        lambda g: g["package"].update(units=["specs/unit-a.md", "specs/unit-a.md"]),
        lambda g: g["document"].update(document_version=3),
        lambda g: g["trace"][0].update(requirement_id="REQ-FOREIGN"),
        lambda g: g["trace"][0].update(acceptance_id="ACC-FOREIGN"),
        lambda g: g["trace"][0].update(design_id="DES-FOREIGN"),
        lambda g: g["trace"][0].update(unit_id="UNIT-FOREIGN"),
        lambda g: g.update(trace=g["trace"][:1]),
        lambda g: g["workflow"]["artifact_refs"].update(solution_document="artifacts/stale-document.yaml"),
        lambda g: g["workflow"]["artifact_refs"].update(solution_spec_package="specs/stale-package.yaml"),
    ],
)
def test_cross_artifact_graph_rejects_stale_foreign_duplicate_or_open_links(project_root: Path, mutation) -> None:
    graph = product_graph()
    mutation(graph)
    with pytest.raises((AssertionError, ValidationError, KeyError)):
        validate_product_graph(_schema(project_root), graph)


def _complete_preview(graph: dict[str, object]) -> dict[str, object]:
    package = graph["package"]
    document = graph["document"]
    return {
        "document_id": document["document_id"],
        "document_version": document["document_version"],
        "package_id": package["package_id"],
        "package_version": package["package_version"],
        "map": [{"unit_id": unit["unit_id"], "path": unit["path"]} for unit in graph["unit_records"]],
        "trace": copy.deepcopy(graph["trace"]),
        "shared_constraints": [{"constraint_id": "CON-001", "content_id": "CON-CONTENT-001"}],
        "unit_records": copy.deepcopy(graph["unit_records"]),
    }


def _validate_preview(schema: dict[str, object], preview: dict[str, object], document: dict[str, object], current_package: dict[str, object]) -> None:
    required = {"document_id", "document_version", "package_id", "package_version", "map", "trace", "shared_constraints", "unit_records"}
    assert set(preview) == required
    _validate(schema, "solution_document", document)
    _validate(schema, "solution_spec_package", current_package)
    assert (preview["document_id"], preview["document_version"]) == (document["document_id"], document["document_version"])
    assert (preview["package_id"], preview["package_version"]) == (current_package["package_id"], current_package["package_version"])
    assert (current_package["document_id"], current_package["document_version"], current_package["content_profile"]) == (document["document_id"], document["document_version"], document["content_profile"])
    units = preview["unit_records"]
    assert units and preview["map"] == [{"unit_id": unit["unit_id"], "path": unit["path"]} for unit in units]
    assert preview["trace"]
    assert preview["shared_constraints"]
    assert all(unit["content_id"] for unit in units)
    assert len({unit["path"] for unit in units}) == len(units)
    assert len({unit["unit_id"] for unit in units}) == len(units)
    assert {unit["path"] for unit in units} == set(current_package["units"])
    assert {row["unit_id"] for row in preview["trace"]} == {unit["unit_id"] for unit in units}
    constraints = preview["shared_constraints"]
    assert len({item["constraint_id"] for item in constraints}) == len(constraints)
    assert all(item["content_id"] for item in constraints)


def _accept_preview(schema: dict[str, object], workflow: dict[str, object], accepted_artifacts: dict[str, object], document: dict[str, object], current_package: dict[str, object], preview: dict[str, object], response: object):
    if response is not True:
        return workflow, accepted_artifacts
    _validate_preview(schema, preview, document, current_package)
    package = {
        "schema_version": 1,
        "workflow_id": document["workflow_id"],
        "package_id": preview["package_id"],
        "package_version": preview["package_version"],
        "document_id": preview["document_id"],
        "document_version": preview["document_version"],
        "content_profile": document["content_profile"],
        "units": [unit["path"] for unit in preview["unit_records"]],
        "acceptance_status": "ACCEPTED",
    }
    updated_artifacts = {**accepted_artifacts, "solution_spec_package": package, "published_preview": copy.deepcopy(preview)}
    updated_workflow = copy.deepcopy(workflow)
    updated_workflow["artifact_refs"]["solution_spec_package"] = PACKAGE_PATH
    updated_workflow["next_stage"] = "DONE"
    return updated_workflow, updated_artifacts


@pytest.mark.parametrize("response", [False, None, "ambiguous", "correction"])
def test_stage8_rejection_or_silence_preserves_workflow_and_artifacts_byte_for_byte(project_root: Path, response) -> None:
    graph = product_graph()
    workflow = graph["workflow"]
    workflow["next_stage"] = "solution-decomposition"
    workflow["artifact_refs"].pop("solution_spec_package")
    artifacts = {"previous_package": {"package_id": "PKG-OLD", "package_version": 1}}
    preview = _complete_preview(graph)
    before_bytes = json.dumps([workflow, artifacts], sort_keys=True).encode()
    after_workflow, after_artifacts = _accept_preview(_schema(project_root), workflow, artifacts, graph["document"], graph["package"], preview, response)
    assert json.dumps([after_workflow, after_artifacts], sort_keys=True).encode() == before_bytes


def test_stage8_explicit_acceptance_publishes_current_package_and_done(project_root: Path) -> None:
    graph = product_graph()
    graph["workflow"]["next_stage"] = "solution-decomposition"
    graph["workflow"]["artifact_refs"].pop("solution_spec_package")
    preview = _complete_preview(graph)
    workflow, artifacts = _accept_preview(_schema(project_root), graph["workflow"], {}, graph["document"], graph["package"], preview, True)
    _validate(_schema(project_root), "solution_spec_package", artifacts["solution_spec_package"])
    assert workflow["artifact_refs"]["solution_spec_package"] == PACKAGE_PATH
    assert workflow["next_stage"] == "DONE"
    assert artifacts["published_preview"] == preview


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.pop("trace"),
        lambda p: p.update(document_version=1),
        lambda p: p.update(package_version=99),
        lambda p: p.update(map=p["map"][:1]),
        lambda p: p.update(shared_constraints=[]),
        lambda p: p["trace"][0].update(unit_id="UNIT-FOREIGN"),
        lambda p: p["shared_constraints"][0].update(content_id=""),
        lambda p: p["unit_records"][0].update(path="specs/foreign.md"),
        lambda p: p["unit_records"][0].update(content_id=""),
    ],
)
def test_stage8_incomplete_stale_or_mismatched_preview_cannot_publish(project_root: Path, mutation) -> None:
    graph = product_graph()
    workflow = graph["workflow"]
    workflow["next_stage"] = "solution-decomposition"
    workflow["artifact_refs"].pop("solution_spec_package")
    preview = _complete_preview(graph)
    mutation(preview)
    before = json.dumps([workflow, {}], sort_keys=True).encode()
    with pytest.raises((AssertionError, KeyError)):
        _accept_preview(_schema(project_root), workflow, {}, graph["document"], graph["package"], preview, True)
    assert json.dumps([workflow, {}], sort_keys=True).encode() == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda preview, package: (preview["unit_records"][0].update(path="specs/foreign.md"), preview["map"][0].update(path="specs/foreign.md")),
        lambda preview, package: package.update(document_version=1),
        lambda preview, package: package.update(units=["specs/unit-a.md", "specs/foreign.md"]),
    ],
)
def test_stage8_rejects_coordinated_preview_or_stale_current_package_before_publication(project_root: Path, mutation) -> None:
    graph = product_graph()
    workflow = graph["workflow"]
    workflow["next_stage"] = "solution-decomposition"
    workflow["artifact_refs"].pop("solution_spec_package")
    preview = _complete_preview(graph)
    current_package = copy.deepcopy(graph["package"])
    mutation(preview, current_package)
    before = json.dumps([workflow, {}], sort_keys=True).encode()
    with pytest.raises(AssertionError):
        _accept_preview(_schema(project_root), workflow, {}, graph["document"], current_package, preview, True)
    assert json.dumps([workflow, {}], sort_keys=True).encode() == before


def test_skills_require_current_prd_tuple_and_explicit_package_acceptance(project_root: Path) -> None:
    documentation = (project_root / "skills/solution-documentation/SKILL.md").read_text("utf-8")
    decomposition = (project_root / "skills/solution-decomposition/SKILL.md").read_text("utf-8")
    assert "prd_document_id" in documentation and "prd_document_version" in documentation
    assert "pre-acceptance" in decomposition.lower()
    assert "silence" in decomposition.lower() and "byte-for-byte unchanged" in decomposition.lower()


def test_delivery_2_1_declares_endpoint_trims_universal_preview_and_legal_returns(
    project_root: Path,
) -> None:
    refinement = (project_root / "skills/solution-refinement/SKILL.md").read_text(
        "utf-8"
    )
    documentation = (
        project_root / "skills/solution-documentation/SKILL.md"
    ).read_text("utf-8")
    control = (
        project_root / "skills/problem-navigator/references/workflow-control.md"
    ).read_text("utf-8")
    normalized_refinement = " ".join(refinement.split())
    normalized_docs = " ".join(documentation.split())

    assert "user_confirmation_status: DRAFT" in normalized_refinement
    assert "PRD_ONLY" in refinement and "do not require a complete How" in normalized_refinement
    assert "TECHNICAL_SPEC_ONLY" in refinement and "do not invent a PRD baseline" in normalized_refinement
    assert "unaccepted preview for every endpoint" in normalized_docs
    assert "These 14 chapters are the default full-product template" in normalized_docs
    assert "omit inapplicable chapters with a concise applicability note" in normalized_docs
    assert "members: [01-technical-solution-spec.md]" in normalized_docs
    assert "PRD_ONLY and TECHNICAL_SPEC_ONLY go directly to DONE" in normalized_docs

    for target in (
        "decision-readiness-interview",
        "adversarial-option-selection",
        "solution-refinement",
        "solution-documentation",
    ):
        assert f"resume --target {target}" in control
    assert "Incorrect fact | reopen affected tasks" in control
    assert "New bounded evidence question | append" in control
