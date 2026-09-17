import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from document_reader import read_document
from proposal_parser import parse_proposal


class Phase1ParserTests(unittest.TestCase):
    def assert_case(self, filename, expected):
        path = Path(filename)
        if not path.exists():
            self.skipTest(f"Test proposal not found: {path}")
        result = parse_proposal(read_document(path))
        data = result["data"]
        for field, value in expected.items():
            self.assertEqual(data.get(field), value, field)
        self.assertFalse(
            [warning for warning in result["warnings"]
             if "Required field not found" in warning],
            result["warnings"],
        )

    def test_longitude_v41(self):
        self.assert_case(
            "CTI_Proposal_Intake_Template.docx",
            {
                "engineering_hours": 1480.0,
                "five_year_npv": 1530000.0,
                "aog_events": 2.0,
                "delivery_delays": 6.0,
                "affected_fleet_pct": 10.6,
                "functions_involved": 7.0,
                "need_by": "2027-03-31",
                "target_date": "2027-03-15",
            },
        )

    def test_cj4_v41(self):
        self.assert_case(
            "CTI_Proposal_Intake_Template test2.docx",
            {
                "engineering_hours": 240.0,
                "five_year_npv": 11000.0,
                "aog_events": 0.0,
                "delivery_delays": 0.0,
                "affected_fleet_pct": 1.0,
                "functions_involved": 4.0,
                "need_by": "2027-09-30",
                "target_date": "2027-09-15",
            },
        )


if __name__ == "__main__":
    unittest.main()
