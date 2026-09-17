from datetime import date
import math


NUMERIC_FIELDS = {
    "implementation_lead_days", "engineering_hours", "engineering_threshold",
    "cos_score", "prevented_deliveries", "aog_events", "delivery_delays",
    "line_interruptions", "repeat_rework", "affected_fleet_pct",
    "customer_escalations", "five_year_npv", "functions_involved",
    "model_families", "lifecycle_areas", "evidence_count", "milestone_count",
    "affected_aircraft", "active_fleet",
}

INTEGER_FIELDS = {
    "implementation_lead_days", "prevented_deliveries", "aog_events",
    "delivery_delays", "line_interruptions", "repeat_rework",
    "customer_escalations", "functions_involved", "model_families",
    "lifecycle_areas", "evidence_count", "milestone_count",
}

PERCENT_FIELDS = {"affected_fleet_pct"}
DATE_FIELDS = {"need_by", "target_date"}


def raw_form_data(form, fields):
    data = {}
    for key in fields:
        values = form.getlist(key)
        if key == "departments":
            data[key] = values
        elif key in {"regulatory", "certification", "external_commitment",
                     "slt_mandate", "delivery_prevention",
                     "critical_obsolescence", "major_supply_disruption",
                     "unit_specific", "fast_engineering", "non_ecr",
                     "cross_functional", "customer_commitment", "ready_owner",
                     "ready_scope", "ready_business_case", "ready_estimate",
                     "ready_functions", "ready_dates", "ready_approach",
                     "ready_funding", "ready_milestones", "ready_evidence"}:
            data[key] = form.get(key, "no")
        else:
            data[key] = form.get(key, "")
    return data


def validate_data(raw, required_fields=None):
    required_fields = set(required_fields or ())
    data = dict(raw)
    errors = {}

    if "title" in required_fields and not str(raw.get("title", "")).strip():
        errors["title"] = "Enter a project title."

    for field in NUMERIC_FIELDS:
        if field not in raw:
            continue
        value = raw.get(field)
        if value in (None, ""):
            data[field] = 0
            continue
        text = str(value).strip()
        try:
            number = float(text)
        except (TypeError, ValueError):
            errors[field] = "Enter a valid number."
            continue
        if not math.isfinite(number):
            errors[field] = "Enter a finite number."
            continue
        if field in INTEGER_FIELDS and not number.is_integer():
            errors[field] = "Enter a whole number."
            continue
        if number < 0:
            errors[field] = "Enter a number greater than or equal to 0."
            continue
        if field in PERCENT_FIELDS and number > 100:
            errors[field] = "Enter a percentage from 0 to 100."
            continue
        data[field] = int(number) if field in INTEGER_FIELDS else number

    for field in DATE_FIELDS:
        if field not in raw:
            continue
        value = str(raw.get(field, "")).strip()
        if not value:
            data[field] = ""
            continue
        try:
            date.fromisoformat(value)
        except ValueError:
            errors[field] = "Enter a valid date in YYYY-MM-DD format."
            continue
        data[field] = value

    if data.get("target_date") and data.get("need_by"):
        if data["target_date"] > data["need_by"]:
            errors["target_date"] = "Target date must be on or before the need-by date."

    for field, value in list(data.items()):
        if field not in NUMERIC_FIELDS and field not in DATE_FIELDS and field != "departments":
            if isinstance(value, bool):
                data[field] = value
            else:
                data[field] = str(value).strip() if value is not None else ""

    return data, errors
