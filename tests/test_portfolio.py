import unittest

from phase2.analytics import portfolio_metrics


class PortfolioMetricTests(unittest.TestCase):
    def test_missing_dates_counts_projects_missing_either_date(self):
        metrics = portfolio_metrics(
            [
                {"qualification": "D", "need_by": None, "target_date": "2027-01-01"},
                {"qualification": "D", "need_by": "2027-01-01", "target_date": None},
                {"qualification": "D", "need_by": "2027-01-01", "target_date": "2027-02-01"},
            ]
        )
        self.assertEqual(metrics["missing_need_by"], 1)
        self.assertEqual(metrics["missing_target"], 1)
        self.assertEqual(metrics["missing_dates"], 2)


if __name__ == "__main__":
    unittest.main()