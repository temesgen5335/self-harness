import unittest

from app.stock import Stock


class TestStock(unittest.TestCase):
    def test_reserve_takes_units(self):
        s = Stock(3)
        self.assertTrue(s.reserve(2))
        self.assertEqual(s.units, 1)

    def test_reserve_refuses_when_short(self):
        self.assertFalse(Stock(1).reserve(2))
