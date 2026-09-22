import re
from datetime import datetime
from qualification import classification_code

CHECKED = ("☒", "☑", "■", "✓", "✔")
UNCHECKED = ("☐", "□", "○")

FIELD_LABELS = {
    "title": ("CTI Title", "Critical Task Item Title", "Proposal Title"),
    "program": ("Model / Program", "Model/Program", "Affected Program", "Program / Model"),
    "requesting_organization": ("Requesting Organization",),
    "originator": ("Originator",),
    "owner": ("Proposed Champion", "Accountable Owner"),
    "scope_change": ("Scope Change", "Scope"),
    "need_by": ("Need-By Date", "Need By Date", "Need-by"),
    "target_date": ("Target Completion Date", "Target Date", "Implementation Date"),
    "implementation_lead_days": ("Estimated Implementation Lead Time", "Estimated Engineering Lead Time", "Calendar Months"),
    "engineering_hours": ("Estimated Engineering Labor", "Engineering Hours", "Engineering Labor"),
    "five_year_npv": ("5-Year Net Benefit / Avoided Cost", "Five-Year Net Benefit / Avoided Cost", "Five-Year Net Benefit"),
    "functions_involved": ("Functions with Deliverables", "Engineering Disciplines"),
    "model_families": ("Affected Model Families",),
    "affected_aircraft": ("Affected Aircraft", "Affected Aircraft / Units"),
    "active_fleet": ("Applicable Active Fleet",),
    "aog_events": ("Annual AOG events",),
    "prevented_deliveries": ("Annual prevented deliveries",),
    "delivery_delays": ("Annual delivery delays",),
    "line_interruptions": ("Annual line interruptions",),
    "repeat_rework": ("Annual repeat rework events",),
    "affected_fleet_pct": ("Affected fleet percentage",),
}

PROGRAM_CATEGORIES = (
    "King Air",
    "Part 23 Jets",
    "Part 25 Jets",
    "SkyCourier",
    "Caravan",
    "OOP",
    "Pistons",
    "Ascend",
)

NUMERIC_FIELDS = {
    "implementation_lead_days", "engineering_hours", "functions_involved",
    "model_families", "affected_aircraft", "active_fleet", "aog_events",
    "prevented_deliveries", "delivery_delays", "line_interruptions",
    "repeat_rework", "affected_fleet_pct",
}
PERCENT_FIELDS = {"affected_fleet_pct"}
NONNEGATIVE_FIELDS = NUMERIC_FIELDS

DEPARTMENT_NAMES = (
    "Structures", "AES", "Avionics", "Electrical Systems", "Software",
    "Interiors", "Materials & Processes", "Reliability", "Quality",
    "Certification", "Customer Service Engineering", "Program Management",
    "Manufacturing Engineering", "Industrial Engineering", "Supply Chain",
    "Procurement", "Configuration Management", "Technical Publications",
    "Test Engineering", "Flight Test", "Safety", "Production Support",
    "Tooling",
)

def clean(value):
    return " ".join((value or "").replace("\xa0", " ").split()).strip()

def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()

def normalize_program(value):
    """Map template model names to the program buckets used by portfolio views."""
    text = normalized(value)
    if not text:
        return ""
    if re.search(r"\bking air\b", text):
        return "King Air"
    if re.search(r"\bsky ?courier\b", text):
        return "SkyCourier"
    if re.search(r"\bout of production\b|\boop\b|\bhawker\b", text):
        return "OOP"
    if re.search(r"\bascend\b", text):
        return "Ascend"
    if re.search(r"\b(?:caravan|grand caravan|model 208|208b|208 caravan)\b", text):
        return "Caravan"
    if re.search(r"\b(?:172|182|t206|skyhawk|skylane|stationair|piston)\b", text):
        return "Pistons"
    if re.search(r"\b(?:longitude|latitude|sovereign|model 700)\b", text):
        return "Part 25 Jets"
    if re.search(r"\b(?:m2|cj3|cj4|model 525|part 23)\b", text):
        return "Part 23 Jets"
    return clean(value)

def number(value):
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", clean(value))
    return float(match.group(0).replace(",", "")) if match else None

