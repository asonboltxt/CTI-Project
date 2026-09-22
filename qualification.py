from config import COS_MANDATORY_GATE, DEFAULT_ENGINEERING_THRESHOLD


def classification_code(data):
    """Return the stable M1/M2/D/NOT CTI decision used by all entry points."""
    threshold = data.get("engineering_threshold") or DEFAULT_ENGINEERING_THRESHOLD
    hours = data.get("engineering_hours") or 0
    if data.get("unit_specific") or data.get("fast_engineering") or data.get("non_ecr"):
        return "NOT CTI"
    if (
        data.get("regulatory")
        or data.get("certification")
        or (data.get("cos_score") or 0) >= COS_MANDATORY_GATE
    ):
        return "M1"
    if hours >= threshold and (
        data.get("external_commitment")
        or data.get("slt_mandate")
        or data.get("delivery_prevention")
        or data.get("critical_obsolescence")
        or data.get("major_supply_disruption")
    ):
        return "M2"
    if hours >= threshold:
        return "D"
    return "NOT CTI"


def calculate_qualification(data):
    """Return the V4.8.2 qualification result and its traceable reasons."""
    threshold = data.get("engineering_threshold") or DEFAULT_ENGINEERING_THRESHOLD
    hours = data.get("engineering_hours", 0)

    exclusions = []
    if data.get("unit_specific"):
        exclusions.append("Unit-specific or serial-specific change")
    if data.get("fast_engineering"):
        exclusions.append("PDI / Fast Engineering work")
    if data.get("non_ecr"):
        exclusions.append("Non-ECR corrective action")
    if exclusions:
        return {"code": "NOT CTI", "qualified": False, "reasons": exclusions}

    m1 = []
    if data.get("regulatory"):
        m1.append("Regulatory requirement")
    if data.get("certification"):
        m1.append("Certification mandate")
    if data.get("cos_score", 0) >= COS_MANDATORY_GATE:
        m1.append(f"COS score meets the {COS_MANDATORY_GATE:g} mandatory gate")
    if m1:
        return {"code": "M1", "qualified": True, "reasons": m1}

    m2 = []
    if data.get("external_commitment") or data.get("slt_mandate"):
        m2.append("SLT / external commitment")
    if data.get("delivery_prevention"):
        m2.append("Delivery-prevention commitment")
    if data.get("critical_obsolescence"):
        m2.append("Critical obsolescence")
    if data.get("major_supply_disruption"):
        m2.append("Major supply disruption")
    if m2 and hours >= threshold:
        m2.append(f"Engineering effort meets the configured {threshold:g}-hour gate")
        return {"code": "M2", "qualified": True, "reasons": m2}

    if hours >= threshold:
        reasons = [f"Engineering effort meets the configured {threshold:g}-hour gate"]
        if data.get("cross_functional"):
            reasons.append("Cross-functional Core Team coordination is required")
        return {"code": "D", "qualified": True, "reasons": reasons}

    reasons = [f"Engineering effort is below the configured {threshold:g}-hour gate"]
    if m2:
        reasons.extend(m2)
    return {"code": "NOT CTI", "qualified": False, "reasons": reasons}
