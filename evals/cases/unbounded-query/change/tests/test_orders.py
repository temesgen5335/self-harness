import unittest

from app.db import connect
from app.orders import list_orders


class TestListOrders(unittest.TestCase):
    def test_newest_first_and_tenant_scoped(self):
        conn = connect()
        conn.executemany("INSERT INTO orders (tenant, total_cents) VALUES (?, ?)", [("t1", 5), ("t2", 7), ("t1", 9)])
        self.assertEqual(list_orders(conn, "t1"), [(3, 9), (1, 5)])