def money(value):
    amount = number(value)
    if amount is None:
        return None
    low = clean(value).lower()
    if re.search(r"(?:million|\d\s*m\b|\d\.\d+m\b)", low):
        amount *= 1_000_000
    elif re.search(r"(?:thousand|\d\s*k\b|\d+k\b)", low):
        amount *= 1_000
    return amount

def date_value(value):
    text = clean(value)
    match = re.search(r"\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}", text)
    candidates = [re.sub(r"\s+", "", match.group(0))] if match else []
    candidates.extend(re.findall(r"\b(?:\w+\s+)?\d{1,2},\s*\d{4}\b", text))
    candidates.extend(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text))
    for candidate in candidates:
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None

def docx_rows(extracted):
    for table in extracted.get("tables", []):
        for row in table.get("rows", []):
            yield row["cells"], table["table_index"], row["row_index"]

def row_value(extracted, labels):
    wanted = [normalized(x) for x in labels]
    rows = list(docx_rows(extracted))
    for cells, table_index, row_index in rows:
        for index, cell in enumerate(cells[:-1]):
            if normalized(cell) in wanted:
                return clean(cells[index + 1]), f"table {table_index + 1}, row {row_index + 1}"
    for cells, table_index, row_index in rows:
        for index, cell in enumerate(cells[:-1]):
            label = normalized(cell)
            if any(label == item or label.startswith(item) for item in wanted):
                return clean(cells[index + 1]), f"table {table_index + 1}, row {row_index + 1}"
    return None, None

def question_value(extracted, phrases):
    wanted = [normalized(x) for x in phrases]
    for cells, table_index, row_index in docx_rows(extracted):
        if len(cells) < 2:
            continue
        question = normalized(cells[0])
        if any(item in question for item in wanted):
            return clean(cells[1]), f"table {table_index + 1}, row {row_index + 1}"
    return None, None

def narrative_value(extracted, phrases):
    text = clean(extracted.get("text", ""))
    for phrase in phrases:
        pattern = re.escape(phrase).replace(r"\ ", r"\s+")
        match = re.search(pattern + r".{0,180}", text, re.I)
        if match:
            return match.group(0), "document narrative"
    return None, None

def find_docx_value(extracted, labels):
    result = row_value(extracted, labels)
    if result[0] is not None:
        return result
    return question_value(extracted, labels)

def find_pdf_value(text, labels):
    lines = [clean(line) for line in text.splitlines()]
    for i, line in enumerate(lines):
        for label in labels:
            pattern = re.escape(label).replace(r"\ ", r"\s+")
            same = re.search(pattern + r"\s*[:|\-]\s*(.+)$", line, re.I)
            if same:
                return clean(same.group(1)), f"PDF line {i + 1}"
            if re.fullmatch(r"\s*" + pattern + r"\s*", line, re.I):
                for next_line in lines[i + 1:i + 4]:
                    if next_line:
                        return next_line, f"PDF line {i + 2}"
    return None, None

def get_value(extracted, labels):
    if extracted.get("file_type") == "docx":
        result = find_docx_value(extracted, labels)
        if result[0] is not None:
            return result
    return find_pdf_value(extracted.get("text", ""), labels)

def all_row_values(extracted, labels):
    wanted = [normalized(x) for x in labels]
    values = []
    for cells, table_index, row_index in docx_rows(extracted):
        for index, cell in enumerate(cells[:-1]):
            label = normalized(cell)
            if label in wanted:
                value = clean(cells[index + 1])
                if value:
                    values.append((value, f"table {table_index + 1}, row {row_index + 1}"))
    return values

def parse_field_value(field, raw):
    if field in ("need_by", "target_date"):
        return date_value(raw)
    if field == "five_year_npv":
        return money(raw)
    if field == "functions_involved":
        return count_functions(raw)
    if field in NUMERIC_FIELDS:
        return number(raw)
    return clean(raw)

def domain_issue(field, value):
    if field in NONNEGATIVE_FIELDS and isinstance(value, (int, float)) and value < 0:
        return "must be zero or greater"
    if field in PERCENT_FIELDS and isinstance(value, (int, float)) and value > 100:
        return "must be between 0 and 100"
    return None

