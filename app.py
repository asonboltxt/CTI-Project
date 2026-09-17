from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_EXTENSIONS,
    CONFIGURATIONS,
    MAX_UPLOAD_BYTES,
    apply_environment_overrides,
    configuration_name,
)
from config import DEFAULT_LIFECYCLE_PHASE, LIFECYCLE_PHASE_LABELS
from confidence import calculate_confidence
from document_reader import DocumentReadError, read_document
from integration import save_calculation
from phase2 import register_phase2
from phase2.database import create_draft, delete_draft, fetch_draft, init_db, save_draft
from proposal_parser import parse_proposal
from qualification import calculate_qualification
from scoring import calculate_all_scores, priority_tier
from validation import raw_form_data, validate_data

BASE_DIR = Path(__file__).resolve().parent
main_bp = Blueprint("main", __name__)

BOOL_FIELDS = {
    "regulatory", "certification", "external_commitment", "slt_mandate",
    "delivery_prevention", "critical_obsolescence", "major_supply_disruption",
    "unit_specific", "fast_engineering", "non_ecr", "cross_functional",
    "customer_commitment", "ready_owner", "ready_scope",
    "ready_business_case", "ready_estimate", "ready_functions", "ready_dates",
    "ready_approach", "ready_funding", "ready_milestones", "ready_evidence",
}

NUM_FIELDS = {
    "implementation_lead_days", "engineering_hours", "engineering_threshold",
    "cos_score", "prevented_deliveries", "aog_events", "delivery_delays",
    "line_interruptions", "repeat_rework", "affected_fleet_pct",
    "customer_escalations", "five_year_npv", "functions_involved",
    "model_families", "lifecycle_areas", "evidence_count", "milestone_count",
    "affected_aircraft", "active_fleet",
}

ALL_FIELDS = [
    "title", "program", "requesting_organization", "originator", "driver",
    "phase", "owner", "problem_statement",
    "business_case", "need_by", "target_date",
] + sorted(NUM_FIELDS) + sorted(BOOL_FIELDS)


def form_data(form):
    raw = raw_form_data(form, ALL_FIELDS + ["departments"])
    data, errors = validate_data(raw)
    if errors:
        return raw, errors
    for key in BOOL_FIELDS:
        data[key] = raw.get(key) == "yes"
    return data, {}


def render_result(data, extraction=None, source_file=None):
    qualification = calculate_qualification(data)
    scoring = calculate_all_scores(data)
    confidence = calculate_confidence(data, extraction)
    tier = priority_tier(scoring["ops"], qualification["code"])

    project_id = save_calculation(
        data=data,
        qualification=qualification,
        scoring=scoring,
        confidence=confidence,
        extraction=extraction,
        source_file=source_file,
    )

    return render_template(
        "results.html",
        data=data,
        qualification=qualification,
        scoring=scoring,
        confidence=confidence,
        tier=tier,
        extraction=extraction,
        project_id=project_id,
    )


@main_bp.route("/")
def home():
    return render_template("home.html")


@main_bp.route("/new-cti", methods=["GET", "POST"])
def new_cti():
    if request.method == "POST":
        data, errors = form_data(request.form)
        if errors:
            return render_template("intake.html", data=data, errors=errors), 400
        return render_result(data)

    return redirect(url_for("main.cti_new"))


WIZARD_STEPS = {
    1: ["title", "program", "requesting_organization", "originator", "driver",
        "phase", "owner", "problem_statement", "scope_change", "business_case"],
    2: ["need_by", "target_date", "implementation_lead_days", "engineering_hours",
        "engineering_threshold", "functions_involved", "model_families",
        "lifecycle_areas", "affected_aircraft", "active_fleet",
        "milestone_count", "evidence_count", "departments"],
    3: ["cos_score", "prevented_deliveries", "aog_events", "delivery_delays",
        "line_interruptions", "repeat_rework", "affected_fleet_pct",
        "customer_escalations", "five_year_npv", "regulatory", "certification",
        "external_commitment", "slt_mandate", "delivery_prevention",
        "critical_obsolescence", "major_supply_disruption", "unit_specific",
        "fast_engineering", "non_ecr", "cross_functional", "customer_commitment"],
    4: ["ready_owner", "ready_scope", "ready_business_case", "ready_estimate",
        "ready_functions", "ready_dates", "ready_approach", "ready_funding",
        "ready_milestones", "ready_evidence"],
}


@main_bp.get("/cti/new")
def cti_new():
    token = uuid4().hex
    create_draft(token, {
        "engineering_threshold": 160,
        "model_families": 1,
        "lifecycle_areas": 1,
        "lifecycle_phase": DEFAULT_LIFECYCLE_PHASE,
    })
    return redirect(url_for("main.cti_step", token=token, step=1))


def _wizard_context(draft, step, errors=None):
    return {
        "draft": draft,
        "data": draft["data"],
        "step": step,
        "steps": WIZARD_STEPS,
        "errors": errors or {},
        "numeric_fields": NUM_FIELDS,
        "date_fields": {"need_by", "target_date"},
        "lifecycle_phase_labels": LIFECYCLE_PHASE_LABELS,
        "extraction": draft.get("extraction", {}),
    }


