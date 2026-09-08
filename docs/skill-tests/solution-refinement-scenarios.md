# Solution refinement scenarios — 2.0.0

| Case | Expected contract result |
|---|---|
| Wrong stage | Return to `$problem-navigator`; no artifact or workflow mutation. |
| Missing decision/evidence | `MISSING_OR_INVALID_ARTIFACT`, `STOPPED`, no reconstruction. |
| GENERAL DECIDE | Freeze a complete general solution definition; do not create a PRD or formal report. |
| PRODUCT_SOFTWARE DECIDE | Freeze What before constrained How, with stable requirement and acceptance IDs. |
| Changed objective/profile | Stop the old workflow and require a new one; do not silently reuse the decision. |
| Public-fact gap | Legal supplemental evidence route; do not research or invent it here. |

The stage never produces code, tests, plans, tasks, tickets, schedules, staffing,
source-file lists, deployment/migration commands, or an implementation handoff.
