import json

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from .analytics import review_reasons
from .database import (
    delete_project,
    fetch_project,
    fetch_projects,
    save_project,
    set_archived,
    projects_by_department,
    fetch_models,
    projects_by_model,
    update_lifecycle_phase,
)
from config import LIFECYCLE_PHASE_LABELS
from .exporting import csv_response
from .portfolio import dashboard_view, models_view, resources_view
from .ranking import ranked_projects
from auth import assert_can_manage_project, assert_can_manage_program, manager_required

phase2_bp = Blueprint(
    "phase2",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/phase2-static",
)

@phase2_bp.get("/resources")
def resources():
    selected_department = request.args.get("department", "").strip()
    return render_template(
        "phase2/resources.html",
        **resources_view(selected_department),
    )
@phase2_bp.get("/models")
def models():
    selected_program = request.args.get("program", "").strip()
    return render_template(
        "phase2/models.html",
        **models_view(selected_program),
    )


@phase2_bp.get(
    "/models/<program>"
)
def model_view(
    program
):

    return render_template(
        "phase2/model.html",
        program=program,
        projects=projects_by_model(program)
    )

@phase2_bp.get(
    "/resources/<department>"
)
def department_view(
    department
):

    return render_template(

        "phase2/department.html",

        department=
            department,

        projects=
            projects_by_department(
                department
            )

    )

@phase2_bp.get("/dashboard")
def dashboard():
    return render_template(
        "phase2/dashboard.html",
        **dashboard_view(
            program=request.args.get("program", "").strip(),
            tier=request.args.get("tier", "").strip().upper(),
            query=request.args.get("q", "").strip().lower(),
            lifecycle_phase=request.args.get("lifecycle_phase", "").strip(),
        ),
        lifecycle_phase_labels=LIFECYCLE_PHASE_LABELS,
    )


@phase2_bp.get("/portfolio")
def portfolio():

    return redirect(
        url_for(
            "phase2.dashboard"
        )
    )


@phase2_bp.get("/project/<int:project_id>")
def project(project_id):

    item = fetch_project(
        project_id
    )

    if not item:

        abort(404)

    #
    # Deserialize JSON
    #

    for field in (

        "confidence_json",

        "scoring_json",

        "raw_data_json",

        "warnings_json",

        "extraction_json",

    ):

        value = item.get(field)

        if value:

            try:

                item[
                    field.replace(
                        "_json",
                        ""
                    )
                ] = json.loads(
                    value
                )

            except Exception:

                item[
                    field.replace(
                        "_json",
                        ""
                    )
                ] = {}

    return render_template(

        "phase2/project.html",

        project=item,
        lifecycle_phase_labels=LIFECYCLE_PHASE_LABELS,

        review_reasons=
            review_reasons(
                item
            )
    )


@phase2_bp.post("/project/<int:project_id>/lifecycle-phase")
@manager_required
def update_project_lifecycle_phase(project_id):
    item = fetch_project(project_id)
    if not item:
        abort(404)
    assert_can_manage_project(project_id)
    lifecycle_phase = request.form.get("lifecycle_phase", "").strip()
    if lifecycle_phase not in LIFECYCLE_PHASE_LABELS:
        abort(400, "Invalid lifecycle phase")
    update_lifecycle_phase(project_id, lifecycle_phase)
    return redirect(url_for("phase2.project", project_id=project_id))


@phase2_bp.post(
    "/project/<int:project_id>/archive"
)
@manager_required
def archive(project_id):

    if not fetch_project(project_id):
        abort(404)
    assert_can_manage_project(project_id)

    set_archived(
        project_id,
        True
    )

    return redirect(
        url_for(
            "phase2.dashboard"
        )
    )


@phase2_bp.post(
    "/project/<int:project_id>/restore"
)
@manager_required
def restore(project_id):

    if not fetch_project(project_id):
        abort(404)
    assert_can_manage_project(project_id)

    set_archived(
        project_id,
        False
    )

    return redirect(
        url_for(
            "phase2.project",
            project_id=project_id
        )
    )


@phase2_bp.post(
    "/project/<int:project_id>/delete"
)
@manager_required
def delete_record(project_id):

    if not fetch_project(project_id):
        abort(404)
    assert_can_manage_project(project_id)

    delete_project(
        project_id
    )

    return redirect(
        url_for(
            "phase2.dashboard"
        )
    )


@phase2_bp.get(
    "/exports/portfolio.csv"
)
def export_csv():

    return csv_response(
        ranked_projects(
            fetch_projects()
        )
    )


@phase2_bp.post(
    "/api/projects"
)
@manager_required
def api_create_project():

    payload = request.get_json(
        force=True
    )

    data = payload.get("data", {})
    assert_can_manage_program(data.get("program"))
    project_id = save_project(

        data,

        payload.get(
            "qualification"
        ),

        payload.get(
            "scoring"
        ),

        payload.get(
            "confidence"
        ),

        payload.get(
            "source"
        ),

        payload.get(
            "warnings"
        ),

    )

    return jsonify({

        "id":
            project_id,

        "url":
            url_for(
                "phase2.project",
                project_id=project_id
            )

    }), 201