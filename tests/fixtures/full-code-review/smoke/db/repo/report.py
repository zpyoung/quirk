def order_totals(conn, customer_ids):
    rows = conn.execute(
        "SELECT customer_id, SUM(amount) FROM orders WHERE customer_id IN (%s) GROUP BY customer_id"
        % ",".join("?" * len(customer_ids)), customer_ids)
    return dict(rows.fetchall())
