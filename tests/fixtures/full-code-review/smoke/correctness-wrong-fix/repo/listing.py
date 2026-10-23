from pager import page_slice


def render_page(items, page, size):
    rows = page_slice(items, page, size)
    return "\n".join(str(row) for row in rows)
