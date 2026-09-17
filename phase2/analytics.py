from collections import Counter
from datetime import date, datetime


def portfolio_metrics(projects):
    records = list(projects)
    active = [p for p in records if not p.get('archived')]
    scores = [float(p['ops']) for p in active if p.get('ops') is not None and p.get('qualification') == 'D']
    confidences = [float(p['confidence']) for p in active if p.get('confidence') is not None]
    score_groups = Counter(round(float(p['ops']), 4) for p in active if p.get('ops') is not None and p.get('qualification') == 'D')
    tie_projects = sum(n for n in score_groups.values() if n > 1)
    largest_tie = max(score_groups.values(), default=0)
    return {
        'total': len(active), 'm1': sum(p.get('qualification') == 'M1' for p in active),
        'm2': sum(p.get('qualification') == 'M2' for p in active),
        'd': sum(p.get('qualification') == 'D' for p in active),
        'avg_ops': round(sum(scores)/len(scores), 1) if scores else None,
        'avg_confidence': round(sum(confidences)/len(confidences), 1) if confidences else None,
        'missing_need_by': sum(not p.get('need_by') for p in active),
        'missing_target': sum(not p.get('target_date') for p in active),
        'low_confidence': sum(p.get('confidence') is not None and float(p['confidence']) < 70 for p in active),
        'no_evidence': sum(int(p.get('evidence_count') or 0) == 0 for p in active),
        'tie_projects': tie_projects, 'largest_tie': largest_tie,
    }


def review_reasons(project):

    reasons = []

    if not project.get("need_by"):

        reasons.append(
            "Missing need-by date"
        )

    if not project.get("target_date"):

        reasons.append(
            "Missing target date"
        )

    confidence = project.get(
        "confidence"
    )

    if isinstance(
        confidence,
        dict
    ):
        confidence = confidence.get(
            "score"
        )

    try:

        if (
            confidence is not None
            and float(confidence) < 70
        ):

            reasons.append(
                "Confidence below 70"
            )

    except (
        ValueError,
        TypeError
    ):
        pass

    if int(
        project.get(
            "evidence_count",
            0
        )
    ) == 0:

        reasons.append(
            "No evidence IDs stored"
        )

    return reasons