import unittest

from app.db import connect


class TestDb(unittest.TestCase):
    def test_schema(self):
        tables = {r[0] for r in connect().execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertEqual(tables, {"users", "orders"})
