from datetime import date, datetime
from config import LABELS, WEIGHTS


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
    elif days <= 90:
        time_score = 95
    elif days <= 180:
        time_score = 85
    elif days <= 365:
        time_score = 65
    elif days <= 540:
        time_score = 45
    else:
        time_score = 25

    if target:
        margin = (need_by - target).days
    elif lead > 0:
        margin = days - lead
    else:
        margin = None

    if margin is None:
        margin_score, detail = 40, "Schedule margin unavailable"
    elif margin < 0:
        margin_score, detail = 100, f"Schedule is short by {abs(margin)} days"
    elif margin <= 15:
        margin_score, detail = 90, f"Schedule margin is {margin} days"
    elif margin <= 30:
        margin_score, detail = 75, f"Schedule margin is {margin} days"
    elif margin <= 60:
        margin_score, detail = 55, f"Schedule margin is {margin} days"
    else:
        margin_score, detail = 30, f"Schedule margin is {margin} days"

    return clamp(0.60 * time_score + 0.40 * margin_score), [f"{days} days to need-by date", detail]


def score_operational(data):
    parts = {
        "Prevented deliveries": min(data.get("prevented_deliveries", 0) * 30, 60),
        "AOG events": min(data.get("aog_events", 0) * 18, 45),
        "Delivery delays": min(data.get("delivery_delays", 0) * 8, 32),
        "Line interruptions": min(data.get("line_interruptions", 0) * 7, 28),
        "Repeat rework": min(data.get("repeat_rework", 0) * 3, 18),
    }
    details = [f"{name}: +{points:g}" for name, points in parts.items() if points > 0]
    return clamp(sum(parts.values())), details or ["No quantified operational impact"]


def score_customer_fleet(data):
    pct = data.get("affected_fleet_pct", 0)
    if pct >= 50: fleet = 100
    elif pct >= 25: fleet = 85
    elif pct >= 10: fleet = 70
    elif pct >= 5: fleet = 50
    elif pct >= 1: fleet = 25
    elif pct > 0: fleet = 10
    else: fleet = 0
    escalation = min(data.get("customer_escalations", 0) * 15, 60)
    commitment = 100 if data.get("customer_commitment") else 0
    score = 0.55 * fleet + 0.25 * escalation + 0.20 * commitment
    return clamp(score), [f"Affected fleet: {pct:g}%", f"Customer escalations: {data.get('customer_escalations', 0):g}", "Customer commitment: " + ("Yes" if commitment else "No")]


def score_financial(data):
    npv = data.get("five_year_npv", 0)
    score = 0 if npv <= 0 else npv / 500000 * 100
    return clamp(score), [f"Five-year net benefit: ${npv:,.0f}"]


def score_breadth(data):
    functions = min(data.get("functions_involved", 0) / 8 * 100, 100)
    models = min(data.get("model_families", 0) / 4 * 100, 100)
    lifecycle = min(data.get("lifecycle_areas", 0) / 5 * 100, 100)
    score = 0.50 * functions + 0.30 * models + 0.20 * lifecycle
    return clamp(score), [f"Functions: {data.get('functions_involved', 0):g}", f"Model families: {data.get('model_families', 0):g}", f"Lifecycle areas: {data.get('lifecycle_areas', 0):g}"]


def score_readiness(data):
    names = ["ready_owner", "ready_scope", "ready_business_case", "ready_estimate", "ready_functions", "ready_dates", "ready_approach", "ready_funding", "ready_milestones", "ready_evidence"]
    completed = sum(bool(data.get(name)) for name in names)
    return completed * 10.0, [f"{completed} of 10 readiness items complete"]


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
        factors[key] = {"label": LABELS[key], "score": score, "weight": WEIGHTS[key], "details": details, "contribution": round(score * WEIGHTS[key], 2)}
    ops = round(sum(item["contribution"] for item in factors.values()), 2)
    return {"ops": ops, "factors": factors}


def priority_tier(ops, qualification):
    if qualification == "M1": return "Mandatory Tier 1"
    if qualification == "M2": return "Mandatory Tier 2"
    if qualification == "NOT CTI": return "Not ranked"
    if ops >= 75: return "D1 - Critical"
    if ops >= 55: return "D2 - High"
    if ops >= 35: return "D3 - Moderate"
    return "D4 - Low"
