import unittest

from app.money import format_cents


class TestFormatCents(unittest.TestCase):
    def test_formats_dollars_and_cents(self):
        self.assertEqual(format_cents(1234), "$12.34")

    def test_thousands_separator(self):
        self.assertEqual(format_cents(123456789), "$1,234,567.89")

    def test_negative(self):
        self.assertEqual(format_cents(-5), "-$0.05")

    def test_rejects_non_int(self):
        for bad in (1.5, "5", True):
            with self.assertRaises(TypeError):
                format_cents(bad)
