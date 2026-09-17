@phase2_bp.get('/resources')
def resources():
    return render_template('phase2/resources.html', departments=fetch_departments())

@phase2_bp.get('/resources/<department>')
def department_view(department):
    return render_template('phase2/department.html', department=department, projects=projects_by_department(department))
