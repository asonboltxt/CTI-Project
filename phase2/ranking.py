from collections import defaultdict
from datetime import date


def _date_key(value):
    return value or '9999-12-31'


def _score(value):
    return float(value) if value is not None else -1.0


def ranked_projects(projects):
    records = [dict(p) for p in projects]
    mandatory = [p for p in records if p.get('qualification') in ('M1','M2')]
    discretionary = [p for p in records if p.get('qualification') not in ('M1','M2')]
    mandatory.sort(key=lambda p: (0 if p.get('qualification') == 'M1' else 1, _date_key(p.get('need_by')), p.get('title') or ''))
    discretionary.sort(key=lambda p: (-_score(p.get('ops')), -_score(p.get('confidence')), _date_key(p.get('need_by')), p.get('title') or ''))
    ordered = mandatory + discretionary
    for i, p in enumerate(ordered, 1): p['company_rank'] = i

    groups = defaultdict(list)
    for p in ordered: groups[p.get('program') or 'Unassigned'].append(p)
    for group in groups.values():
        m = [p for p in group if p.get('qualification') in ('M1','M2')]
        d = [p for p in group if p.get('qualification') not in ('M1','M2')]
        m.sort(key=lambda p: (0 if p.get('qualification') == 'M1' else 1, _date_key(p.get('need_by')), p.get('title') or ''))
        d.sort(key=lambda p: (-_score(p.get('ops')), -_score(p.get('confidence')), _date_key(p.get('need_by')), p.get('title') or ''))
        for i, p in enumerate(m + d, 1): p['model_rank'] = i
    return ordered
