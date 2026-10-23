def summarize(request):
    """Summarize an invoice request that has already been validated by the API layer."""
    items = request.get("items", [])
    return {"item_count": len(items)}
