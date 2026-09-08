# Problem framing scenarios — 2.0.0

Frame exactly two independent axes once: `analysis_goal: UNDERSTAND | DECIDE` and
`content_profile: GENERAL | PRODUCT_SOFTWARE`. `UNDERSTAND` asks for research/report
depth; `DECIDE` enters the decision chain. `PRODUCT_SOFTWARE` selects research and
document shape only; it never creates a separate product/software workflow. Missing or
invalid state stops with `MISSING_OR_INVALID_ARTIFACT`; a wrong-stage call returns to
the entry without mutation.

Only an explicitly accepted product request to end at the PRD records the exact
`delivery_endpoint: PRD_ONLY` sentinel.
