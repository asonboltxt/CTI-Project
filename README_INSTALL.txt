CTI Model and Resource Ranked-List Update

FILES TO REPLACE
1. C:\CTI_V482\phase2\templates\phase2\models.html
2. C:\CTI_V482\phase2\templates\phase2\resources.html

CODE TO MERGE
3. In phase2\routes.py, replace the current resources() and models() functions with the functions from routes_model_resource_update.py.
4. In phase2\database.py, replace fetch_departments(), projects_by_department(), fetch_models(), and projects_by_model() with the functions from database_model_resource_update.py.
5. Append model_resource_styles.css to the end of static\style.css.

REQUIRED IMPORTS IN phase2\routes.py
- request and render_template from flask
- fetch_departments, fetch_models, fetch_projects, projects_by_department, projects_by_model from .database
- ranked_projects from .ranking

VALIDATE
cd C:\CTI_V482
.\.venv\Scripts\python.exe -m py_compile phase2\routes.py phase2\database.py app.py
.\.venv\Scripts\python.exe app.py

TEST
- http://127.0.0.1:5000/models
- http://127.0.0.1:5000/models?program=Citation%20Longitude%20(Model%20700)
- http://127.0.0.1:5000/resources
