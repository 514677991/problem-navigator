from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from test_artifact_contracts import minimal_payloads
from test_decision_stages import decision_evidence
from test_deliverable_stages import product_graph, validate_product_graph


PATHS = {
    "problem_frame": "artifacts/problem-frame.yaml",
    "research_brief": "artifacts/research-brief.yaml",
    "evidence_package": "artifacts/evidence-package.yaml",
    "readiness_pack": "artifacts/readiness-pack.yaml",
    "decision": "artifacts/decision.yaml",
    "refined_solution": "artifacts/refined-solution.yaml",
    "solution_document": "artifacts/solution-document.yaml",
    "solution_spec_package": "artifacts/solution-spec-package.yaml",
}
DEFINITIONS = {name: name for name in PATHS}


def _schema(root: Path) -> dict[str, object]:
    return json.loads(
        (
            root / "skills/problem-navigator/references/artifacts.schema.json"
        ).read_text("utf-8")
    )


def _validate(schema: dict[str, object], name: str, payload: dict[str, object]) -> None:
    Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{name}"}
    ).validate(payload)


def _validate_chain(schema: dict[str, object], chain: dict[str, object]) -> None:
    workflow = chain["workflow"]
    artifacts = chain["artifacts"]
    transitions = chain["transitions"]
    report = chain["report_contract"]
    _validate(schema, "workflow", workflow)
    assert set(workflow["artifact_refs"].values()) == set(artifacts)
    assert len(workflow["artifact_refs"]) == len(artifacts)
    for artifact_name, path in workflow["artifact_refs"].items():
        assert path in artifacts
        _validate(schema, DEFINITIONS[artifact_name], artifacts[path])
        assert artifacts[path]["workflow_id"] == workflow["workflow_id"]
    frame = artifacts[PATHS["problem_frame"]]
    brief = artifacts[PATHS["research_brief"]]
    evidence = artifacts[PATHS["evidence_package"]]
    assert frame["analysis_goal"] == brief["analysis_goal"] == evidence["analysis_goal"] == workflow["analysis_goal"]
    assert frame["content_profile"] == chain["content_profile"]
    assert evidence["brief_revision"] == brief["revision"]
    assert report["workflow_id"] == workflow["workflow_id"]
    assert report["content_profile"] == frame["content_profile"]
    assert report["analysis_goal"] == frame["analysis_goal"] == workflow["analysis_goal"]
    assert report["evidence_revision"] == evidence["evidence_revision"]
    assert report["views"] and set(report["views"]).isdisjoint(report["omitted_views"])
    product_views = {"product-form", "key-resources", "open-source-ecosystem", "feasibility"}
    if frame["content_profile"] == "GENERAL":
        assert "product-form" not in report["views"]
    else:
        assert product_views <= set(report["views"]) | set(report["omitted_views"])
    assert transitions[-1]["next_stage"] == workflow["next_stage"] == "DONE"
    assert transitions[-1]["artifact_refs"] == workflow["artifact_refs"]
    expected_stages = (
        ("problem-framing", "research-design-kickoff", "research-execution", "DONE")
        if workflow["analysis_goal"] == "UNDERSTAND"
        else ("problem-framing", "research-design-kickoff", "research-execution", "decision-readiness-interview", "adversarial-option-selection", "solution-refinement", "solution-documentation", "solution-decomposition", "DONE")
    )
    assert tuple(snapshot["next_stage"] for snapshot in transitions) == expected_stages
    expected_ref_names = (
        [(), ("problem_frame",), ("problem_frame", "research_brief"), ("problem_frame", "research_brief", "evidence_package")]
        if workflow["analysis_goal"] == "UNDERSTAND"
        else [
            (),
            ("problem_frame",),
            ("problem_frame", "research_brief"),
            ("problem_frame", "research_brief", "evidence_package"),
            ("problem_frame", "research_brief", "evidence_package", "readiness_pack"),
            ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision"),
            ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision", "refined_solution"),
            ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision", "refined_solution", "solution_document"),
            tuple(PATHS),
        ]
    )
    assert [set(snapshot["artifact_refs"]) for snapshot in transitions] == [set(names) for names in expected_ref_names]
    for earlier, later in zip(transitions, transitions[1:]):
        assert set(earlier["artifact_refs"]).issubset(later["artifact_refs"])
    for snapshot in transitions:
        assert set(snapshot["artifact_refs"].values()) <= set(artifacts)
    if workflow["analysis_goal"] == "UNDERSTAND":
        assert set(workflow["artifact_refs"]) == {"problem_frame", "research_brief", "evidence_package"}
        assert len(transitions) == 4
        return
    readiness = artifacts[PATHS["readiness_pack"]]
    decision = artifacts[PATHS["decision"]]
    refined = artifacts[PATHS["refined_solution"]]
    document = artifacts[PATHS["solution_document"]]
    package = artifacts[PATHS["solution_spec_package"]]
    assert readiness["brief_revision"] == brief["revision"]
    assert readiness["evidence_revision"] == evidence["evidence_revision"]
    assert (decision["readiness_pack_id"], decision["readiness_pack_version"]) == (readiness["readiness_pack_id"], readiness["readiness_pack_version"])
    assert decision["evidence_revision"] == evidence["evidence_revision"]
    assert set(decision["selected_candidate_ids"]) <= {candidate["candidate_id"] for candidate in evidence["candidates"]}
    assert (refined["decision_id"], refined["decision_version"]) == (decision["decision_id"], decision["decision_version"])
    assert (document["refined_solution_id"], document["refined_solution_version"]) == (refined["refined_solution_id"], refined["refined_solution_version"])
    assert (package["document_id"], package["document_version"]) == (document["document_id"], document["document_version"])
    assert document["content_profile"] == package["content_profile"] == frame["content_profile"]
    assert len(transitions) == 9


