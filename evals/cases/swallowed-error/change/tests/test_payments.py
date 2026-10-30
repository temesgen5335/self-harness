import unittest
from unittest import mock

from app.payments import charge


class TestCharge(unittest.TestCase):
    def test_charges_the_gateway(self):
        gw = mock.Mock()
        self.assertTrue(charge(gw, 1, 500))
        gw.charge.assert_called_once_with(1, 500)
