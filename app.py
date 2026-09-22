from pathlib import Path
from uuid import uuid4
import getpass

import click

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
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required

from config import (
    ALLOWED_EXTENSIONS,
    CONFIGURATIONS,
    MAX_UPLOAD_BYTES,
    apply_environment_overrides,
    configuration_name,
)
from config import DEFAULT_LIFECYCLE_PHASE
from auth import auth_bp, login_manager, manager_required, assert_can_manage_program
from confidence import calculate_confidence
from document_reader import DocumentReadError, read_document
from integration import save_calculation
from phase2 import register_phase2
from phase2.database import (
    assign_user_programs,
    create_draft,
    create_user,
    delete_draft,
    fetch_draft,
    fetch_user_by_email,
    init_db,
    save_draft,
)
from proposal_parser import parse_proposal
from qualification import calculate_qualification
from scoring import calculate_all_scores, priority_tier
from services.intake import (
    BOOL_FIELDS,
    NUM_FIELDS,
    WIZARD_STEPS,
    form_data,
    new_draft_data,
    normalize_step_data,
    parsed_draft_data,
    parsed_extraction,
    raw_form_data,
    submitted_extraction,
    validate_data,
    wizard_context,
)

BASE_DIR = Path(__file__).resolve().parent
main_bp = Blueprint("main", __name__)

def render_result(data, extraction=None, source_file=None):
    if current_user.is_authenticated:
        assert_can_manage_program(data.get("program"))
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
@manager_required
def new_cti():
    if request.method == "POST":
        data, errors = form_data(request.form)
        if errors:
            return render_template("intake.html", data=data, errors=errors), 400
        return render_result(data)

    return redirect(url_for("main.cti_new"))


@main_bp.get("/cti/new")
@manager_required
def cti_new():
    token = uuid4().hex
    create_draft(token, new_draft_data())
    return redirect(url_for("main.cti_step", token=token, step=1))


@main_bp.route("/cti/<token>/step/<int:step>", methods=["GET", "POST"])
@manager_required
def cti_step(token, step):
    draft = fetch_draft(token)
    if not draft or step not in WIZARD_STEPS:
        abort(404)
    if request.method == "POST":
        raw = raw_form_data(request.form, WIZARD_STEPS[step])
        normalized, errors = normalize_step_data(raw, step)
        if errors:
            draft["data"].update(raw)
            save_draft(token, draft["data"], step, warnings=draft["warnings"], extraction=draft["extraction"])
            return render_template("wizard.html", **wizard_context(draft, step, errors)), 400
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
    return render_template("wizard.html", **wizard_context(draft, step))


@main_bp.post("/cti/<token>/save")
@manager_required
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
@manager_required
def cti_resume(token):
    draft = fetch_draft(token)
    if not draft:
        abort(404)
    return redirect(url_for("main.cti_step", token=token, step=draft["current_step"]))


@main_bp.post("/cti/<token>/submit")
@manager_required
def cti_submit(token):
    draft = fetch_draft(token)
    if not draft:
        abort(404)
    raw = dict(draft["data"])
    normalized, errors = validate_data(raw, {"title"})
    if errors:
        return render_template("wizard.html", **wizard_context(draft, 4, errors)), 400
    for key in BOOL_FIELDS:
        normalized[key] = normalized.get(key) == "yes" if isinstance(normalized.get(key), str) else bool(normalized.get(key))
    result = render_result(
        normalized,
        extraction=submitted_extraction(draft),
        source_file=draft.get("source_file"),
    )
    delete_draft(token)
    return result


@main_bp.route("/upload", methods=["GET", "POST"])
@manager_required
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
        parsed_draft_data(parsed),
        current_step=1,
        source={
            "file_name": stored_name,
            "source_type": parsed.get("source_type", ""),
            "template_version": parsed.get("template_version", ""),
        },
        warnings=parsed.get("warnings", []),
        extraction=parsed_extraction(parsed),
    )
    return redirect(url_for("main.cti_step", token=token, step=1))


@main_bp.route("/calculate-upload", methods=["POST"])
@manager_required
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
@login_required
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
    login_manager.init_app(application)
    application.register_blueprint(auth_bp)
    application.register_blueprint(main_bp)
    register_phase2(application)

    @application.cli.command("create-user")
    @click.option("--email", prompt=True)
    @click.option("--display-name", prompt=True)
    @click.option(
        "--role",
        type=click.Choice(["admin", "program_manager", "viewer"]),
        prompt=True,
    )
    @click.option("--program", "programs", multiple=True)
    def create_user_command(email, display_name, role, programs):
        """Create a CTI user and optionally assign managed programs."""
        if fetch_user_by_email(email):
            raise click.ClickException("A user with that email already exists.")
        password = getpass.getpass("Password: ")
        if not password:
            raise click.ClickException("Password cannot be empty.")
        user_id = create_user(
            email,
            display_name,
            generate_password_hash(password),
            role,
        )
        assign_user_programs(user_id, programs)
        click.echo(f"Created {role} user {email}.")
    return application


app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
