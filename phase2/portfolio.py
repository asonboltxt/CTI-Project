from .analytics import portfolio_metrics, review_reasons
from .database import (
    fetch_departments,
    fetch_models,
    fetch_projects,
    fetch_projects_with_departments,
    projects_by_department,
    projects_by_model,
)
from .ranking import ranked_projects
from config import LIFECYCLE_PHASE_LABELS


def resources_view(selected_department=""):
    departments = fetch_departments()
    source_projects = (
        projects_by_department(selected_department)
        if selected_department
        else fetch_projects_with_departments()
    )
    return {
        "departments": departments,
        "selected_department": selected_department,
        "projects": ranked_projects(source_projects),
    }


def models_view(selected_program=""):
    model_rows = fetch_models()
    source_projects = (
        projects_by_model(selected_program)
        if selected_program
        else fetch_projects()
    )
    return {
        "models": model_rows,
        "selected_program": selected_program,
        "projects": ranked_projects(source_projects),
    }


def dashboard_view(program="", tier="", query="", lifecycle_phase=""):
    ranked = ranked_projects(fetch_projects())
    filtered = [
        project
        for project in ranked
        if (
            (not program or project.get("program") == program)
            and (
                not lifecycle_phase
                or project.get("lifecycle_phase") == lifecycle_phase
            )
            and (not tier or project.get("qualification") == tier)
            and (
                not query
                or query in (project.get("title") or "").lower()
                or query in (project.get("driver") or "").lower()
            )
        )
    ]
    needs_attention = [
        {"project": project, "reasons": review_reasons(project)}
        for project in ranked
        if review_reasons(project)
    ]
    programs = sorted(
        {project.get("program") for project in ranked if project.get("program")}
    )
    phase_counts = [
        {
            "key": key,
            "label": label,
            "count": sum(project.get("lifecycle_phase") == key for project in ranked),
        }
        for key, label in LIFECYCLE_PHASE_LABELS.items()
    ]
    return {
        "projects": filtered,
        "metrics": portfolio_metrics(ranked),
        "programs": programs,
        "needs_attention": needs_attention,
        "phase_counts": phase_counts,
        "filters": {"program": program, "tier": tier, "q": query, "lifecycle_phase": lifecycle_phase},
    }
