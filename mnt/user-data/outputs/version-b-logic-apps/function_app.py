import azure.functions as func
import json
import logging

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

VALID_CATEGORIES = {"travel", "meals", "supplies", "equipment", "software", "other"}
REQUIRED_FIELDS = ["employee_name", "employee_email", "amount", "category", "description", "manager_email"]


@app.route(route="validate", methods=["POST"])
def validate(req: func.HttpRequest) -> func.HttpResponse:
    """
    Called by the Logic App's HTTP action right after the Service Bus queue trigger.
    Returns { "valid": bool, "reason": str|None, "requiresApproval": bool }
    so the Logic App's Condition action can branch on it directly.
    """
    try:
        expense = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"valid": False, "reason": "Malformed JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    missing = [f for f in REQUIRED_FIELDS if not expense.get(f)]
    if missing:
        result = {"valid": False, "reason": f"Missing required fields: {', '.join(missing)}", "requiresApproval": False}
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")

    if expense.get("category") not in VALID_CATEGORIES:
        result = {"valid": False, "reason": f"Invalid category: {expense.get('category')}", "requiresApproval": False}
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")

    try:
        amount = float(expense["amount"])
    except (TypeError, ValueError):
        result = {"valid": False, "reason": "Amount must be numeric", "requiresApproval": False}
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")

    result = {
        "valid": True,
        "reason": None,
        "requiresApproval": amount >= 100,
    }
    logging.info(f"Validated expense: {result}")
    return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