def _base_artifacts(profile: str, goal: str) -> dict[str, tuple[str, dict[str, object]]]:
    base = minimal_payloads()
    frame = {**base["problem_frame"], "analysis_goal": goal, "content_profile": profile, "delivery_endpoint": "RESEARCH_REPORT" if goal == "UNDERSTAND" else "FINAL_SPEC_PACKAGE"}
    brief = {**base["research_brief"], "analysis_goal": goal}
    evidence = {**base["evidence_package"], "analysis_goal": goal}
    if goal == "DECIDE":
        evidence = decision_evidence(["CAND-001"])
    return {
        PATHS["problem_frame"]: ("problem_frame", frame),
        PATHS["research_brief"]: ("research_brief", brief),
        PATHS["evidence_package"]: ("evidence_package", evidence),
    }


def _registry(records: dict[str, tuple[str, dict[str, object]]]) -> dict[str, dict[str, object]]:
    return {path: payload for path, (_, payload) in records.items()}


def test_general_understand_complete_chain_and_illegal_product_view(project_root: Path) -> None:
    records = _base_artifacts("GENERAL", "UNDERSTAND")
    refs = {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package")}
    chain = {
        "content_profile": "GENERAL",
        "workflow": {**minimal_payloads()["workflow"], "analysis_goal": "UNDERSTAND", "research_state": "RESEARCH_COMPLETE", "next_stage": "DONE", "artifact_refs": refs},
        "artifacts": _registry(records),
        "report_contract": {"workflow_id": minimal_payloads()["workflow"]["workflow_id"], "analysis_goal": "UNDERSTAND", "content_profile": "GENERAL", "evidence_revision": 1, "views": ["dynamic-problem-theme"], "omitted_views": ["product-form", "open-source-ecosystem"]},
        "transitions": [
            {"next_stage": "problem-framing", "artifact_refs": {}},
            {"next_stage": "research-design-kickoff", "artifact_refs": {"problem_frame": PATHS["problem_frame"]}},
            {"next_stage": "research-execution", "artifact_refs": {"problem_frame": PATHS["problem_frame"], "research_brief": PATHS["research_brief"]}},
            {"next_stage": "DONE", "artifact_refs": refs},
        ],
    }
    _validate_chain(_schema(project_root), chain)
    invalid = copy.deepcopy(chain)
    invalid["report_contract"]["views"] = ["product-form"]
    invalid["report_contract"]["omitted_views"] = ["product-form"]
    with pytest.raises(AssertionError):
        _validate_chain(_schema(project_root), invalid)


def test_product_understand_complete_chain_and_illegal_decision_transition(project_root: Path) -> None:
    records = _base_artifacts("PRODUCT_SOFTWARE", "UNDERSTAND")
    refs = {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package")}
    chain = {
        "content_profile": "PRODUCT_SOFTWARE",
        "workflow": {**minimal_payloads()["workflow"], "analysis_goal": "UNDERSTAND", "research_state": "RESEARCH_COMPLETE", "next_stage": "DONE", "artifact_refs": refs},
        "artifacts": _registry(records),
        "report_contract": {"workflow_id": minimal_payloads()["workflow"]["workflow_id"], "analysis_goal": "UNDERSTAND", "content_profile": "PRODUCT_SOFTWARE", "evidence_revision": 1, "views": ["product-form", "key-resources", "open-source-ecosystem", "feasibility"], "omitted_views": []},
        "transitions": [
            {"next_stage": "problem-framing", "artifact_refs": {}},
            {"next_stage": "research-design-kickoff", "artifact_refs": {"problem_frame": PATHS["problem_frame"]}},
            {"next_stage": "research-execution", "artifact_refs": {"problem_frame": PATHS["problem_frame"], "research_brief": PATHS["research_brief"]}},
            {"next_stage": "DONE", "artifact_refs": refs},
        ],
    }
    _validate_chain(_schema(project_root), chain)
    invalid = copy.deepcopy(chain)
    invalid["transitions"][-1]["next_stage"] = "decision-readiness-interview"
    with pytest.raises(AssertionError):
        _validate_chain(_schema(project_root), invalid)


def _decide_artifacts(profile: str) -> dict[str, dict[str, object]]:
    base = minimal_payloads()
    records = _base_artifacts(profile, "DECIDE")
    document = {**base["solution_document"], "content_profile": profile, "members": ["formal-solution-report.md"] if profile == "GENERAL" else ["01-prd.md", "02-technical-solution-spec.md"], "document_version": 2}
    package = {**base["solution_spec_package"], "content_profile": profile, "document_version": 2, "units": ["specs/only-unit.md"] if profile == "GENERAL" else ["specs/unit-a.md", "specs/unit-b.md"]}
    for name, payload in (
        ("readiness_pack", base["readiness_pack"]),
        ("decision", base["decision"]),
        ("refined_solution", base["refined_solution"]),
        ("solution_document", document),
        ("solution_spec_package", package),
    ):
        records[PATHS[name]] = (name, payload)
    return _registry(records)


def test_general_decide_complete_lineage_and_one_unit_with_stale_refinement_mutation(project_root: Path) -> None:
    artifacts = _decide_artifacts("GENERAL")
    refs = {name: PATHS[name] for name in PATHS}
    base_workflow = minimal_payloads()["workflow"]
    chain = {
        "content_profile": "GENERAL",
        "workflow": {**base_workflow, "analysis_goal": "DECIDE", "research_state": "RESEARCH_COMPLETE", "next_stage": "DONE", "artifact_refs": refs},
        "artifacts": artifacts,
        "report_contract": {"workflow_id": base_workflow["workflow_id"], "analysis_goal": "DECIDE", "content_profile": "GENERAL", "evidence_revision": 1, "views": ["dynamic-problem-theme"], "omitted_views": ["product-form", "open-source-ecosystem"]},
        "transitions": [
            {"next_stage": "problem-framing", "artifact_refs": {}},
            {"next_stage": "research-design-kickoff", "artifact_refs": {"problem_frame": PATHS["problem_frame"]}},
            {"next_stage": "research-execution", "artifact_refs": {"problem_frame": PATHS["problem_frame"], "research_brief": PATHS["research_brief"]}},
            {"next_stage": "decision-readiness-interview", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package")}},
            {"next_stage": "adversarial-option-selection", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack")}},
            {"next_stage": "solution-refinement", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision")}},
            {"next_stage": "solution-documentation", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision", "refined_solution")}},
            {"next_stage": "solution-decomposition", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision", "refined_solution", "solution_document")}},
            {"next_stage": "DONE", "artifact_refs": refs},
        ],
    }
    _validate_chain(_schema(project_root), chain)
    assert chain["artifacts"][PATHS["solution_spec_package"]]["units"] == ["specs/only-unit.md"]
    invalid = copy.deepcopy(chain)
    invalid["artifacts"][PATHS["solution_document"]]["refined_solution_version"] = 99
    with pytest.raises(AssertionError):
        _validate_chain(_schema(project_root), invalid)


def test_product_decide_complete_lineage_trace_and_foreign_unit_mutation(project_root: Path) -> None:
    artifacts = _decide_artifacts("PRODUCT_SOFTWARE")
    refs = {name: PATHS[name] for name in PATHS}
    base_workflow = minimal_payloads()["workflow"]
    chain = {
        "content_profile": "PRODUCT_SOFTWARE",
        "workflow": {**base_workflow, "analysis_goal": "DECIDE", "research_state": "RESEARCH_COMPLETE", "next_stage": "DONE", "artifact_refs": refs},
        "artifacts": artifacts,
        "report_contract": {"workflow_id": base_workflow["workflow_id"], "analysis_goal": "DECIDE", "content_profile": "PRODUCT_SOFTWARE", "evidence_revision": 1, "views": ["product-form", "key-resources", "open-source-ecosystem", "feasibility"], "omitted_views": []},
        "transitions": [
            {"next_stage": "problem-framing", "artifact_refs": {}},
            {"next_stage": "research-design-kickoff", "artifact_refs": {"problem_frame": PATHS["problem_frame"]}},
            {"next_stage": "research-execution", "artifact_refs": {"problem_frame": PATHS["problem_frame"], "research_brief": PATHS["research_brief"]}},
            {"next_stage": "decision-readiness-interview", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package")}},
            {"next_stage": "adversarial-option-selection", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack")}},
            {"next_stage": "solution-refinement", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision")}},
            {"next_stage": "solution-documentation", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision", "refined_solution")}},
            {"next_stage": "solution-decomposition", "artifact_refs": {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package", "readiness_pack", "decision", "refined_solution", "solution_document")}},
            {"next_stage": "DONE", "artifact_refs": refs},
        ],
    }
    graph = product_graph()
    chain.update({key: graph[key] for key in ("frame", "document", "prd", "technical", "package", "trace", "unit_records")})
    graph_artifacts = chain["artifacts"]
    graph_artifacts[PATHS["problem_frame"]] = graph["frame"]
    graph_artifacts[PATHS["solution_document"]] = graph["document"]
    graph_artifacts[PATHS["solution_spec_package"]] = graph["package"]
    graph["workflow"] = chain["workflow"]
    graph["document_ref"] = PATHS["solution_document"]
    graph["package_ref"] = PATHS["solution_spec_package"]
    _validate_chain(_schema(project_root), chain)
    validate_product_graph(_schema(project_root), graph)
    invalid = copy.deepcopy(graph)
    invalid["package"]["units"][0] = "specs/foreign.md"
    with pytest.raises(AssertionError):
        validate_product_graph(_schema(project_root), invalid)


def test_general_understand_rejects_coordinated_product_view_and_wrong_goal(project_root: Path) -> None:
    records = _base_artifacts("GENERAL", "UNDERSTAND")
    refs = {name: PATHS[name] for name in ("problem_frame", "research_brief", "evidence_package")}
    chain = {
        "content_profile": "GENERAL",
        "workflow": {**minimal_payloads()["workflow"], "analysis_goal": "UNDERSTAND", "research_state": "RESEARCH_COMPLETE", "next_stage": "DONE", "artifact_refs": refs},
        "artifacts": _registry(records),
        "report_contract": {"workflow_id": minimal_payloads()["workflow"]["workflow_id"], "analysis_goal": "DECIDE", "content_profile": "GENERAL", "evidence_revision": 1, "views": ["product-form"], "omitted_views": []},
        "transitions": [
            {"next_stage": "problem-framing", "artifact_refs": {}},
            {"next_stage": "research-design-kickoff", "artifact_refs": {"problem_frame": PATHS["problem_frame"]}},
            {"next_stage": "research-execution", "artifact_refs": {"problem_frame": PATHS["problem_frame"], "research_brief": PATHS["research_brief"]}},
            {"next_stage": "DONE", "artifact_refs": refs},
        ],
    }
    with pytest.raises(AssertionError):
        _validate_chain(_schema(project_root), chain)


def test_decide_chain_rejects_resolvable_downstream_ref_published_early(project_root: Path) -> None:
    artifacts = _decide_artifacts("GENERAL")
    refs = {name: PATHS[name] for name in PATHS}
    base_workflow = minimal_payloads()["workflow"]
    chain = {
        "content_profile": "GENERAL",
        "workflow": {**base_workflow, "analysis_goal": "DECIDE", "research_state": "RESEARCH_COMPLETE", "next_stage": "DONE", "artifact_refs": refs},
        "artifacts": artifacts,
        "report_contract": {"workflow_id": base_workflow["workflow_id"], "analysis_goal": "DECIDE", "content_profile": "GENERAL", "evidence_revision": 1, "views": ["dynamic-problem-theme"], "omitted_views": []},
        "transitions": [
            {"next_stage": "problem-framing", "artifact_refs": {"decision": PATHS["decision"]}},
            {"next_stage": "research-design-kickoff", "artifact_refs": {"decision": PATHS["decision"], "problem_frame": PATHS["problem_frame"]}},
            {"next_stage": "research-execution", "artifact_refs": {"decision": PATHS["decision"], "problem_frame": PATHS["problem_frame"], "research_brief": PATHS["research_brief"]}},
            {"next_stage": "decision-readiness-interview", "artifact_refs": {"decision": PATHS["decision"], "problem_frame": PATHS["problem_frame"], "research_brief": PATHS["research_brief"], "evidence_package": PATHS["evidence_package"]}},
            {"next_stage": "adversarial-option-selection", "artifact_refs": {name: PATHS[name] for name in ("decision", "problem_frame", "research_brief", "evidence_package", "readiness_pack")}},
            {"next_stage": "solution-refinement", "artifact_refs": {name: PATHS[name] for name in ("decision", "problem_frame", "research_brief", "evidence_package", "readiness_pack")}},
            {"next_stage": "solution-documentation", "artifact_refs": {name: PATHS[name] for name in ("decision", "problem_frame", "research_brief", "evidence_package", "readiness_pack", "refined_solution")}},
            {"next_stage": "solution-decomposition", "artifact_refs": {name: PATHS[name] for name in ("decision", "problem_frame", "research_brief", "evidence_package", "readiness_pack", "refined_solution", "solution_document")}},
            {"next_stage": "DONE", "artifact_refs": refs},
        ],
    }
    with pytest.raises(AssertionError):
        _validate_chain(_schema(project_root), chain)
