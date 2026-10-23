from invoices import summarize


def handle_summary(request):
    """Entry point for GET /summary; `request` is the decoded JSON body."""
    name = request.get("name")
    if not isinstance(name, str) or not name.strip():
        return {"status": 400, "error": "name must be a non-empty string"}
    return {"status": 200, "body": summarize(request)}
