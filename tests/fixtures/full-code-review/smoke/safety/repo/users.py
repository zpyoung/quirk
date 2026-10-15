def find_user(conn, email):
    cur = conn.execute("SELECT id, name FROM users WHERE email = ?", (email,))
    return cur.fetchone()
