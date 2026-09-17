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

from .analytics import portfolio_metrics, review_reasons
from .database import (
    delete_project,
    fetch_project,
    fetch_projects,
    save_project,
    set_archived,
    fetch_departments,
    projects_by_department,
    fetch_models,
    projects_by_model,
    update_lifecycle_phase,
)
from config import LIFECYCLE_PHASE_LABELS
from .exporting import csv_response
from .ranking import ranked_projects

phase2_bp = Blueprint(
    "phase2",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/phase2-static",
)

@phase2_bp.get("/resources")
def resources():
    selected_department = request.args.get(
        "department",
        "",
    ).strip()

    departments = fetch_departments()

    if selected_department:
        source_projects = projects_by_department(
            selected_department
        )
    else:
        # Show only projects that appear under at least one department.
        project_ids = set()
        for department in departments:
            for project in projects_by_department(
                department["department"]
            ):
                project_ids.add(project["id"])

        source_projects = [
            project
            for project in fetch_projects()
            if project["id"] in project_ids
        ]

    projects = ranked_projects(source_projects)

    return render_template(
        "phase2/resources.html",
        departments=departments,
        selected_department=selected_department,
        projects=projects,
    )
@phase2_bp.get("/models")
def models():
    selected_program = request.args.get(
        "program",
        "",
    ).strip()

    model_rows = fetch_models()

    if selected_program:
        source_projects = projects_by_model(
            selected_program
        )
    else:
        source_projects = fetch_projects()

    projects = ranked_projects(source_projects)

    return render_template(
        "phase2/models.html",
        models=model_rows,
        selected_program=selected_program,
        projects=projects,
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

    ranked = ranked_projects(
        fetch_projects()
    )

    program = request.args.get(
        "program",
        ""
    ).strip()

    tier = request.args.get(
        "tier",
        ""
    ).strip().upper()

    query = request.args.get(
        "q",
        ""
    ).strip().lower()

    lifecycle_phase = request.args.get("lifecycle_phase", "").strip()

    filtered = [

        project

        for project in ranked

        if (

            (
                not program
                or project.get("program")
                == program
            )

            and

            (
                not lifecycle_phase
                or project.get("lifecycle_phase") == lifecycle_phase
            )

            and

            (
                not tier
                or project.get(
                    "qualification"
                )
                == tier
            )

            and

            (
                not query

                or query in (
                    project.get(
                        "title"
                    )
                    or ""
                ).lower()

                or query in (
                    project.get(
                        "driver"
                    )
                    or ""
                ).lower()

            )

        )

    ]

    needs_attention = [
        {"project": project, "reasons": review_reasons(project)}
        for project in ranked
        if review_reasons(project)
    ]

    programs = sorted({

        project.get("program")

        for project in ranked

        if project.get("program")

    })
    phase_counts = [
        {
            "key": key,
            "label": label,
            "count": sum(
                project.get("lifecycle_phase") == key for project in ranked
            ),
        }
        for key, label in LIFECYCLE_PHASE_LABELS.items()
    ]

    return render_template(

        "phase2/dashboard.html",

        projects=filtered,

        metrics=portfolio_metrics(
            ranked
        ),

        programs=programs,

        filters={

            "program":
                program,

            "tier":
                tier,

            "q":
                request.args.get(
                    "q",
                    ""
                ),
            "lifecycle_phase": lifecycle_phase,

        },
        needs_attention=needs_attention,
        lifecycle_phase_labels=LIFECYCLE_PHASE_LABELS,
        phase_counts=phase_counts,

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
def update_project_lifecycle_phase(project_id):
    item = fetch_project(project_id)
    if not item:
        abort(404)
    lifecycle_phase = request.form.get("lifecycle_phase", "").strip()
    if lifecycle_phase not in LIFECYCLE_PHASE_LABELS:
        abort(400, "Invalid lifecycle phase")
    update_lifecycle_phase(project_id, lifecycle_phase)
    return redirect(url_for("phase2.project", project_id=project_id))


@phase2_bp.post(
    "/project/<int:project_id>/archive"
)
def archive(project_id):

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
def restore(project_id):

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
def delete_record(project_id):

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
def api_create_project():

    payload = request.get_json(
        force=True
    )

    project_id = save_project(

        payload.get(
            "data",
            {}
        ),

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