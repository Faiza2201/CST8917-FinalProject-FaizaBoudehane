# CST8917 — Assignment 2: Dual Implementation of an Expense Approval Workflow

**Name:** [YOUR NAME]
**Student Number:** [YOUR STUDENT #]
**Course:** CST8917 — Serverless Applications
**Project:** Compare & Contrast — Durable Functions vs. Logic Apps + Service Bus
**Date:** [DATE]

> ⚠️ Fill in the bracketed placeholders above and throughout, and replace the
> comparison text below with your own observations once you've actually run both
> versions — see the note at the end of this file.

---

## Version A Summary — Durable Functions

Version A implements the workflow as a single Durable Functions app (Python v2
model) with three function types:

- **Client function** (`submit_expense`, HTTP-triggered): starts a new orchestration
  instance per expense and returns Durable Functions' standard status-check URLs.
- **Orchestrator function** (`expense_orchestrator`): chains validation → threshold
  check → (conditionally) a race between `wait_for_external_event("ManagerDecision")`
  and a `create_timer` durable timer → notification. This is the Human Interaction
  pattern taught in the course, applied directly.
- **Activity functions** (`validate_expense`, `notify_employee`): the actual business
  logic, kept deliberately simple/synchronous so the orchestrator's control flow stays
  readable.
- **Second HTTP endpoint** (`manager_decision`) simulates the manager: it calls
  `raise_event` against a running orchestration instance to deliver an approve/reject
  decision.

**Design decisions:**
- `TIMEOUT_MINUTES` is set short (2 min) for demo purposes — call this out in your
  video and mention what you'd use in production (e.g., 48 hours).
- Notification is a logged message rather than a real email, to keep the demo
  self-contained; note in your write-up whether you swapped in SendGrid/ACS Email.

**Challenges:** [fill in what actually gave you trouble — e.g., getting the
Azurite storage emulator running, understanding `task_any` semantics, local.settings
gotchas, etc.]

---

## Version B Summary — Logic Apps + Service Bus

Version B decomposes the same workflow across services instead of one codebase:

- A **Service Bus queue** (`expense-requests`) receives incoming expense JSON.
- A **Logic App** triggers on new queue messages, calls an **Azure Function**
  (`/api/validate`) for validation, branches on the result, and branches again on the
  $100 threshold.
- For amounts requiring approval, the **approach chosen for manager approval** is
  polling: the Logic App publishes a `pending` message to a Service Bus topic
  (`expense-outcomes`) and polls a `manager-decisions` subscription on a timer inside
  an `Until` loop, bounded by an iteration count that stands in for the timeout window.
  Logic Apps has no native equivalent of Durable Functions' `wait_for_external_event` +
  durable-timer race, so this loop is the pragmatic substitute — worth stating plainly
  rather than glossing over.
- The final outcome is published back to the `expense-outcomes` topic with an
  `outcome` message property, and three filtered subscriptions (`approved`,
  `rejected`, `escalated`) let downstream consumers (or just the portal, for your
  screenshots) see the split.
- An email connector (Office 365 Outlook or SendGrid) sends the employee the result.

**Challenges:** [fill in — e.g., wiring API connections in the designer, getting the
Until loop's variables initialized correctly, correlating the manager decision message
back to the right expense, etc.]

---

## Comparison Analysis

> The paragraphs below are a strong starting draft based on the two implementations
> above. **You must personalize this with what you actually experienced** — timings,
> specific error messages you hit, screenshots you can point to. Graders can tell a
> generic comparison from a lived one; the assignment explicitly says "Durable
> Functions was easier to test" is a weak sentence on its own.

### Development Experience

Building Version A felt like writing normal Python with one unusual constraint: the
orchestrator function must be deterministic and side-effect-free, delegating all I/O to
activities. Once that rule clicked, the whole workflow — validation, branching,
timeout, notification — lived in about 90 lines of one file, and `func start` gave a
tight local edit-test loop. Version B distributes the same logic across a queue, a
Function, a Logic App, and a topic with three subscriptions. Each of those is
individually simple, but wiring them together happens partly in a JSON workflow
definition and partly by clicking through connector authentication in the portal,
which is slower to iterate on and harder to keep in version control cleanly (the
Logic App JSON references connection GUIDs that don't travel well between
environments). [Add your own timing: how long did each actually take you to get to a
first successful end-to-end run?]

### Testability

The Durable Functions orchestrator can be tested with plain HTTP calls against a
locally running Function host — the `test-durable.http` file in this repo drives all
six scenarios without touching Azure at all (aside from the local Azurite emulator).
The validation and notification activities are also just Python functions, so unit
testing them with `pytest` requires no mocking of Azure infrastructure. Version B is
harder to test in isolation: the validation Function can be unit-tested the same way,
but the orchestration logic itself only exists inside the Logic App designer/runtime,
so verifying the full flow means actually deploying and running it in Azure — there's
no local Logic Apps emulator equivalent to Azurite for this kind of testing setup.
[State what you actually did — did you use the Azure Logic Apps (Standard) local
runtime, or purely cloud-based testing?]

### Error Handling

Durable Functions gives fine control: activity retries can be configured with
`RetryOptions` (max attempts, backoff), and unhandled exceptions in an activity
surface as catchable exceptions in the orchestrator, so you can wrap steps in
try/except and branch on failure explicitly. Logic Apps' error handling is
configuration-driven — each action has a built-in retry policy (count, interval,
type) set via the designer or JSON, and you can add a "Run after" branch that fires
only on `Failed`/`TimedOut`/`Skipped`. It's less code but also less flexible for
anything beyond simple retry-then-branch logic. [Note anything you observed about
where a step actually failed during testing and how each platform surfaced it.]

### Human Interaction Pattern

This was the sharpest contrast. Durable Functions expresses "wait for a human, but
not forever" natively and precisely with `context.task_any([wait_for_external_event,
create_timer])` — the orchestrator suspends (at zero cost while idle) and resumes the
instant either the event or the timer fires. Logic Apps has no equivalent primitive
for Consumption workflows, so Version B approximates it with a polling `Until` loop
against a Service Bus subscription, which is coarser (decision latency is bounded by
the poll interval, not instant) and burns a recurring action execution on every poll
even when nothing has changed. Durable Functions' approach is the more "natural" fit
for exactly the pattern the assignment names. [If you explored an alternative for
Version B — e.g., an HTTP webhook/callback action instead of polling — describe what
you tried and why you did or didn't switch to it.]

### Observability

Durable Functions instances get built-in status-query endpoints
(`statusQueryGetUri`) plus visibility into Application Insights, and the Durable
Task Framework's instance history (`replay` log) shows exactly which activity ran
when. Logic Apps' Run History in the portal is arguably more approachable for a
non-developer audience — every action shows its inputs/outputs and status inline,
with no separate query needed — which is likely why the assignment specifically asks
for run-history screenshots from Version B. [Compare what you actually found easier
when something went wrong — cite a specific failed run from your testing.]

### Cost

Both are consumption-priced serverless options, so cost scales with volume rather
than idle capacity — estimate this yourself with the Azure Pricing Calculator rather
than trusting numbers here, since pricing changes. As a starting structure for your
estimate:

| Scale | Durable Functions cost drivers | Logic Apps + Service Bus cost drivers |
|---|---|---|
| ~100 expenses/day (~3,000/mo) | Function executions (client + orchestrator replays + 2 activities per expense) + storage transactions for orchestration state | Logic App action executions (≈8–10 actions per run incl. polling) + Service Bus namespace base cost + queue/topic operations |
| ~10,000 expenses/day (~300,000/mo) | Same drivers, scaled — orchestration replay overhead becomes more visible in Functions execution counts | Polling loop actions dominate — each pending approval multiplies action-executions by however many 20s polls it takes, so this is the line item to watch |

State your assumptions explicitly: average % of expenses requiring approval, average
wait time for a manager decision (drives Durable Functions timer duration and Logic
Apps poll count), and whether you're on Service Bus Standard or Premium tier.

---

## Recommendation

[200–300 words — draft below as a starting point, personalize with your own
reasoning]

For a production expense-approval system, Durable Functions is the stronger default
choice specifically because of how central the "wait for a human, with a timeout"
requirement is to this workflow — it's a first-class pattern in the Durable Task
Framework, not a workaround. That translates directly into better testability (a
local HTTP test suite, no cloud dependency to validate core logic), tighter control
over retries and error branching, and lower operational cost at scale since idle
waiting doesn't cost polling actions. The trade-off is that it requires developers
comfortable writing and reasoning about orchestrator code and its determinism
constraints — not a small ask for a team without existing Azure Functions experience.

I would choose Logic Apps + Service Bus instead when the audience for maintaining the
workflow is primarily non-developers — business analysts or ops staff who need to see
and adjust conditions visually without a deploy pipeline — or when the workflow needs
to integrate many pre-built connectors (CRM, ticketing, SaaS APIs) where Logic Apps'
400+ connector catalog beats hand-rolling SDK calls in Durable Functions activities.
It's also the better fit if the "human interaction" step in a given workflow is
naturally event-driven from an external system (e.g., a webhook callback from an
approval portal) rather than needing a precise timer race, since that sidesteps the
polling weakness entirely.

---

## References

- [Add every source you actually used — Microsoft Learn docs, blog posts, Stack
  Overflow answers — as working hyperlinks. Do not leave this section templated.]

## AI Disclosure

Per the assignment's AI policy: [state which AI tools you used, for what parts, and
how you verified/modified the output — this is mandatory, not optional.]
