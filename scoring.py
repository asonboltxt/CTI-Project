from datetime import date, datetime, timezone
from config import LABELS, SCORING_MODEL_VERSION, WEIGHTS


def clamp(value):
    return round(max(0, min(100, value)), 1)


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def score_urgency(data):
    need_by = parse_date(data.get("need_by"))
    target = parse_date(data.get("target_date"))
    lead = data.get("implementation_lead_days", 0)
    if not need_by:
        return 0.0, ["Need-by date is missing"]

    days = (need_by - date.today()).days
    if days <= 0:
        time_score = 100
        time_range = "due or overdue"
    elif days <= 90:
        time_score = 95
        time_range = "1-90 days"
    elif days <= 180:
        time_score = 85
        time_range = "91-180 days"
    elif days <= 365:
        time_score = 65
        time_range = "181-365 days"
    elif days <= 540:
        time_score = 45
        time_range = "366-540 days"
    else:
        time_score = 25
        time_range = "more than 540 days"

    if target:
        margin = (need_by - target).days
    elif lead > 0:
        margin = days - lead
    else:
        margin = None

    if margin is None:
        margin_score, detail = 40, "Schedule margin unavailable"
        margin_calculation = "No target date or usable implementation lead"
    elif margin < 0:
        margin_score, detail = 100, f"Schedule is short by {abs(margin)} days"
        margin_calculation = f"Need-by date - target date/lead = {margin} days"
    elif margin <= 15:
        margin_score, detail = 90, f"Schedule margin is {margin} days"
        margin_calculation = f"Need-by date - target date/lead = {margin} days"
    elif margin <= 30:
        margin_score, detail = 75, f"Schedule margin is {margin} days"
        margin_calculation = f"Need-by date - target date/lead = {margin} days"
    elif margin <= 60:
        margin_score, detail = 55, f"Schedule margin is {margin} days"
        margin_calculation = f"Need-by date - target date/lead = {margin} days"
    else:
        margin_score, detail = 30, f"Schedule margin is {margin} days"
        margin_calculation = f"Need-by date - target date/lead = {margin} days"

    time_points = 0.60 * time_score
    margin_points = 0.40 * margin_score
    factor_score = clamp(time_points + margin_points)
    return factor_score, [
        f"Time-to-need: {days} days ({time_range}) -> {time_score}/100 x 60% = {time_points:g} points",
        f"{margin_calculation}: {margin_score}/100 x 40% = {margin_points:g} points",
        f"Urgency factor score: {factor_score}/100",
    ]


def score_operational(data):
    components = {
        "Prevented deliveries": (data.get("prevented_deliveries", 0), 30, 60),
        "AOG events": (data.get("aog_events", 0), 18, 45),
        "Delivery delays": (data.get("delivery_delays", 0), 8, 32),
        "Line interruptions": (data.get("line_interruptions", 0), 7, 28),
        "Repeat rework": (data.get("repeat_rework", 0), 3, 18),
    }
    parts = {
        name: min(count * points_per_item, cap)
        for name, (count, points_per_item, cap) in components.items()
    }
    factor_score = clamp(sum(parts.values()))
    details = [
        f"{name}: {count:g} x {points_per_item} points, capped at {cap} = {parts[name]:g} points"
        for name, (count, points_per_item, cap) in components.items()
    ]
    details.append(f"Operational factor score: {factor_score}/100 (sum capped at 100)")
    return factor_score, details


def score_customer_fleet(data):
    pct = data.get("affected_fleet_pct", 0)
    if pct >= 50: fleet = 100
    elif pct >= 25: fleet = 85
    elif pct >= 10: fleet = 70
    elif pct >= 5: fleet = 50
    elif pct >= 1: fleet = 25
    elif pct > 0: fleet = 10
    else: fleet = 0
    escalations = data.get("customer_escalations", 0)
    escalation = min(escalations * 15, 60)
    commitment = 100 if data.get("customer_commitment") else 0
    fleet_points = 0.55 * fleet
    escalation_points = 0.25 * escalation
    commitment_points = 0.20 * commitment
    score = clamp(fleet_points + escalation_points + commitment_points)
    return score, [
        f"Affected fleet: {pct:g}% -> {fleet}/100 x 55% = {fleet_points:g} points",
        f"Customer escalations: {escalations:g} x 15, capped at 60 -> {escalation}/100 x 25% = {escalation_points:g} points",
        f"Customer commitment: {'Yes' if commitment else 'No'} -> {commitment}/100 x 20% = {commitment_points:g} points",
        f"Customer / Fleet factor score: {score}/100",
    ]


def score_financial(data):
    npv = data.get("five_year_npv", 0)
    score = 0 if npv <= 0 else npv / 500000 * 100
    factor_score = clamp(score)
    return factor_score, [
        f"Five-year net benefit: ${npv:,.0f} / $500,000 x 100 = {score:g}, bounded to {factor_score}/100"
    ]


def score_breadth(data):
    function_count = data.get("functions_involved", 0)
    model_count = data.get("model_families", 0)
    lifecycle_count = data.get("lifecycle_areas", 0)
    functions = min(function_count / 8 * 100, 100)
    models = min(model_count / 4 * 100, 100)
    lifecycle = min(lifecycle_count / 5 * 100, 100)
    function_points = 0.50 * functions
    model_points = 0.30 * models
    lifecycle_points = 0.20 * lifecycle
    score = clamp(function_points + model_points + lifecycle_points)
    return score, [
        f"Functions: {function_count:g}/8 -> {functions:g}/100 x 50% = {function_points:g} points",
        f"Model families: {model_count:g}/4 -> {models:g}/100 x 30% = {model_points:g} points",
        f"Lifecycle areas: {lifecycle_count:g}/5 -> {lifecycle:g}/100 x 20% = {lifecycle_points:g} points",
        f"Breadth factor score: {score}/100",
    ]


