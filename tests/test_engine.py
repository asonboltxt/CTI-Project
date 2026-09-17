import unittest
from qualification import calculate_qualification
from scoring import calculate_all_scores
from confidence import calculate_confidence
from samples import SAMPLE_CASES

class EngineTests(unittest.TestCase):
    def test_longitude(self):
        data = SAMPLE_CASES["longitude"]
        self.assertEqual(calculate_qualification(data)["code"], "D")
        self.assertGreater(calculate_all_scores(data)["ops"], 50)
        self.assertEqual(calculate_confidence(data)["score"], 100)

    def test_cj4(self):
        data = SAMPLE_CASES["cj4"]
        self.assertEqual(calculate_qualification(data)["code"], "D")
        self.assertLess(calculate_all_scores(data)["ops"], calculate_all_scores(SAMPLE_CASES["longitude"])["ops"])

    def test_m1(self):
        data = {"engineering_hours": 10, "engineering_threshold": 160, "cos_score": 12}
        self.assertEqual(calculate_qualification(data)["code"], "M1")

    def test_exclusion(self):
        data = {"engineering_hours": 1000, "engineering_threshold": 160, "unit_specific": True}
        self.assertEqual(calculate_qualification(data)["code"], "NOT CTI")

if __name__ == "__main__":
    unittest.main()
