import azure.functions as func
import azure.durable_functions as df
import logging
from datetime import timedelta

myApp = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

VALID_CATEGORIES = {"travel", "meals", "supplies", "equipment", "software", "other"}
REQUIRED_FIELDS = ["employee_name", "employee_email", "amount", "category", "description", "manager_email"]
AUTO_APPROVE_THRESHOLD = 100
# Kept short for demo/testing. Bump to a realistic value (e.g. 48 hrs) for the README discussion.
TIMEOUT_MINUTES = 2


# ---------- HTTP: start a new expense workflow ----------
@myApp.route(route="expenses/submit", methods=["POST"])
@myApp.durable_client_input(client_name="client")
async def submit_expense(req: func.HttpRequest, client):
    try:
        expense = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    instance_id = await client.start_new("expense_orchestrator", client_input=expense)
    logging.info(f"Started orchestration with ID = {instance_id}")
    return client.create_check_status_response(req, instance_id)


# ---------- HTTP: simulate manager approving/rejecting ----------
@myApp.route(route="expenses/{instanceId}/decision", methods=["POST"])
@myApp.durable_client_input(client_name="client")
async def manager_decision(req: func.HttpRequest, client):
    instance_id = req.route_params.get("instanceId")
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    decision = body.get("decision")
    if decision not in ("approved", "rejected"):
        return func.HttpResponse('decision must be "approved" or "rejected"', status_code=400)

    await client.raise_event(instance_id, "ManagerDecision", decision)
    return func.HttpResponse(f"Decision '{decision}' sent to instance {instance_id}", status_code=200)


# ---------- Orchestrator ----------
@myApp.orchestration_trigger(context_name="context")
def expense_orchestrator(context: df.DurableOrchestrationContext):
    expense = context.get_input()

    # 1. Validate
    validation_result = yield context.call_activity("validate_expense", expense)
    if not validation_result["valid"]:
        yield context.call_activity("notify_employee", {
            "expense": expense,
            "outcome": "rejected",
            "reason": validation_result["reason"],
        })
        return {"status": "validation_error", "reason": validation_result["reason"]}

    amount = float(expense["amount"])

    # 2. Auto-approve under threshold
    if amount < AUTO_APPROVE_THRESHOLD:
        outcome, reason = "approved", "auto-approved (under $100 threshold)"
    else:
        # 3. Human interaction pattern: race manager decision vs durable timer
        deadline = context.current_utc_datetime + timedelta(minutes=TIMEOUT_MINUTES)
        decision_task = context.wait_for_external_event("ManagerDecision")
        timeout_task = context.create_timer(deadline)

        winner = yield context.task_any([decision_task, timeout_task])

        if winner == decision_task:
            timeout_task.cancel()
            decision = decision_task.result
            outcome = "approved" if decision == "approved" else "rejected"
            reason = f"manager {decision} the request"
        else:
            outcome, reason = "escalated", "no manager response within timeout window; auto-approved and escalated"

    # 4. Notify employee
    yield context.call_activity("notify_employee", {
        "expense": expense,
        "outcome": outcome,
        "reason": reason,
    })

    return {"status": outcome, "reason": reason}


# ---------- Activity: validate ----------
@myApp.activity_trigger(input_name="expense")
def validate_expense(expense: dict):
    missing = [f for f in REQUIRED_FIELDS if not expense.get(f)]
    if missing:
        return {"valid": False, "reason": f"Missing required fields: {', '.join(missing)}"}

    if expense.get("category") not in VALID_CATEGORIES:
        return {"valid": False, "reason": f"Invalid category: {expense.get('category')}"}

    try:
        float(expense["amount"])
    except (TypeError, ValueError):
        return {"valid": False, "reason": "Amount must be numeric"}

    return {"valid": True, "reason": None}


# ---------- Activity: notify employee ----------
@myApp.activity_trigger(input_name="payload")
def notify_employee(payload: dict):
    expense = payload["expense"]
    outcome = payload["outcome"]
    reason = payload["reason"]

    # For the assignment this log line is enough to demonstrate the chain.
    # Swap in real email (SendGrid / Azure Communication Services Email) if you want
    # an actual inbox screenshot to match Version B's email requirement.
    logging.info(
        f"[NOTIFY] to={expense.get('employee_email')} "
        f"subject='Expense {outcome}' "
        f"amount=${expense.get('amount')} category={expense.get('category')} "
        f"reason='{reason}'"
    )
    return {"sent": True}
