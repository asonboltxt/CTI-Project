def calculate_confidence(data, extraction=None):
    checks=[(bool(data.get("title")),"CTI title"),(bool(data.get("program")),"model / program"),(bool(data.get("owner")),"accountable owner"),(bool(data.get("problem_statement")),"problem statement"),(bool(data.get("business_case")),"business case"),(bool(data.get("need_by")),"need-by date"),(bool(data.get("target_date")),"target date"),((data.get("engineering_hours") or 0)>0,"engineering estimate"),((data.get("evidence_count") or 0)>0,"supporting evidence"),((data.get("milestone_count") or 0)>0,"milestone schedule")]
    missing=[label for ok,label in checks if not ok]; score=sum(ok for ok,_ in checks)*10
    warnings=[]
    if extraction:
        warnings=list(extraction.get("warnings",[]))
        score=max(0,score-min(20,5*len(warnings)))
    return {"score":score,"missing":missing,"warnings":warnings}
