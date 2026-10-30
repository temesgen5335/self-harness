def list_orders(conn, tenant):
    """Orders for the tenant's orders page, newest first."""
    return conn.execute(
        "SELECT id, total_cents FROM orders WHERE tenant = ? ORDER BY id DESC", (tenant,)
    ).fetchall()
