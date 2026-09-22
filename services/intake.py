from config import DEFAULT_LIFECYCLE_PHASE, LIFECYCLE_PHASE_LABELS
from validation import raw_form_data, validate_data


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
    "phase", "owner", "problem_statement", "business_case", "need_by",
    "target_date",
] + sorted(NUM_FIELDS) + sorted(BOOL_FIELDS)

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


def form_data(form):
    raw = raw_form_data(form, ALL_FIELDS + ["departments"])
    data, errors = validate_data(raw)
    if errors:
        return raw, errors
    for key in BOOL_FIELDS:
        data[key] = raw.get(key) == "yes"
    return data, {}


def normalize_step_data(raw, step):
    required = {"title"} if step == 1 else set()
    normalized, errors = validate_data(raw, required)
    if errors:
        return raw, errors
    for key in BOOL_FIELDS:
        if key in normalized:
            normalized[key] = normalized[key] == "yes"
    return normalized, {}


def wizard_context(draft, step, errors=None):
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


def new_draft_data():
    return {
        "engineering_threshold": 160,
        "model_families": 1,
        "lifecycle_areas": 1,
        "lifecycle_phase": DEFAULT_LIFECYCLE_PHASE,
    }


def parsed_draft_data(parsed):
    return dict(parsed["data"], lifecycle_phase=DEFAULT_LIFECYCLE_PHASE)


def parsed_extraction(parsed):
    return {
        "fields": parsed.get("fields", {}),
        "review": parsed.get("review", {}),
        "classification": parsed.get("classification", ""),
        "source_type": parsed.get("source_type", ""),
        "template_version": parsed.get("template_version", ""),
    }


def submitted_extraction(draft):
    extraction = draft.get("extraction", {})
    return {
        "warnings": draft.get("warnings", []),
        "fields": extraction.get("fields", {}),
        "review": extraction.get("review", {}),
        "classification": extraction.get("classification", ""),
        "source_type": draft.get("source_type", ""),
        "template_version": draft.get("template_version", ""),
    }
