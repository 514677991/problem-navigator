# Product and software research design

Use this guide only for `PRODUCT_SOFTWARE`. During framing, use the six-input
section to clarify scope; during research design, use the remaining sections to
turn that accepted scope into executable questions. `GENERAL` chooses its own
relevant themes and does not inherit this scaffold.

The guide supplies domain knowledge, not a fixed questionnaire or task count.
An `UNDERSTAND` request needs explanations and evidence boundaries, without
manufactured candidates, rankings or recommendations. A `DECIDE` brief asks for
evidence that can distinguish alternatives; selection belongs to later stages.

## Six inputs, asked only where needed

Read the user's request, accepted frame and supplied materials first. The frame
holds accepted scope and constraints in its existing fields. During research design,
summarize the six inputs in the brief's `design.product_context` with labels and references
to that frame/material context. For each, record what is known, what requires user
clarification, what research must find, or why it is not applicable. Do not create a
second product specification, new frame fields or a new state machine. A supplied
claim remains attributed to its source; inclusion in the frame does not verify it.

| Input | What to capture | How it changes research |
|---|---|---|
| Product definition | What is being built or examined, for whom, in which situation, and what outcome it should enable. | Identifies relevant user journeys, actual alternatives and success constraints. If the intended user changes the boundary, ask who needs the outcome and when. |
| Target market | Intended regions, languages and deployment/customer setting; distinguish a user decision from unknown market facts. | Directs competitor discovery, local availability, source languages, pricing/currency and applicable resource restrictions. Research public market facts; do not ask the user to supply them. |
| Competitor or substitute anchors | Products, links, screenshots, current workflow or manual substitutes already known to the user. | Gives discovery a starting point. No known competitor is a research gap, not proof of novelty or a reason to stop. Include direct, adjacent or non-software alternatives when they address the same need. |
| Critical resources | External data, APIs, hardware, models, content or another indispensable input; note the limiting resource and significant dependencies. | Selects the resource-specific dimensions below. Multiple critical types can coexist; do not force all projects into one resource category. |
| Reuse intention | Existing user instruction to build afresh, fork, reuse modules, study precedents, or leave the choice open. | Changes the depth of licensing, replaceability and integration research. An open choice calls for comparative evidence, not a forced early preference. |
| Capability/module map | User-visible capabilities and, where technical scope calls for it, existing or provisional subsystem boundaries and interfaces. | Organizes module-level alternatives and integration questions. No fixed number of modules, forced MVP cut or invented architecture. For PRD-only work, capability boundaries can be sufficient. |

Ask only about an unknown that materially changes scope and is controlled by the
user, such as intended customers, delivery endpoint or a hard constraint. Ask the
smallest useful question and reuse answers already supplied. Public facts become
research questions; delegated choices remain open for evidence and later decision.
Do not require six questions, a prescribed interview rhythm or a separate approval
for each input. An unresolved public fact does not prevent an otherwise clear frame.

## Apply the four themes to the actual deliverable

Check product form, critical resources, open-source ecosystem and implementation
paths. Explain meaningful omissions or merges in the brief. These are coverage
prompts, not four mandatory tasks, four agents or four output documents. A single
well-bounded task may cover related dimensions; split when questions or dependencies
need distinct treatment, not to obtain more calls.

`PRD_ONLY` studies user journeys, product behavior and feasibility constraints that
affect requirements; it does not select a stack or demand a technical architecture.
`TECHNICAL_SPEC_ONLY` starts from available code, logs, versions, interfaces and
observed behavior. It can omit broad market/product discovery when that cannot
change the technical question. An existing-system diagnosis does not need a new
product definition exercise.

### Product form

Use the supplied competitor/substitute anchors and target market to find relevant
examples. Compare the parts that bear on the user's problem:

- Information architecture: entry points, navigation, information organization and
  the path to the main outcome.
- Core interaction: creation, management, triggers, feedback, exception/recovery
  states and accessibility or collaboration needs when they affect the scenario.
