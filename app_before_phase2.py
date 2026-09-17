from pathlib import Path
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from document_reader import read_document, DocumentReadError
from proposal_parser import parse_proposal
from qualification import calculate_qualification
from scoring import calculate_all_scores, priority_tier
from confidence import calculate_confidence

app=Flask(__name__); app.secret_key="cti-v482-local-prototype"; app.config["MAX_CONTENT_LENGTH"]=MAX_UPLOAD_BYTES
UPLOAD=Path(__file__).parent/"uploads"; UPLOAD.mkdir(exist_ok=True)
BOOL_FIELDS={"regulatory","certification","external_commitment","slt_mandate","delivery_prevention","critical_obsolescence","major_supply_disruption","unit_specific","fast_engineering","non_ecr","cross_functional","customer_commitment","ready_owner","ready_scope","ready_business_case","ready_estimate","ready_functions","ready_dates","ready_approach","ready_funding","ready_milestones","ready_evidence"}
NUM_FIELDS={"implementation_lead_days","engineering_hours","engineering_threshold","cos_score","prevented_deliveries","aog_events","delivery_delays","line_interruptions","repeat_rework","affected_fleet_pct","customer_escalations","five_year_npv","functions_involved","model_families","lifecycle_areas","evidence_count","milestone_count"}
ALL_FIELDS=["title","program","driver","phase","owner","problem_statement","business_case","need_by","target_date"]+sorted(NUM_FIELDS)+sorted(BOOL_FIELDS)

def form_data(form):
    d={}
    for k in ALL_FIELDS:
        if k in BOOL_FIELDS: d[k]=form.get(k)=="yes"
        elif k in NUM_FIELDS:
            try: d[k]=float(form.get(k) or 0)
            except ValueError: d[k]=0
        else: d[k]=(form.get(k) or "").strip()
    return d

def render_result(data,extraction=None):
    q=calculate_qualification(data); s=calculate_all_scores(data); c=calculate_confidence(data,extraction); tier=priority_tier(s["ops"],q["code"])
    return render_template("results.html",data=data,qualification=q,scoring=s,confidence=c,tier=tier,extraction=extraction)

@app.route("/",methods=["GET","POST"])
def index():
    if request.method=="POST": return render_result(form_data(request.form))
    return render_template("intake.html",data={"engineering_threshold":160,"model_families":1,"lifecycle_areas":1})

@app.route("/upload",methods=["GET","POST"])
def upload():
    if request.method=="GET": return render_template("upload.html")
    f=request.files.get("proposal")
    if not f or not f.filename: flash("Choose a DOCX or PDF proposal.","error"); return redirect(url_for("upload"))
    ext=Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS: flash("Only .docx and .pdf files are supported.","error"); return redirect(url_for("upload"))
    name=f"{uuid4().hex}_{secure_filename(f.filename)}"; path=UPLOAD/name; f.save(path)
    try: parsed=parse_proposal(read_document(path))
    except DocumentReadError as exc: flash(str(exc),"error"); return redirect(url_for("upload"))
    finally:
        try: path.unlink()
        except OSError: pass
    return render_template("review.html",data=parsed["data"],extraction=parsed)

@app.route("/calculate-upload",methods=["POST"])
def calculate_upload():
    data=form_data(request.form); warnings=[x for x in request.form.getlist("extraction_warning") if x]
    return render_result(data,{"warnings":warnings,"source_type":request.form.get("source_type","")})

@app.route("/health")
def health(): return {"status":"ok","version":"4.8.2","document_intake":True}
if __name__=="__main__": app.run(debug=True)
