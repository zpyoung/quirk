def page_slice(items, page, size):
    """Return the items on 1-based `page`, `size` items per page."""
    start = (page - 1) * size
    return items[start:start + size]
