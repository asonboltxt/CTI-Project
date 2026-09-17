import unittest
from pathlib import Path
from document_reader import read_document
from proposal_parser import parse_proposal

class ParserTests(unittest.TestCase):
    def test_classification_and_scope_use_structured_evidence(self):
        extracted = {
            "file_type": "docx",
            "text": (
                "Requested Classification Safety / Regulatory "
                "A safety requirement applies. "
                "Scope change: replace the actuator and update the maintenance instructions. "
                "Business Case: reduce repeat removals."
            ),
            "tables": [
                {
                    "table_index": 0,
                    "rows": [
                        {"row_index": 0, "cells": ["CTI Title", "Actuator alert"]},
                        {"row_index": 1, "cells": ["Engineering Hours", "200"]},
                        {"row_index": 2, "cells": ["Requested Classification", "☒ Safety / Regulatory ☐ Discretionary"]},
                        {"row_index": 3, "cells": ["In Scope", "Replace actuator and update maintenance instructions"]},
                        {"row_index": 4, "cells": ["Business Case", "Reduce repeat removals"]},
                    ],
                }
            ],
            "warnings": [],
        }
        result = parse_proposal(extracted)
        self.assertEqual(result["classification"], "M1")
        self.assertTrue(result["data"]["regulatory"])
        self.assertIn("Replace actuator", result["data"]["scope_change"])
        self.assertEqual(result["data"]["business_case"], "Reduce repeat removals")

        extracted["text"] = "Discretionary obsolescence case with supplier end-of-production and delivery disruption."
        extracted["tables"][0]["rows"][2]["cells"] = [
            "Requested Classification", "☒ Discretionary"
        ]
        result = parse_proposal(extracted)
        self.assertEqual(result["classification"], "M2")

    def test_uploaded_samples_parse_with_field_provenance(self):
        upload_dir = Path(__file__).parents[1] / "uploads"
        samples = [
            path for path in upload_dir.iterdir()
            if path.suffix.lower() in {".docx", ".pdf"} and path.stat().st_size > 100
        ]
        if not samples:
            self.skipTest("No uploaded document samples are available")
        parsed_count = 0
        for path in samples:
            result = parse_proposal(read_document(path))
            self.assertTrue(result["fields"], path.name)
            self.assertIn("review", result, path.name)
            self.assertIn("missing", result["review"], path.name)
            self.assertEqual(
                set(result["review"]["conflicts"]),
                {
                    field for field, metadata in result["fields"].items()
                    if metadata["status"] == "conflict"
                },
                path.name,
            )
            for field, metadata in result["fields"].items():
                self.assertIn(metadata["status"], {"extracted", "fallback", "inferred", "missing", "conflict"})
                self.assertGreaterEqual(metadata["confidence"], 0)
                self.assertLessEqual(metadata["confidence"], 100)
            parsed_count += 1
        self.assertGreater(parsed_count, 0)

    def test_longitude_docx(self):
        p=Path(__file__).parents[2]/"CTI_Proposal_Intake_Template.docx"
        if not p.exists(): self.skipTest("Source proposal not present")
        d=parse_proposal(read_document(p))["data"]
        self.assertEqual(d["engineering_hours"],1480)
        self.assertEqual(d["aog_events"],2)
        self.assertEqual(d["delivery_delays"],6)
        self.assertEqual(d["affected_fleet_pct"],10.6)
        self.assertEqual(d["five_year_npv"],1530000)

    def test_additional_cti_proposal_formats(self):
        examples = [
            (
                "TC-01_Citation Latitude Elevator Trim Runaway Alert Logic.docx",
                {
                    "driver": "Safety",
                    "phase": "Phase 2",
                    "engineering_hours": 2180.0,
                    "functions_involved": 11.0,
                    "cos_score": 14.0,
                    "regulatory": True,
                },
            ),
            (
                "V4.5_Mock_CTI_01_Safety_Flight_Control.docx",
                {
                    "driver": "Safety",
                    "phase": "Phase 2",
                    "engineering_hours": 2860.0,
                    "five_year_npv": 8400000.0,
                    "regulatory": True,
                },
            ),
        ]
        root = Path(
            r"C:\Users\asonbol\OneDrive - Textron\Desktop\CTI PROJ\test docs"
        )
        for filename, expected in examples:
            path = root / filename
            if not path.exists():
                self.skipTest(f"Proposal example not present: {path}")
            result = parse_proposal(read_document(path))
            for field, value in expected.items():
                self.assertEqual(result["data"].get(field), value, field)
            self.assertFalse(
                [warning for warning in result["warnings"]
                 if "Required field not found" in warning],
                result["warnings"],
            )
if __name__=="__main__": unittest.main()