def find_heading_block_docx(extracted, heading):
    target = normalized(heading)
    tables = extracted.get("tables", [])
    for table in tables:
        rows = table.get("rows", [])
        for index, row in enumerate(rows):
            cells = row["cells"]
            if cells and normalized(cells[0]) == target:
                for next_row in rows[index + 1:index + 3]:
                    value = clean(" ".join(next_row["cells"]))
                    if value:
                        return value
    return ""

def find_heading_block_pdf(text, heading, next_headings):
    low = text.lower()
    start = low.find(heading.lower())
    if start < 0:
        return ""
    start += len(heading)
    end = len(text)
    for next_heading in next_headings:
        position = low.find(next_heading.lower(), start)
        if position >= 0:
            end = min(end, position)
    return clean(text[start:end])

def heading_block(extracted, heading, next_headings):
    if extracted.get("file_type") == "docx":
        value = find_heading_block_docx(extracted, heading)
        if value:
            return value
    return find_heading_block_pdf(extracted.get("text", ""), heading, next_headings)

def checked_option(value, option):
    value = clean(value)
    option_pattern = re.escape(option).replace(r"\ ", r"\s+")
    return bool(re.search(r"(?:☒|☑|■|✓|✔)\s*" + option_pattern, value, re.I))

def selected_driver(value):
    choices = [
        ("Quality/Reliability", "Quality/Reliability"),
        ("Supply Chain", "Supply Chain"),
        ("Production Support", "Production Support"),
        ("Safety", "Safety"),
        ("Certification Mandate", "Certification Mandate"),
        ("Certification / Program Commitment", "Certification Mandate"),
        ("Regulatory / Certification Compliance", "Certification Mandate"),
        ("Customer Service", "Customer Service"),
        ("Marketability", "Marketability"),
        ("Obsolescence", "Obsolescence"),
        ("Obsolescence / Supply Continuity", "Obsolescence"),
    ]
    for choice, canonical in choices:
        if checked_option(value, choice):
            return canonical
    plain = normalized(value)
    for choice, canonical in choices:
        if normalized(choice) in plain:
            return canonical
    return "Quality/Reliability"

def selected_phase(value):
    match = re.search(r"(?:☒|☑|■|✓|✔)\s*Phase\s*([1-7])", value, re.I)
    if not match:
        match = re.search(r"\bPhase\s*([1-7])\b", value, re.I)
    return f"Phase {match.group(1)}" if match else "Phase 1"

def exact_objective_rows(extracted):
    values = {}
    evidence = set()
    for table in extracted.get("tables", []):
        rows = table.get("rows", [])
        if not rows:
            continue
        header = " | ".join(rows[0]["cells"]).lower()
        if "objective input" not in header or "value" not in header:
            continue
        for row in rows[1:]:
            cells = row["cells"]
            if len(cells) >= 2:
                values[normalized(cells[0])] = clean(cells[1])
            if len(cells) >= 4:
                evidence.update(re.findall(r"\bE-\d{2}\b", cells[3], re.I))
    return values, evidence

def count_milestones(extracted):
    for table in extracted.get("tables", []):
        rows = table.get("rows", [])
        if rows and "milestone" in normalized(rows[0]["cells"][0]) and any("target date" in normalized(cell) for cell in rows[0]["cells"]):
            return max(0, len(rows) - 1)
    return 0

def count_functions(raw):
    explicit = number(raw)
    if explicit is not None:
        return explicit
    if not raw or normalized(raw) in {"mock planning basis", "n a", "not applicable"}:
        return None
    tail = re.sub(r"^[^—-]*[—-]", "", raw)
    names = [x.strip() for x in tail.split(",") if x.strip()]
    return float(len(names)) if names else None