@main_bp.route("/cti/<token>/step/<int:step>", methods=["GET", "POST"])
def cti_step(token, step):
    draft = fetch_draft(token)
    if not draft or step not in WIZARD_STEPS:
        abort(404)
    if request.method == "POST":
        raw = raw_form_data(request.form, WIZARD_STEPS[step])
        required = {"title"} if step == 1 else set()
        normalized, errors = validate_data(raw, required)
        if errors:
            draft["data"].update(raw)
            save_draft(token, draft["data"], step, warnings=draft["warnings"], extraction=draft["extraction"])
            return render_template("wizard.html", **_wizard_context(draft, step, errors)), 400
        for key in BOOL_FIELDS:
            if key in normalized:
                normalized[key] = normalized[key] == "yes"
        draft["data"].update(normalized)
        save_draft(
            token,
            draft["data"],
            min(step + 1, 4),
            warnings=draft["warnings"],
            extraction=draft["extraction"],
        )
        if step < 4:
            return redirect(url_for("main.cti_step", token=token, step=step + 1))
        return cti_submit(token)
    return render_template("wizard.html", **_wizard_context(draft, step))


@main_bp.post("/cti/<token>/save")
def cti_save(token):
    draft = fetch_draft(token)
    if not draft:
        abort(404)
    raw = raw_form_data(request.form, WIZARD_STEPS.get(draft["current_step"], []))
    draft["data"].update(raw)
    save_draft(
        token,
        draft["data"],
        draft["current_step"],
        warnings=draft["warnings"],
        extraction=draft["extraction"],
    )
    flash("Draft saved. Use the resume link to continue.", "success")
    return redirect(url_for("main.cti_resume", token=token))


@main_bp.get("/cti/<token>/resume")
def cti_resume(token):
    draft = fetch_draft(token)
    if not draft:
        abort(404)
    return redirect(url_for("main.cti_step", token=token, step=draft["current_step"]))


@main_bp.post("/cti/<token>/submit")
def cti_submit(token):
    draft = fetch_draft(token)
    if not draft:
        abort(404)
    raw = dict(draft["data"])
    normalized, errors = validate_data(raw, {"title"})
    if errors:
        return render_template("wizard.html", **_wizard_context(draft, 4, errors)), 400
    for key in BOOL_FIELDS:
        normalized[key] = normalized.get(key) == "yes" if isinstance(normalized.get(key), str) else bool(normalized.get(key))
    result = render_result(
        normalized,
        extraction={
            "warnings": draft.get("warnings", []),
            "fields": draft.get("extraction", {}).get("fields", {}),
            "review": draft.get("extraction", {}).get("review", {}),
            "classification": draft.get("extraction", {}).get("classification", ""),
            "source_type": draft.get("source_type", ""),
            "template_version": draft.get("template_version", ""),
        },
        source_file=draft.get("source_file"),
    )
    delete_draft(token)
    return result


@main_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    uploaded = request.files.get("proposal")
    if not uploaded or not uploaded.filename:
        flash("Choose a DOCX or PDF proposal.", "error")
        return redirect(url_for("main.upload"))

    original_name = secure_filename(uploaded.filename)
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        flash("Only .docx and .pdf files are supported.", "error")
        return redirect(url_for("main.upload"))

    stored_name = f"{uuid4().hex}_{original_name}"
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    path = upload_folder / stored_name
    uploaded.save(path)

    try:
        parsed = parse_proposal(read_document(path))
    except DocumentReadError as exc:
        try:
            path.unlink()
        except OSError:
            pass
        flash(str(exc), "error")
        return redirect(url_for("main.upload"))

    token = uuid4().hex
    create_draft(
        token,
        dict(parsed["data"], lifecycle_phase=DEFAULT_LIFECYCLE_PHASE),
        current_step=1,
        source={
            "file_name": stored_name,
            "source_type": parsed.get("source_type", ""),
            "template_version": parsed.get("template_version", ""),
        },
        warnings=parsed.get("warnings", []),
        extraction={
            "fields": parsed.get("fields", {}),
            "review": parsed.get("review", {}),
            "classification": parsed.get("classification", ""),
            "source_type": parsed.get("source_type", ""),
            "template_version": parsed.get("template_version", ""),
        },
    )
    return redirect(url_for("main.cti_step", token=token, step=1))


@main_bp.route("/calculate-upload", methods=["POST"])
def calculate_upload():
    data, errors = form_data(request.form)
    if errors:
        return render_template(
            "review.html",
            data=data,
            extraction={"warnings": request.form.getlist("extraction_warning")},
            source_file=request.form.get("source_file", ""),
            original_file_name=request.form.get("original_file_name", ""),
            errors=errors,
        ), 400
    warnings = [
        item
        for item in request.form.getlist("extraction_warning")
        if item
    ]

    extraction = {
        "warnings": warnings,
        "source_type": request.form.get("source_type", ""),
        "template_version": request.form.get("template_version", ""),
        "original_file_name": request.form.get("original_file_name", ""),
    }

    return render_result(
        data,
        extraction,
        request.form.get("source_file", ""),
    )


@main_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    safe_name = Path(filename).name
    if safe_name != filename:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], safe_name, as_attachment=False)


@main_bp.route("/health")
def health():
    return {
        "status": "ok",
        "version": "4.8.2",
        "document_intake": True,
        "phase2": True,
    }


def create_app(config_name=None, test_config=None):
    """Create and configure a CTI application instance."""
    selected = config_name or configuration_name()
    config_class = CONFIGURATIONS.get(selected)
    if config_class is None:
        raise RuntimeError(f"Unknown CTI_ENV: {selected}")

    application = Flask(__name__, instance_relative_config=True)
    application.config.from_object(config_class())
    apply_environment_overrides(application.config)
    if test_config:
        application.config.update(test_config)

    upload_folder = Path(application.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    application.config["UPLOAD_FOLDER"] = upload_folder
    application.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    init_db(application)
    application.register_blueprint(main_bp)
    register_phase2(application)
    return application


app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
