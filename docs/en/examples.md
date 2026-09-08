[简体中文](../zh-CN/examples.md) · [Home](../../README.md)

# Example prompts and outputs

First load the entry skill and its references using the [generic quick start](quickstart.md) or your host's adapter. These are illustrative output excerpts, not transcripts of live end-to-end runs. Each Chinese example has the same scope and facts as its English counterpart. The plugin may ask material follow-up questions and presents a preview before final acceptance.

## 1. Understand a general problem, offline

**Prompt**

> Use problem-navigator. Answer in English. Using only these notes, explain why our weekly meeting overruns: planned duration 30 minutes; last three meetings lasted 45, 50, and 55 minutes; agenda items were added during each meeting. Do not browse or select a solution yet. Produce a research report with facts, inferences, and unknowns.

**Route:** `UNDERSTAND` + `GENERAL` → `RESEARCH_REPORT`; backend `NONE`.

**Illustrative report excerpt**

> **FACT:** The three recorded meetings exceeded their planned duration by 15, 20, and 25 minutes. Source: user-provided meeting notes, duration entries.
>
> **INFERENCE:** Added agenda items could contribute to overruns, but the notes do not establish causation.
>
> **UNKNOWN:** Time spent on each item, whether the original agenda was realistic, and whether participants consider the extra time useful.
>
> **Next evidence needed:** Item-level timing and participants' accounts. This report supports understanding the gap; it does not yet rank solutions.

No public source or provider call should be invented. The supplied notes establish what was reported, not independent verification of the meetings.

## 2. Define a product, PRD only

**Prompt**

> Use problem-navigator in English. We need a room-booking product for one office with four shared rooms. Employees must see availability, reserve a free time slot, and cancel their own reservation. Reception can cancel any reservation. Conflicting reservations must be rejected. Use only this brief; do not browse. Help resolve remaining product decisions and deliver a PRD only, with stable requirement and acceptance IDs. Do not choose an implementation stack.

**Route:** `DECIDE` + `PRODUCT_SOFTWARE` → `PRD_ONLY`; backend `NONE`.

**Illustrative `01-prd.md` excerpt**

> **REQ-001 — Prevent conflicting bookings:** A room cannot have overlapping active reservations.
>
> **AC-001:** Given an active reservation for a room, when another request overlaps its time interval, that request is rejected and the existing reservation remains unchanged.
>
> **REQ-002 — Cancellation authority:** Employees may cancel their own reservations; reception may cancel any reservation.
>
> **Open decision:** Confirm office hours and whether adjacent bookings may share an endpoint before accepting the PRD.

The full preview covers the agreed users, scope, relevant constraints, and acceptance criteria. No architecture selection or technical-spec member is required for this endpoint. Open product decisions must be resolved or explicitly retained as limitations before acceptance.

## 3. Resolve a technical design problem

**Prompt**

> Use problem-navigator. Answer in English. We have an existing service that receives duplicate event deliveries. Our supplied contract gives every event a stable ID, requires duplicate deliveries to have no repeated side effects, and requires processing acknowledgements only after durable completion. The storage system supports atomic transactions. Use only these constraints, compare design alternatives, and produce a technical solution specification only. Do not create a PRD, code, or implementation tasks.

**Route:** `DECIDE` + `PRODUCT_SOFTWARE` → `TECHNICAL_SPEC_ONLY`; backend `NONE`.

**Illustrative `01-technical-solution-spec.md` excerpt**

> **DES-001 — Durable duplicate detection:** Evaluate storing the event ID and the side effect in one atomic transaction against a separate deduplication store.
>
> **Design condition:** The one-transaction option is viable only if the relevant side effect can participate in that transaction. External side effects remain an unresolved boundary.
>
> **AC-001:** Replaying a completed event must leave the durable business outcome unchanged.
>
> **AC-002:** Acknowledgement occurs only after the relevant durable state commits.
>
> **UNKNOWN:** Retention duration for event IDs and whether any side effects are external.

The final design depends on the actual alternatives, clarified boundaries, and user decision. No PRD identifier is fabricated. Acceptance criteria describe behavior; the deliverable does not include test code.

## Optional Web evidence variation

After [configuring a provider](configuration.md), extend a request with:

> Use public official documentation to verify the current constraints relevant to this design. Before research, state the query/URL scope and selected provider routes. Keep confidential system names out of outbound queries, distinguish source facts from inferences, and retain precise citations and retrieval dates.

Expected additions are source-backed findings, operation receipts, and limitations when sources are missing or truncated. `web_research_status` alone is not a research result. If you explicitly prefer host-native research, name that choice and its scope in the prompt.

To switch output language, add “Write the final report in Chinese” or “最终报告请用英文”. Translate prose while preserving schema keys, enum values, IDs, canonical filenames, and original citations.
