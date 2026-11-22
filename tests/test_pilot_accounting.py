import unittest

from scripts.evaluate_enterprise_pilot import summarize_costs


class PilotAccountingTest(unittest.TestCase):
    def test_cost_increase_includes_rollout(self):
        costs = dict(manual_labor=100, manual_other=0, assisted_labor=50, model=20,
                     infrastructure=10, rollout_allocation=30, assisted_other=0)
        result = summarize_costs([{"case_id": "sample"}], {"sample": costs})
        self.assertEqual(result["observed_unverified_cost_change_pct"], -10)
        self.assertEqual(result["difference_fen"], -10)

    def test_missing_pair_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize_costs([{"case_id": "sample"}], {})