def score_readiness(data):
    items = [
        ("ready_owner", "Owner identified"),
        ("ready_scope", "Scope defined"),
        ("ready_business_case", "Business case documented"),
        ("ready_estimate", "Estimate prepared"),
        ("ready_functions", "Functions identified"),
        ("ready_dates", "Dates established"),
        ("ready_approach", "Approach selected"),
        ("ready_funding", "Funding identified"),
        ("ready_milestones", "Milestones defined"),
        ("ready_evidence", "Evidence provided"),
    ]
    names = [name for name, _ in items]
    completed = sum(bool(data.get(name)) for name in names)
    score = completed * 10.0
    details = [
        f"Readiness checks: {completed}/10 complete x 10 points each = {score:g}/100"
    ]
    details.extend(
        f"{label}: {'Complete' if data.get(name) else 'Incomplete'}"
        for name, label in items
    )
    return score, details


FACTOR_INPUTS = {
    "urgency": ("need_by", "target_date", "implementation_lead_days"),
    "operational": (
        "prevented_deliveries", "aog_events", "delivery_delays",
        "line_interruptions", "repeat_rework",
    ),
    "customer_fleet": ("affected_fleet_pct", "customer_escalations", "customer_commitment"),
    "financial": ("five_year_npv",),
    "breadth": ("functions_involved", "model_families", "lifecycle_areas"),
    "readiness": (
        "ready_owner", "ready_scope", "ready_business_case", "ready_estimate",
        "ready_functions", "ready_dates", "ready_approach", "ready_funding",
        "ready_milestones", "ready_evidence",
    ),
}

FACTOR_METHODS = {
    "urgency": (
        "Factor score = 60% time-to-need score + 40% schedule-margin score. "
        "Time-to-need scores are 100 for due/overdue, 95 for 1-90 days, "
        "85 for 91-180, 65 for 181-365, 45 for 366-540, and 25 beyond 540 days. "
        "Margin scores are 100 when the schedule is short, 90 for 0-15 days, "
        "75 for 16-30, 55 for 31-60, 30 beyond 60, or 40 when unavailable. "
        "Margin is need-by date minus target date, or days remaining minus implementation lead; "
        "a missing need-by date gives urgency a score of 0."
    ),
    "operational": (
        "Add impact points: prevented deliveries +30 each (cap 60), AOG events "
        "+18 each (cap 45), delivery delays +8 each (cap 32), line interruptions "
        "+7 each (cap 28), and repeat rework +3 each (cap 18). Total is capped at 100."
    ),
    "customer_fleet": (
        "Factor score = 55% affected-fleet score + 25% escalation score + "
        "20% customer-commitment score. Fleet scores are 0 for none, 10 below 1%, "
        "25 at 1-4.9%, 50 at 5-9.9%, 70 at 10-24.9%, 85 at 25-49.9%, and "
        "100 at 50% or more. Escalations add 15 points each, capped at 60; "
        "a customer commitment scores 100."
    ),
    "financial": (
        "Factor score = five-year net benefit / $500,000 x 100, bounded from 0 to 100. "
        "A benefit of $500,000 or more scores 100; zero or negative benefit scores 0."
    ),
    "breadth": (
        "Factor score = 50% functions score + 30% model-families score + "
        "20% lifecycle-areas score. Each input is normalized to 0-100 against "
        "8 functions, 4 model families, and 5 lifecycle areas, respectively."
    ),
    "readiness": (
        "There are 10 readiness checks worth 10 points each. Each completed check "
        "adds 10 points, for a factor score from 0 to 100: owner, scope, business case, "
        "estimate, functions, dates, approach, funding, milestones, and evidence."
    ),
}


def missing_inputs(data, fields):
    return [
        field for field in fields
        if field not in data or data.get(field) in (None, "")
    ]


def calculate_all_scores(data):
    methods = {
        "urgency": score_urgency,
        "operational": score_operational,
        "customer_fleet": score_customer_fleet,
        "financial": score_financial,
        "breadth": score_breadth,
        "readiness": score_readiness,
    }
    factors = {}
    for key, method in methods.items():
        score, details = method(data)
        missing = missing_inputs(data, FACTOR_INPUTS[key])
        factors[key] = {
            "label": LABELS[key],
            "score": score,
            "weight": WEIGHTS[key],
            "method": FACTOR_METHODS[key],
            "details": details,
            "contribution": round(score * WEIGHTS[key], 2),
            "missing_inputs": missing,
            "complete": not missing,
        }
    ops = round(sum(item["contribution"] for item in factors.values()), 2)
    missing = sorted({field for factor in factors.values() for field in factor["missing_inputs"]})
    return {
        "ops": ops,
        "factors": factors,
        "model_version": SCORING_MODEL_VERSION,
        "scored_utc": datetime.now(timezone.utc).isoformat(),
        "missing_inputs": missing,
        "data_quality": "Complete" if not missing else "Incomplete",
    }


def priority_tier(ops, qualification):
    if qualification == "M1": return "Mandatory Tier 1"
    if qualification == "M2": return "Mandatory Tier 2"
    if qualification == "NOT CTI": return "Not ranked"
    if ops >= 75: return "D1 - Critical"
    if ops >= 55: return "D2 - High"
    if ops >= 35: return "D3 - Moderate"
    return "D4 - Low"
