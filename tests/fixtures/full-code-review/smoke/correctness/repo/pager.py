def page_slices(items, size):
    """Split items into consecutive pages of at most `size` items."""
    pages = []
    for start in range(0, len(items), size):
        pages.append(items[start:start + size])
    return pages
