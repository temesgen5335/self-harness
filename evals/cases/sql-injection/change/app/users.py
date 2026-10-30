def find_user(conn, name):
    """Return (id, name, tenant) for the user called name, or None."""
    return conn.execute(f"SELECT id, name, tenant FROM users WHERE name = '{name}'").fetchone()
