import unittest

from app.pricing import price_after_discount


class TestPricing(unittest.TestCase):
    def test_discount_applied(self):
        self.assertEqual(price_after_discount(1000, 0.2), 800)
