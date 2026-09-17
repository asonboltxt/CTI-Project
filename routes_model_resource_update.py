# In phase2/routes.py, keep your existing imports.
# Confirm request is imported from flask and ranked_projects is imported from .ranking.
# Replace ONLY your current resources() and models() route functions with these.

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
