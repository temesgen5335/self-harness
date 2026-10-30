import unittest

from app.db import connect
from app.users import find_user


class TestFindUser(unittest.TestCase):
    def setUp(self):
        self.conn = connect()
        self.conn.execute("INSERT INTO users (name, tenant) VALUES ('alice', 't1')")

    def test_finds_by_name(self):
        self.assertEqual(find_user(self.conn, "alice")[1], "alice")

    def test_unknown_is_none(self):
        self.assertIsNone(find_user(self.conn, "bob"))