def classification_flags(extracted):
    requested, _ = get_value(extracted, ("Requested Classification",))
    mandatory_basis = heading_block(extracted, "SAFETY / REGULATORY / SLT / EXTERNAL COMMITMENT BASIS", ("10. Originator", "11. System"))
    requested = clean(requested or "")
    basis = clean(mandatory_basis or "")
    combined = clean(requested + " " + basis)
    has_structured_classification = bool(requested)
    negative = bool(re.search(
        r"not applicable|no safety|no regulatory|no certification|no (?:slt|external)",
        combined,
        re.I,
    ))
    regulatory_selected = checked_option(requested, "Safety / Regulatory") or normalized(requested) == "safety regulatory"
    external_selected = checked_option(requested, "SLT / External Commitment") or normalized(requested) == "slt external commitment"
    text = extracted.get("text", "")
    positive_obsolescence = bool(re.search(
        r"\b(?:critical obsolescence|obsolescence|obsolete|end[- ]of[- ]life|end[- ]of[- ]production)\b",
        text,
        re.I,
    ))
    positive_supply = bool(re.search(
        r"\b(?:major supply disruption|sole[- ]source|supplier .*?(?:end[- ]of[- ]life|end[- ]of[- ]production)|delivery disruption)\b",
        text,
        re.I,
    ))
    negative_obsolescence = bool(re.search(r"\bno (?:critical )?obsolescence\b|\bnot applicable\b", combined, re.I))
    negative_supply = bool(re.search(r"\bno (?:major )?supply disruption\b|\bnot applicable\b", combined, re.I))
    return {
        "regulatory": (
            regulatory_selected
            if has_structured_classification
            else bool(re.search(r"regulatory requirement|regulatory mandate|safety evidence", basis, re.I))
        ) and not negative,
        "certification": (
            bool(re.search(r"certification mandate|certification requirements? are triggered", basis, re.I))
            and (regulatory_selected or not has_structured_classification)
            and not negative
        ),
        "external_commitment": (
            external_selected
            if has_structured_classification
            else bool(re.search(r"external(?:ly)? (?:imposed|committed)|mandatory basis", basis, re.I))
        ) and not negative,
        "slt_mandate": (
            external_selected
            if has_structured_classification
            else bool(re.search(r"\bSLT\b", basis, re.I))
        ) and not negative,
        "critical_obsolescence": positive_obsolescence and not negative_obsolescence,
        "major_supply_disruption": positive_supply and not negative_supply,
    }

def classify_cti(data):
    return classification_code(data)

def scope_block(extracted):
    parts = []
    for cells, table_index, row_index in docx_rows(extracted):
        if len(cells) < 2:
            continue
        label = normalized(cells[0])
        if label in {"scope", "in scope", "out of scope", "scope change", "what is the proposed scope change"}:
            value = clean(" ".join(cells[1:]))
            if value:
                parts.append(value)
    if parts:
        return " ".join(dict.fromkeys(parts))
    return heading_block(
        extracted,
        "SCOPE",
        ("BUSINESS CASE", "5. Objective Impact Data"),
    )

