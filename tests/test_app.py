import tempfile
import unittest
import sqlite3
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import app, create_app
from phase2.database import assign_user_programs, create_user
from phase2.database import (
    SCHEMA,
    fetch_draft,
    fetch_project,
    fetch_projects,
    fetch_project_departments,
    init_db,
    save_project,
    update_project,
)
from werkzeug.security import generate_password_hash


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app_context = app.app_context()
        self.app_context.push()
        app.config.update(
            TESTING=True,
            CTI_DATABASE=str(Path(self.temp_dir.name) / "cti.db"),
        )
        init_db(app)
        self.client = app.test_client()
        create_user(
            "director@example.com",
            "Director",
            generate_password_hash("director-password"),
            "admin",
        )
        self.login("director@example.com", "director-password")

    def tearDown(self):
        self.app_context.pop()
        self.temp_dir.cleanup()

    def login(self, email, password):
        response = self.client.post(
            "/login",
            data={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 302)

    def create_user(self, email, role, programs=()):
        user_id = create_user(
            email,
            email.split("@")[0].title(),
            generate_password_hash("password"),
            role,
        )
        assign_user_programs(user_id, programs)
        return user_id

    def test_application_factory_registers_core_routes_and_safe_defaults(self):
        factory_app = create_app(
            "testing",
            {
                "CTI_DATABASE": str(Path(self.temp_dir.name) / "factory.db"),
            },
        )
        self.assertTrue(factory_app.config["TESTING"])
        self.assertFalse(factory_app.config["DEBUG"])
        self.assertTrue(factory_app.secret_key)
        client = factory_app.test_client()
        self.assertEqual(client.get("/health").status_code, 200)
        with factory_app.app_context():
            create_user(
                "factory@example.com",
                "Factory Viewer",
                generate_password_hash("factory-password"),
                "viewer",
            )
        self.assertEqual(
            client.post(
                "/login",
                data={"email": "factory@example.com", "password": "factory-password"},
            ).status_code,
            302,
        )
        self.assertEqual(client.get("/dashboard").status_code, 200)

    def test_production_factory_requires_secret_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                create_app(
                    "production",
                    {
                        "CTI_DATABASE": str(Path(self.temp_dir.name) / "production.db"),
                    },
                )

    def draft_token(self):
        response = self.client.get("/cti/new")
        self.assertEqual(response.status_code, 302)
        return response.location.split("/")[2]

    def test_invalid_numeric_input_is_explicit_and_not_saved_as_zero(self):
        response = self.client.post(
            "/new-cti",
            data={"engineering_hours": "not-a-number"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Enter a valid number.", response.data)
        self.assertEqual(fetch_projects(), [])

    def test_wizard_saves_and_resumes_draft(self):
        token = self.draft_token()
        draft = fetch_draft(token)
        self.assertEqual(draft["data"]["lifecycle_phase"], "Phase 3")
        response = self.client.post(
            f"/cti/{token}/step/1",
            data={"title": "Resume me", "program": "Program A"},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            f"/cti/{token}/save",
            data={"engineering_hours": "42"},
        )
        self.assertEqual(response.status_code, 302)
        draft = fetch_draft(token)
        self.assertEqual(draft["data"]["engineering_hours"], "42")
        self.assertEqual(draft["data"]["title"], "Resume me")

        response = self.client.get(f"/cti/{token}/resume")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/step/2"))

    def test_new_intake_defaults_saved_project_to_phase_three(self):
        token = self.draft_token()
        self.client.post(
            f"/cti/{token}/step/1",
            data={"title": "Default Phase CTI"},
        )
        self.client.post(f"/cti/{token}/step/2", data={})
        self.client.post(f"/cti/{token}/step/3", data={})
        response = self.client.post(f"/cti/{token}/step/4", data={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(fetch_projects()[0]["lifecycle_phase"], "Phase 3")

    def test_project_detail_uses_only_lifecycle_phase(self):
        project_id = save_project({
            "title": "Lifecycle-only CTI",
            "phase": "Legacy content phase",
            "lifecycle_phase": "Phase 3",
        })
        response = self.client.get(f"/project/{project_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Lifecycle phase", response.data)
        self.assertNotIn(b">Legacy content phase<", response.data)

    def test_wizard_rejects_range_error_and_final_submission_saves_project(self):
        token = self.draft_token()
        self.client.post(
            f"/cti/{token}/step/1",
            data={"title": "Complete CTI"},
        )
        response = self.client.post(
            f"/cti/{token}/step/2",
            data={"engineering_hours": "10", "target_date": "2027-02-01",
                   "need_by": "2027-01-01"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"on or before", response.data)

        self.assertEqual(
            self.client.post(
                f"/cti/{token}/step/2",
                data={"engineering_hours": "10"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                f"/cti/{token}/step/3",
                data={"affected_fleet_pct": "10"},
            ).status_code,
            302,
        )
        response = self.client.post(
            f"/cti/{token}/step/4",
            data={"ready_owner": "yes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(fetch_projects()), 1)
        self.assertIsNone(fetch_draft(token))

    def test_dashboard_lists_attention_reasons(self):
        save_project(
            {"title": "Needs review", "program": "Program A"},
            qualification={"code": "D"},
            scoring={"ops": 25, "factors": {}},
            confidence={"score": 50},
        )
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Needs attention", response.data)
        self.assertIn(b"Missing need-by date", response.data)
        self.assertIn(b"Confidence below 70", response.data)

    def test_dashboard_opens_cti_project_record(self):
        project_id = save_project({"title": "Dashboard CTI", "program": "Program A"})
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f'href="/project/{project_id}"'.encode(),
            response.data,
        )
        project_response = self.client.get(f"/project/{project_id}")
        self.assertEqual(project_response.status_code, 200)
        self.assertIn(b"Dashboard CTI", project_response.data)

    def test_submitted_departments_are_available_on_resources_page(self):
        token = self.draft_token()
        self.client.post(
            f"/cti/{token}/step/1",
            data={"title": "Resource CTI", "program": "Program A"},
        )
        self.client.post(
            f"/cti/{token}/step/2",
            data={
                "engineering_hours": "200",
                "departments": ["Avionics", "Software"],
            },
        )
        self.client.post(f"/cti/{token}/step/3", data={})
        self.client.post(f"/cti/{token}/step/4", data={})

        resources = self.client.get("/resources")
        self.assertEqual(resources.status_code, 200)
        self.assertIn(b"Avionics", resources.data)
        self.assertIn(b"Software", resources.data)
        filtered = self.client.get("/resources?department=Avionics")
        self.assertIn(b"Resource CTI", filtered.data)

    def test_duplicate_submission_adds_new_departments(self):
        token = self.draft_token()
        self.client.post(f"/cti/{token}/step/1", data={"title": "Duplicate CTI"})
        self.client.post(
            f"/cti/{token}/step/2",
            data={"engineering_hours": "200", "departments": ["Safety"]},
        )
        self.client.post(f"/cti/{token}/step/3", data={})
        self.client.post(f"/cti/{token}/step/4", data={})

        duplicate = self.draft_token()
        self.client.post(f"/cti/{duplicate}/step/1", data={"title": "Duplicate CTI"})
        self.client.post(
            f"/cti/{duplicate}/step/2",
            data={"engineering_hours": "200", "departments": ["Software"]},
        )
        self.client.post(f"/cti/{duplicate}/step/3", data={})
        self.client.post(f"/cti/{duplicate}/step/4", data={})

        self.assertIn(b"Software", self.client.get("/resources").data)

    def test_lifecycle_phase_is_saved_filtered_counted_and_updated(self):
        token = self.draft_token()
        self.client.post(
            f"/cti/{token}/step/1",
            data={"title": "Lifecycle CTI", "program": "Program A"},
        )
        self.client.post(
            f"/cti/{token}/step/2",
            data={"engineering_hours": "200"},
        )
        self.client.post(f"/cti/{token}/step/3", data={})
        response = self.client.post(
            f"/cti/{token}/step/4",
            data={"lifecycle_phase": "Phase 3"},
        )
        self.assertEqual(response.status_code, 200)
        project = fetch_projects()[0]
        self.assertEqual(project["lifecycle_phase"], "Phase 3")

        dashboard = self.client.get("/dashboard?lifecycle_phase=Phase%203")
        self.assertIn(b"Lifecycle CTI", dashboard.data)
        self.assertIn(b"Phase 3", dashboard.data)
        self.assertIn(b">1</strong>", dashboard.data)

        response = self.client.post(
            f"/project/{project['id']}/lifecycle-phase",
            data={"lifecycle_phase": "Phase 6"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(fetch_project(project["id"])["lifecycle_phase"], "Phase 6")

    def test_invalid_lifecycle_phase_is_rejected(self):
        save_project({"title": "Phase validation"})
        project = fetch_projects()[0]
        response = self.client.post(
            f"/project/{project['id']}/lifecycle-phase",
            data={"lifecycle_phase": "Phase 99"},
        )
        self.assertEqual(response.status_code, 400)

    def test_program_manager_cannot_change_another_programs_project(self):
        self.create_user("manager-a@example.com", "program_manager", ["Program A"])
        self.create_user("manager-b@example.com", "program_manager", ["Program B"])
        project_id = save_project({"title": "Program A CTI", "program": "Program A"})

        self.client.post("/logout")
        self.login("manager-b@example.com", "password")
        response = self.client.post(
            f"/project/{project_id}/lifecycle-phase",
            data={"lifecycle_phase": "Phase 6"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(fetch_project(project_id)["lifecycle_phase"], "Phase 3")

    def test_program_manager_can_change_only_assigned_program(self):
        self.create_user("manager-a@example.com", "program_manager", ["Program A"])
        project_id = save_project({"title": "Program A CTI", "program": "Program A"})

        self.client.post("/logout")
        self.login("manager-a@example.com", "password")
        response = self.client.post(
            f"/project/{project_id}/lifecycle-phase",
            data={"lifecycle_phase": "Phase 6"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(fetch_project(project_id)["lifecycle_phase"], "Phase 6")

    def test_viewer_cannot_create_or_delete_ctis(self):
        viewer_id = self.create_user("viewer@example.com", "viewer")
        project_id = save_project({"title": "Protected CTI", "program": "Program A"})

        self.client.post("/logout")
        self.login("viewer@example.com", "password")
        self.assertEqual(self.client.get("/cti/new").status_code, 403)
        self.assertEqual(self.client.post(f"/project/{project_id}/delete").status_code, 403)
        self.assertIsNotNone(fetch_project(project_id))

    def test_anonymous_users_can_view_portfolio_without_mutation_access(self):
        self.client.post("/logout")
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        self.assertEqual(self.client.get("/models").status_code, 200)
        self.assertEqual(self.client.get("/resources").status_code, 200)
        self.assertEqual(self.client.get("/cti/new").status_code, 302)

    def test_project_edit_is_unavailable(self):
        project_id = save_project({"title": "Immutable CTI"})
        response = self.client.get(f"/project/{project_id}/edit")
        self.assertEqual(response.status_code, 404)

    def test_project_delete_removes_related_history_and_departments(self):
        project_id = save_project(
            {"title": "Delete me", "departments": ["Avionics", "Quality"]}
        )
        self.client.post(
            f"/project/{project_id}/lifecycle-phase",
            data={"lifecycle_phase": "Phase 6"},
        )
        self.assertEqual(fetch_project_departments(project_id), ["Avionics", "Quality"])

        response = self.client.post(f"/project/{project_id}/delete")

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(fetch_project(project_id))
        self.assertEqual(fetch_project_departments(project_id), [])

    def test_project_update_persists_scope_and_source_metadata(self):
        project_id = save_project(
            {"title": "Metadata CTI"},
            source={"file_name": "old.docx", "source_type": "docx"},
            warnings=["old warning"],
            extraction={"fields": {"title": {"confidence": 80}}},
        )
        self.assertTrue(
            update_project(
                project_id,
                {"title": "Metadata CTI", "scope_change": "Updated scope"},
                {"code": "D"},
                {"ops": 42, "factors": {}},
                {"score": 75},
                source={"file_name": "new.pdf", "source_type": "pdf", "template_version": "v2"},
                warnings=["new warning"],
                extraction={"fields": {"title": {"confidence": 99}}},
            )
        )
        project = fetch_project(project_id)
        self.assertEqual(project["scope_change"], "Updated scope")
        self.assertEqual(project["source_file"], "new.pdf")
        self.assertEqual(project["source_type"], "pdf")
        self.assertEqual(project["template_version"], "v2")
        self.assertEqual(project["warnings_json"], '["new warning"]')

    def test_existing_database_is_migrated_to_lifecycle_phase(self):
        path = Path(self.temp_dir.name) / "legacy.db"
        legacy_schema = SCHEMA.replace(
            "    lifecycle_phase TEXT NOT NULL DEFAULT 'Phase 1',\n",
            "",
        )
        conn = sqlite3.connect(path)
        try:
            conn.executescript(legacy_schema)
            conn.execute("INSERT INTO cti_projects (title) VALUES (?)", ("Legacy CTI",))
            conn.commit()
        finally:
            conn.close()
        app.config["CTI_DATABASE"] = str(path)
        init_db(app)
        project = fetch_projects()[0]
        self.assertEqual(project["lifecycle_phase"], "Phase 1")

    @patch.object(app_module, "read_document", return_value="proposal text")
    @patch.object(
        app_module,
        "parse_proposal",
        return_value={
            "data": {"title": "Uploaded CTI", "engineering_hours": 12},
            "warnings": ["Check extracted owner"],
            "fields": {
                "title": {
                    "raw": "Uploaded CTI",
                    "normalized": "Uploaded CTI",
                    "location": "table 1, row 1",
                    "source": "table",
                    "confidence": 95,
                    "status": "extracted",
                    "candidates": [],
                }
            },
            "review": {"uncertain": [], "inferred": [], "missing": [], "conflicts": []},
            "source_type": "docx",
            "template_version": "v4.1",
        },
    )
    def test_upload_enters_wizard_with_extracted_draft(
        self, parse_proposal_mock, read_document_mock
    ):
        response = self.client.post(
            "/upload",
            data={"proposal": (BytesIO(b"document"), "proposal.docx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        token = response.location.split("/")[2]
        draft = fetch_draft(token)
        self.assertEqual(draft["data"]["title"], "Uploaded CTI")
        self.assertEqual(draft["warnings"], ["Check extracted owner"])
        self.assertEqual(draft["extraction"]["fields"]["title"]["confidence"], 95)
        self.assertEqual(draft["source_type"], "docx")
        wizard = self.client.get(response.location)
        self.assertIn(b"Uploaded CTI", wizard.data)
        self.assertIn(b'Imported from', wizard.data)
        step_two = self.client.get(f"/cti/{token}/step/2")
        self.assertIn(b'name="engineering_hours"', step_two.data)
        self.assertIn(b'type="number"', step_two.data)

    @patch.object(app_module, "read_document", return_value="proposal text")
    @patch.object(
        app_module,
        "parse_proposal",
        return_value={
            "data": {
                "title": "Full Intake",
                "program": "Citation Latitude",
                "requesting_organization": "Safety / Avionics",
                "originator": "Test Originator",
                "owner": "Test Owner",
                "engineering_hours": 2180,
                "affected_aircraft": 9,
                "active_fleet": 210,
            },
            "warnings": [],
            "source_type": "docx",
            "template_version": "V5.0",
        },
    )
    def test_uploaded_fields_are_visible_on_their_wizard_steps(
        self, parse_proposal_mock, read_document_mock
    ):
        response = self.client.post(
            "/upload",
            data={"proposal": (BytesIO(b"document"), "proposal.docx")},
            content_type="multipart/form-data",
        )
        token = response.location.split("/")[2]
        step_one = self.client.get(response.location)
        self.assertIn(b"Safety / Avionics", step_one.data)
        self.assertIn(b"Test Originator", step_one.data)
        self.assertIn(b"Test Owner", step_one.data)
        step_two = self.client.get(f"/cti/{token}/step/2")
        self.assertIn(b'value="2180"', step_two.data)
        self.assertIn(b'value="9"', step_two.data)
        self.assertIn(b'value="210"', step_two.data)

    @patch.object(app_module, "read_document", return_value="proposal text")
    @patch.object(
        app_module,
        "parse_proposal",
        return_value={
            "data": {
                "title": "Ranked Upload",
                "program": "Program A",
                "engineering_hours": 200,
                "need_by": "2027-01-01",
                "target_date": "2026-12-01",
                "affected_fleet_pct": 50,
                "five_year_npv": 500000,
                "functions_involved": 8,
                "model_families": 4,
                "lifecycle_areas": 5,
                "evidence_count": 1,
                "milestone_count": 1,
            },
            "warnings": [],
            "source_type": "pdf",
            "template_version": "CTI proposal",
        },
    )
    def test_uploaded_cti_is_scored_and_ranked(
        self, parse_proposal_mock, read_document_mock
    ):
        response = self.client.post(
            "/upload",
            data={"proposal": (BytesIO(b"document"), "proposal.pdf")},
            content_type="multipart/form-data",
        )
        token = response.location.split("/")[2]
        self.client.post(
            f"/cti/{token}/step/1",
            data={"title": "Ranked Upload", "program": "Program A"},
        )
        self.client.post(
            f"/cti/{token}/step/2",
            data={
                "engineering_hours": "200",
                "need_by": "2027-01-01",
                "target_date": "2026-12-01",
                "functions_involved": "8",
                "model_families": "4",
                "lifecycle_areas": "5",
                "evidence_count": "1",
                "milestone_count": "1",
            },
        )
        self.client.post(
            f"/cti/{token}/step/3",
            data={"affected_fleet_pct": "50", "five_year_npv": "500000"},
        )
        result = self.client.post(
            f"/cti/{token}/step/4",
            data={
                "ready_owner": "yes",
                "ready_scope": "yes",
                "ready_business_case": "yes",
                "ready_estimate": "yes",
                "ready_functions": "yes",
                "ready_dates": "yes",
                "ready_milestones": "yes",
                "ready_evidence": "yes",
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Objective score breakdown", result.data)
        project = fetch_projects()[0]
        self.assertGreater(project["ops"], 0)
        self.assertEqual(project["source_type"], "pdf")
        dashboard = self.client.get("/dashboard")
        self.assertIn(b"Ranked Upload", dashboard.data)


if __name__ == "__main__":
    unittest.main()