- Result delivery: dashboard, card, export, notification, message or other surface,
  including what the user can do after receiving the result.
- AI fit when relevant: the actual task improved, human review/control, failure
  behavior and evidence of usable capability; distinguish an advertised feature
  from demonstrated behavior or adoption.

Ask for a comparison organized by user journey or capability, with identifiable
products and source/screenshot locations for concrete observations. Record where
the evidence comes from a demo, documentation, supplied screenshot or measured
use. Do not infer popularity or quality from marketing language. No fixed minimum
number of competitors substitutes for relevant coverage.

### Critical resources

Choose the rows matching the project's real dependencies. Compare facts under
compatible versions, regions, workloads and commercial terms; expose missing
conditions rather than inventing a common baseline.

| Type | Research dimensions that can change feasibility | Useful comparison output |
|---|---|---|
| Data | Official, licensed, open or otherwise permissible channels; coverage, granularity, freshness, latency, history/backfill, quotas, price, onboarding, provenance and permitted use/redistribution. | Source-by-dimension matrix, unsupported coverage, access restrictions and evidence for replacement or fallback paths. |
| API/service | Capability and endpoint fit, regional availability, price/free tier, workload-based cost, rate limits/quotas, documented SLA, authentication, data retention/residency and migration/interface compatibility. | Comparable plans and usage assumptions, failure/exit conditions, primary-source terms and unresolved operational gaps. An SLA promise is not measured reliability. |
| Hardware | Required components and interfaces, compatible substitutes, unit/BOM costs at the relevant quantity, minimum order, lead time, supply continuity, certification/support and operating constraints. | Component/supplier comparison with dated quantity assumptions, compatibility risks and substitute dependencies. |
| Model | Task/domain/language fit, model/version and hosting mode, license and usage terms, representative evaluation conditions, known failure modes, context/input limits, latency/throughput, inference cost and deployment/data constraints. | Model-by-task evidence matrix separating published benchmarks, vendor claims and actual local measurements; gaps for task-specific validation. |
| Content | Authoritative origin, topical/language coverage, update cadence, access, licensing/attribution/redistribution, provenance, moderation needs and ingestion/format quality. | Content-source comparison, permission/update gaps and the effect of missing or stale material on the product. |

For a different resource type, derive dimensions from how its absence, failure,
cost or replacement would affect the intended outcome. Do not force it into an
unrelated row. Research viable fallback mechanisms when continuity matters; do
not declare a preferred supplier or fallback selected in the brief.

### Open-source ecosystem and reuse

Seed discovery with the capability/module terms and relevant local and original
source languages. Cover the repositories and ecosystems that plausibly contain
the needed capability, without fixed project counts or mandatory bilingual searches
when they add no coverage.

For relevant projects, ask for license and redistribution obligations, current
release/commit and maintenance evidence, stack/runtime compatibility, supported
capabilities, material gaps, reusable boundaries, integration effort and dependencies.
Stars alone establish neither quality nor active maintenance. Distinguish a full
fork, modular integration and design reference; a demo does not establish production
fitness. Compare upkeep, upgrade and exit costs as well as initial implementation.

The useful output is a capability-to-project reuse matrix with dated source
locations and explicit gaps. If the user has already ruled out reuse, retain only
the precedent or feasibility research that can change the answer; explain the trim.
If reuse is undecided, collect the evidence needed to compare it with building.

### Implementation paths

Use the capability/module map at the level required by the endpoint. Describe each
module's responsibility, inputs/outputs and dependencies before researching
alternatives. Prefer boundaries that allow meaningful independent comparison;
do not present that provisional map as an approved architecture.