def parse_proposal(extracted):
    data = {"engineering_threshold": 160, "model_families": 1, "lifecycle_areas": 1}
    metadata = {}
    warnings = list(extracted.get("warnings", []))

    for field, labels in FIELD_LABELS.items():
        raw, location = get_value(extracted, labels)
        if raw is None:
            continue
        parsed = parse_field_value(field, raw)
        issue = domain_issue(field, parsed)
        if issue:
            warnings.append(f"{field}: extracted value {parsed} {issue}; review required")
            continue
        if parsed is not None and parsed != "":
            if field == "program":
                parsed = normalize_program(parsed)
            data[field] = parsed
            candidates = all_row_values(extracted, labels)
            parsed_candidates = [parse_field_value(field, value) for value, _ in candidates]
            distinct = {str(value) for value in parsed_candidates if value is not None}
            conflict = len(distinct) > 1
            metadata[field] = {
                "raw": raw,
                "normalized": parsed,
                "location": location,
                "source": "table" if location and location.startswith("table") else "document",
                "confidence": 65 if conflict else (95 if extracted.get("file_type") == "docx" else 85),
                "status": "conflict" if conflict else "extracted",
                "candidates": [
                    {"raw": value, "location": candidate_location}
                    for value, candidate_location in candidates
                ],
            }
            if conflict:
                warnings.append(
                    f"Conflicting values found for {field}; selected {parsed} from {location}"
                )

    question_fallbacks = {
        "engineering_hours": ("How many engineering hours", "engineering hours or man-months"),
        "functions_involved": ("Which engineering disciplines", "affected functions"),
        "five_year_npv": ("net-benefit", "net benefit"),
        "target_date": ("implementation timing", "software and publication release"),
    }
    for field, phrases in question_fallbacks.items():
        if data.get(field) not in (None, ""):
            continue
        raw, location = question_value(extracted, phrases)
        if raw is None:
            raw, location = narrative_value(extracted, phrases)
        if raw is None:
            continue
        parsed = money(raw) if field == "five_year_npv" else count_functions(raw) if field == "functions_involved" else number(raw) if field == "engineering_hours" else date_value(raw)
        if parsed is not None:
            data[field] = parsed
            metadata[field] = {
                "raw": raw, "normalized": parsed, "location": location,
                "source": "question" if location and location.startswith("table") else "narrative",
                "confidence": 80, "status": "fallback",
                "candidates": [{"raw": raw, "location": location}],
            }

    objective, evidence = exact_objective_rows(extracted)
    objective_map = {
        "annual aog events": "aog_events",
        "annual prevented deliveries": "prevented_deliveries",
        "annual delivery delays": "delivery_delays",
        "annual line interruptions": "line_interruptions",
        "annual repeat rework events": "repeat_rework",
        "affected fleet percentage": "affected_fleet_pct",
    }
    for label, field in objective_map.items():
        if label in objective:
            parsed = number(objective[label])
            if parsed is not None:
                data[field] = parsed
                metadata[field] = {
                    "raw": objective[label], "normalized": parsed,
                    "location": "Objective Impact Data table", "source": "objective_table",
                    "confidence": 98, "status": "extracted",
                    "candidates": [{"raw": objective[label], "location": "Objective Impact Data table"}],
                }

    data["problem_statement"] = heading_block(extracted, "PROBLEM STATEMENT", ("DESIRED OUTCOME", "CONSEQUENCE OF NO ACTION", "3. CTI Qualification"))
    data["business_case"], _ = row_value(extracted, ("Business Case",))
    if not data["business_case"]:
        data["business_case"] = heading_block(extracted, "BUSINESS CASE", ("Affected Model Families", "5. Objective Impact Data"))
    data["business_case"] = clean(data["business_case"]).lstrip(":|- ").rstrip(".")
    data["scope_change"] = scope_block(extracted)
    for field, value, heading in (
        ("problem_statement", data["problem_statement"], "PROBLEM STATEMENT"),
        ("business_case", data["business_case"], "BUSINESS CASE"),
        ("scope_change", data["scope_change"], "SCOPE"),
    ):
        if value:
            metadata[field] = {
                "raw": value, "normalized": value,
                "location": heading, "source": "narrative",
                "confidence": 90, "status": "extracted", "candidates": [],
            }

    driver_raw, _ = get_value(extracted, ("Requested Driver", "Driver"))
    phase_raw, _ = get_value(extracted, ("Current Phase", "Phase"))
    if not driver_raw:
        driver_raw = extracted.get("text", "")
    if not phase_raw:
        phase_raw = extracted.get("text", "")
    data["driver"] = selected_driver(driver_raw or "")
    data["phase"] = selected_phase(phase_raw or "")
    metadata["driver"] = {
        "raw": driver_raw, "normalized": data["driver"],
        "location": "driver selection", "source": "selection",
        "confidence": 85 if driver_raw else 55,
        "status": "extracted" if driver_raw else "inferred",
        "candidates": [],
    }
    metadata["phase"] = {
        "raw": phase_raw, "normalized": data["phase"],
        "location": "phase selection", "source": "selection",
        "confidence": 85 if phase_raw else 55,
        "status": "extracted" if phase_raw else "inferred",
        "candidates": [],
    }

    data.update(classification_flags(extracted))
    text = extracted.get("text", "")
    cos = re.search(r"(?:COS(?: hazard)?(?: score)?|hazard score)\s*(?:of|[:=])?\s*(\d+(?:\.\d+)?)", text, re.I)
    data["cos_score"] = float(cos.group(1)) if cos else 0
    if data["cos_score"] >= 12:
        data["regulatory"] = data.get("regulatory", False)

    qualification_text = heading_block(extracted, "QUALIFICATION RATIONALE", ("4. Scope", "SCOPE", "BUSINESS CASE"))
    data["cross_functional"] = bool(re.search(r"cross-functional|across (?:multiple|\w+) functions|coordinated", qualification_text, re.I))
    if not data["cross_functional"]:
        data["cross_functional"] = data.get("functions_involved", 0) >= 5
    data["unit_specific"] = False
    data["fast_engineering"] = False
    data["non_ecr"] = False
    metadata["cross_functional"] = {
        "raw": qualification_text, "normalized": data["cross_functional"],
        "location": "qualification rationale", "source": "inference",
        "confidence": 70, "status": "inferred", "candidates": [],
    }

    customer_rows = objective.get("customer commitment escalation", "")
    nearby = text
    escalation_match = re.search(r"(\d+)\s+escalated cases", nearby, re.I)
    data["customer_escalations"] = float(escalation_match.group(1)) if escalation_match else 0
    data["customer_commitment"] = bool(customer_rows and not re.search(r"\bno\b.*commitment", customer_rows, re.I))

    data["evidence_count"] = len(evidence or set(re.findall(r"\bE-\d{2}\b", text, re.I)))
    data["milestone_count"] = count_milestones(extracted)
    data["departments"] = [
        department
        for department in DEPARTMENT_NAMES
        if re.search(r"\b" + re.escape(department) + r"\b", text, re.I)
    ]
    data["ready_milestones"] = data["milestone_count"] > 0
    data["ready_evidence"] = data["evidence_count"] > 0

    readiness_phrases = {
        "ready_owner": "named accountable owner",
        "ready_scope": "problem statement and scope",
        "ready_business_case": "business case completed",
        "ready_estimate": "engineering estimate completed",
        "ready_functions": "required functions identified",
        "ready_dates": "need-by and target dates",
        "ready_approach": "initial technical approach identified",
        "ready_funding": "funding or resource source identified",
    }
    for field, phrase in readiness_phrases.items():
        data[field] = bool(re.search(r"(?:☒|☑|■|✓|✔)\s*" + re.escape(phrase), text, re.I))

    if data.get("affected_fleet_pct") is None and data.get("affected_aircraft") is not None and data.get("active_fleet"):
        data["affected_fleet_pct"] = round(100 * data["affected_aircraft"] / data["active_fleet"], 1)
        metadata["affected_fleet_pct"] = {
            "raw": f"{data['affected_aircraft']} / {data['active_fleet']}",
            "normalized": data["affected_fleet_pct"],
            "location": "derived from affected aircraft and active fleet",
            "source": "inference", "confidence": 75, "status": "inferred",
            "candidates": [],
        }

    classification = classify_cti(data)
    requested_classification = (
        "M1"
        if data.get("regulatory") or data.get("certification")
        else "M2"
        if data.get("external_commitment") or data.get("slt_mandate")
        else "D"
    )
    metadata["classification"] = {
        "raw": requested_classification,
        "normalized": classification,
        "location": "Requested Classification / qualification rules",
        "source": "calculated",
        "confidence": 95,
        "status": "extracted",
        "candidates": [],
    }
    if requested_classification != classification and requested_classification == "M1":
        warnings.append(
            f"Requested classification {requested_classification} differs from calculated classification {classification}; calculated result will be used"
        )

    required = ("title", "program", "need_by", "target_date", "engineering_hours", "five_year_npv", "functions_involved", "aog_events", "delivery_delays", "affected_fleet_pct")
    for field in required:
        if data.get(field) is None or data.get(field) == "":
            warnings.append(f"Required field not found: {field}")
    for field in FIELD_LABELS:
        if field not in metadata:
            metadata[field] = {
                "raw": None, "normalized": data.get(field),
                "location": None, "source": "missing",
                "confidence": 0, "status": "missing", "candidates": [],
            }

    version = "V4.5" if "V4.5 Mock" in text else "V4.1" if "V4.1 Prototype" in text else "CTI proposal"
    review = {
        "uncertain": [field for field, item in metadata.items() if item["confidence"] < 70 and item["status"] != "missing"],
        "inferred": [field for field, item in metadata.items() if item["status"] == "inferred"],
        "missing": [field for field, item in metadata.items() if item["status"] == "missing"],
        "conflicts": [field for field, item in metadata.items() if item["status"] == "conflict"],
    }
    return {
        "data": data, "fields": metadata, "review": review,
        "classification": classification,
        "warnings": list(dict.fromkeys(warnings)),
        "source_type": extracted.get("file_type"), "template_version": version,
    }
