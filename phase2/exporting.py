import csv
import io
from flask import Response

FIELDS = ['company_rank','model_rank','id','qualification','program','title','driver','phase','ops','confidence','need_by','target_date','engineering_hours','five_year_npv','evidence_count','milestone_count','status','created_utc','modified_utc']

def csv_response(projects):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(projects)
    return Response(stream.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=cti_portfolio.csv'})
