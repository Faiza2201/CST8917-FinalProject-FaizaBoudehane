# Version B Build Notes

`logicapp-workflow.json` is a **skeleton/reference**, not something you can paste into
Code View and run as-is — Consumption Logic Apps generate connection references and
variable initializers automatically when you build in the visual designer, and the
portal will fight you if you hand-author every GUID. Use this file as your map, then
build the real thing in the designer. That also gives you the screenshots the
assignment asks for.

## Order of operations in the Azure Portal

1. **Service Bus namespace** — create it first (Standard tier, you need topics).
   - Queue: `expense-requests`
   - Topic: `expense-outcomes`
     - Subscription: `manager-decisions` (filter: `outcome = pending`)
     - Subscription: `approved-sub` (filter: `outcome = approved`)
     - Subscription: `rejected-sub` (filter: `outcome = rejected`)
     - Subscription: `escalated-sub` (filter: `outcome = escalated`)

2. **Validation Function App** — deploy `function_app.py` from this folder first so you
   have a URL + function key to paste into the Logic App's HTTP action.

3. **Logic App (Consumption)** — build in the designer in this order:
   1. Trigger: Service Bus — *When a message is received in a queue* (`expense-requests`)
   2. **Initialize variables** (add this — not in the JSON skeleton, do it first thing
      after the trigger): `finalOutcome` (string), `decisionReceived` (bool, default false),
      `managerDecision` (string), `pollCount` (integer, default 0)
   3. Parse JSON on the message content
   4. HTTP action calling your validation Function
   5. Condition: `valid == true`
      - False branch → send validation-error email, terminate
      - True branch → Condition: `requiresApproval == true`
        - False → set `finalOutcome = approved`
        - True → publish a `pending` message to `expense-outcomes`, then an **Until**
          loop that peeks the `manager-decisions` subscription every ~20s, up to a
          count/timeout that stands in for the assignment's timeout window, setting
          `decisionReceived`/`managerDecision` if a message shows up
      - After the loop: Condition on `decisionReceived` → set `finalOutcome` to the
        manager's decision, else set it to `escalated`
   6. Publish final outcome message to `expense-outcomes` (topic) with the outcome as
      a message property, so the three outcome subscriptions filter correctly
   7. Send employee email (Office 365 Outlook or SendGrid connector) with `finalOutcome`

4. **Document the honest limitation** in your comparison write-up: Logic Apps has no
   native equivalent to Durable Functions' `wait_for_external_event` + durable timer
   race. Polling is the pragmatic workaround — call this out explicitly in Part 3,
   it's exactly the kind of "specific, not generic" observation the rubric wants.

## Screenshots to capture (per the assignment)
- Logic App **Run history** showing a completed run for each of the 6 test scenarios
- The **condition branches** taken (expand the run to show valid/invalid, auto-approve
  vs. approval-required, approved/rejected/escalated)
- The **email received** (approved, rejected, escalated, and validation-error cases)
- **Topic subscription message counts** in the Service Bus namespace (Portal → Topic →
  Subscriptions, showing message counts moving as the workflow runs)