| Relevant module | Example questions to adapt |
|---|---|
| Resource intake | How are inputs received, validated, cleaned, refreshed and handed to storage? Which source limits affect the path? |
| Storage | Which access patterns need history, caching, user data or search; what consistency, retention and migration limits follow? |
| Core behavior | Which algorithms, rules, workflows or scheduling approaches meet the actual workload; where do they fail? |
| Interface | Which rendering, component, visualization, accessibility or real-time capabilities are required by the user journeys? |
| Notifications/integrations | What delivery channels, authentication, failure handling, usage charges and integration limits apply? |
| Deployment/operations | What hosting, runtime, observability, recovery and maintenance needs follow; what cost assumptions remain unverified? |
| Identity/billing | If in scope, what authorization, account, payment and subscription behaviors and provider constraints must be supported? |

Ask for relevant alternatives, conditions under which each fits or fails,
integration/interface consequences and supported effort/cost ranges. Include
reasons a plausible alternative may not fit. Carry unknown workloads or effort
assumptions explicitly; a precise-looking estimate is not evidence. Module-level
comparisons and a provisional dependency diagram may help a technical endpoint;
they do not choose a stack. Do not expand a requirements-only request into these
technical details.

## Evidence quality and honest stopping

Make critical dimensions explicit in each task's quality bar. A decisive resource
claim should be traceable to its primary source and passage, with the relevant
version/date, region, plan, quantity or workload. First-party documentation can
establish a stated limit or term; it does not by itself prove observed performance,
reliability, adoption or fitness for the user's task. Use appropriate independent
evidence for those claims and preserve attribution to the actual source.
Mark FACT items critical when they could change feasibility, a key explanation or
the comparison, following the shared evidence contract and retaining passage locators.

Target counterevidence at claims whose failure could change feasibility, a key
explanation or a candidate comparison. Look for contrary conditions, failure cases
and incompatible evidence; do not manufacture an opposing claim or a quota of
defects. Resolve differences in date/version/conditions where possible. Keep any
remaining conflict and its impact visible instead of averaging it into agreement.

Define completion through covered dimensions and a usable comparison or explanation,
not "research thoroughly" or an arbitrary source count. If a needed fact cannot be
established within authorized access and the shared stopping/budget rules, produce
an explicit gap with what was attempted, what remains unknown and what conclusion
it could change. A gap is not evidence that a candidate is inferior. In `UNDERSTAND`,
describe the explanation's limits without inventing candidate IDs.

A proposed benchmark, trial, ablation or prototype is a validation question until
authorized and actually executed. Label published, supplied, inferred and proposed
results distinctly; never report a planned experiment as an observed result.

## Example: turn a resource gap into a task

Suppose the accepted frame requests a support-summary product for French-speaking
customers in the EU, sets a user-supplied monthly volume and prohibits training on
customer messages. Those are planning inputs, not verified provider capabilities.
One API task can read as follows; the rest of the brief and its theme coverage still
follow the stage contract.

```yaml
task_id: RES-001
theme_id: critical-resources
purpose: Establish which API constraints could prevent the scoped support-summary service.
question: |
  Using the accepted frame's French-language task, EU setting, monthly volume and
  no-training constraint, compare relevant API plans. What capability evidence,
  regional access, retention/training terms, quotas and documented service limits
  apply? What workload assumptions are needed for comparable costs? Which claimed
  capabilities have contrary evidence or still need task-specific validation?
task_kind: PUBLIC_WEB
direction: developer
domains: []
freshness: ""
expected_output: |
  A plan-by-constraint evidence matrix with sources, applicable versions/regions,
  workload-based cost inputs, conflicts and gaps; no selected supplier.
quality_bar: |
  Trace decisive limits and terms to primary passages and dates. Separate stated
  SLA/capability claims from observed results. Mark critical FACT items, show the
  cost assumptions, and preserve any contrary evidence affecting feasibility.
stop_condition: |
  Finish when each scoped constraint has supported comparative evidence or an
  explicit unresolved gap and impact. If authorized access or shared limits stop
  the task first, report the missing dimensions and attempts without claiming completion.
depends_on: []
```

The same pattern can be much shorter for one supplied-material question. Change
the dimensions and output to fit the problem; do not copy this API checklist into
an unrelated product or GENERAL task.
