# In phase2/database.py, replace your existing four functions with these versions.


def fetch_departments():
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                d.department,
                COUNT(DISTINCT d.project_id) AS ctis
            FROM cti_departments d
            JOIN cti_projects p
              ON p.id = d.project_id
            WHERE p.archived = 0
            GROUP BY d.department
            ORDER BY ctis DESC, d.department ASC
            """
        ).fetchall()

        return [dict(row) for row in rows]


def projects_by_department(department):
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT p.*
            FROM cti_projects p
            JOIN cti_departments d
              ON p.id = d.project_id
            WHERE d.department = ?
              AND p.archived = 0
            ORDER BY p.id DESC
            """,
            (department,),
        ).fetchall()

        return [dict(row) for row in rows]


def fetch_models():
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT
                TRIM(program) AS program,
                COUNT(*) AS ctis
            FROM cti_projects
            WHERE archived = 0
              AND program IS NOT NULL
              AND TRIM(program) <> ''
            GROUP BY TRIM(program)
            ORDER BY TRIM(program) ASC
            """
        ).fetchall()

        return [dict(row) for row in rows]


def projects_by_model(program):
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM cti_projects
            WHERE archived = 0
              AND TRIM(program) = TRIM(?)
            ORDER BY id DESC
            """,
            (program,),
        ).fetchall()

        return [dict(row) for row in rows]
