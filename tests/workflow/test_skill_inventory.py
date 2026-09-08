from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


ENTRY = "problem-navigator"
STAGES = (
    "problem-framing",
    "research-design-kickoff",
    "research-execution",
    "decision-readiness-interview",
    "adversarial-option-selection",
    "solution-refinement",
    "solution-documentation",
    "solution-decomposition",
)
EXPECTED = {Path("skills") / name / "SKILL.md" for name in (ENTRY, *STAGES)}


def _parse_gate(text: str, stage: str) -> dict[str, object]:
    marker = re.search(r"stage_gate: next_stage == ([a-z-]+)", text)
    wrong = re.search(r"wrong_stage: return=problem-navigator; artifact_writes=(\d+); state_mutations=(\d+)", text)
    invalid = re.search(r"invalid_artifact: atomic_next_stage=(STOPPED); blocking_reason\.code=([A-Z_]+)", text)
    assert marker and wrong and invalid
    return {
        "own_stage": marker.group(1),
        "wrong_return": "problem-navigator",
        "artifact_writes": int(wrong.group(1)),
        "state_mutations": int(wrong.group(2)),
        "invalid_next_stage": invalid.group(1),
        "invalid_code": invalid.group(2),
    }


def test_exactly_nine_canonical_skill_paths_without_collapsing_duplicates(project_root: Path) -> None:
    actual = [path.relative_to(project_root) for path in (project_root / "skills").rglob("SKILL.md")]
    assert len(actual) == 9
    assert set(actual) == EXPECTED
    assert len(actual) == len(set(actual))


def test_entry_routes_resolve_to_the_named_sibling_skill(project_root: Path) -> None:
    entry = project_root / "skills" / ENTRY / "SKILL.md"
    routes = re.findall(
        r"^\|\s*([a-z-]+)\s*\|\s*\[[^\]]+\]\(([^)]+)\)\s*\|$",
        entry.read_text("utf-8"),
        flags=re.MULTILINE,
    )
    assert len(routes) == len(STAGES)
    assert {stage for stage, _ in routes} == set(STAGES)
    for stage, relative in routes:
        target = (entry.parent / relative).resolve()
        assert target == (project_root / "skills" / stage / "SKILL.md").resolve()
        frontmatter = yaml.safe_load(target.read_text("utf-8").split("---", 2)[1])
        assert frontmatter["name"] == stage


def test_common_instructions_do_not_require_host_invocation_aliases(project_root: Path) -> None:
    aliases = re.compile(r"\$(?:" + "|".join((ENTRY, *STAGES)) + r")\b")
    for path in (project_root / "skills").rglob("*.md"):
        assert not aliases.search(path.read_text("utf-8")), path.relative_to(project_root)


@pytest.mark.parametrize("stage", STAGES)
def test_every_child_has_exact_gate_and_wrong_stage_is_byte_stable(project_root: Path, stage: str) -> None:
    text = (project_root / "skills" / stage / "SKILL.md").read_text("utf-8")
    gate = _parse_gate(text, stage)
    assert gate == {
        "own_stage": stage,
        "wrong_return": "problem-navigator",
        "artifact_writes": 0,
        "state_mutations": 0,
        "invalid_next_stage": "STOPPED",
        "invalid_code": "MISSING_OR_INVALID_ARTIFACT",
    }


@pytest.mark.parametrize("stage", STAGES)
def test_every_child_invalid_artifact_stops_with_required_reason(project_root: Path, stage: str) -> None:
    text = (project_root / "skills" / stage / "SKILL.md").read_text("utf-8")
    gate = _parse_gate(text, stage)
    assert gate["invalid_next_stage"] == "STOPPED"
    assert gate["invalid_code"] == "MISSING_OR_INVALID_ARTIFACT"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda text: text.replace("stage_gate: next_stage == solution-refinement", "stage_gate: next_stage == solution-documentation"),
        lambda text: text.replace("return=problem-navigator", "return=solution-refinement"),
        lambda text: text.replace("artifact_writes=0", "artifact_writes=1"),
        lambda text: text.replace("state_mutations=0", "state_mutations=1"),
        lambda text: text.replace("atomic_next_stage=STOPPED", "atomic_next_stage=DONE"),
        lambda text: text.replace("MISSING_OR_INVALID_ARTIFACT", "INVALID"),
    ],
)
def test_each_normative_gate_clause_is_independently_mutation_guarded(mutation) -> None:
    contract = (
        "stage_gate: next_stage == solution-refinement\n"
        "wrong_stage: return=problem-navigator; artifact_writes=0; state_mutations=0\n"
        "invalid_artifact: atomic_next_stage=STOPPED; blocking_reason.code=MISSING_OR_INVALID_ARTIFACT"
    )
    with pytest.raises(AssertionError):
        parsed = _parse_gate(mutation(contract), "solution-refinement")
        assert parsed == {
            "own_stage": "solution-refinement",
            "wrong_return": "problem-navigator",
            "artifact_writes": 0,
            "state_mutations": 0,
            "invalid_next_stage": "STOPPED",
            "invalid_code": "MISSING_OR_INVALID_ARTIFACT",
        }


def test_agent_metadata_exposes_only_entry_implicitly(project_root: Path) -> None:
    for name in (ENTRY, *STAGES):
        metadata = project_root / "adapters" / "codex" / "skills" / name / "agents" / "openai.yaml"
        assert metadata.is_file()
        parsed = yaml.safe_load(metadata.read_text("utf-8"))
        assert parsed["policy"]["allow_implicit_invocation"] is (name == ENTRY)


def test_no_retired_stage_or_execution_exit_tokens(project_root: Path) -> None:
    production = "\n".join(path.read_text("utf-8") for path in (project_root / "skills").rglob("SKILL.md"))
    for token in ("web-research-execution", "READY_FOR_PLANNING", "DIRECT_EXECUTION", "selected_executor", "workflow_control"):
        assert token not in production
