import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from flask import current_app
from config import DEFAULT_LIFECYCLE_PHASE

SCHEMA_VERSION = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cti_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,
    title TEXT NOT NULL,
    program TEXT,
    driver TEXT,
    phase TEXT,
    lifecycle_phase TEXT NOT NULL DEFAULT 'Phase 1',
    qualification TEXT NOT NULL DEFAULT 'D',
    status TEXT NOT NULL DEFAULT 'Active',
    ops REAL,
    confidence REAL,
    urgency REAL,
    operational REAL,
    customer_fleet REAL,
    financial REAL,
    breadth REAL,
    readiness REAL,
    need_by TEXT,
    target_date TEXT,
    engineering_hours REAL,
    five_year_npv REAL,
    functions_involved REAL,
    aog_events REAL,
    prevented_deliveries REAL,
    delivery_delays REAL,
    line_interruptions REAL,
    repeat_rework REAL,
    affected_fleet_pct REAL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    milestone_count INTEGER NOT NULL DEFAULT 0,
    problem_statement TEXT,
    scope_change TEXT,
    business_case TEXT,
    source_file TEXT,
    source_type TEXT,
    template_version TEXT,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    extraction_json TEXT NOT NULL DEFAULT '{}',
    raw_data_json TEXT NOT NULL DEFAULT '{}',
    scoring_json TEXT NOT NULL DEFAULT '{}',
    confidence_json TEXT NOT NULL DEFAULT '{}',
    archived INTEGER NOT NULL DEFAULT 0,
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cti_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES cti_projects(id)
);
CREATE INDEX IF NOT EXISTS idx_cti_active ON cti_projects(archived, status);
CREATE INDEX IF NOT EXISTS idx_cti_program ON cti_projects(program);
CREATE INDEX IF NOT EXISTS idx_cti_qualification ON cti_projects(qualification);
CREATE INDEX IF NOT EXISTS idx_cti_ops ON cti_projects(ops);
CREATE INDEX IF NOT EXISTS idx_cti_need_by ON cti_projects(need_by);
CREATE TABLE IF NOT EXISTS cti_departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    department TEXT NOT NULL,
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES cti_projects(id)
);
CREATE TABLE IF NOT EXISTS cti_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 1,
    data_json TEXT NOT NULL DEFAULT '{}',
    source_file TEXT,
    source_type TEXT,
    template_version TEXT,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    extraction_json TEXT NOT NULL DEFAULT '{}',
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cti_departments_dept
ON cti_departments(department);
"""

def delete_project(project_id):
    with connection() as conn:
        conn.execute(
            "DELETE FROM cti_history WHERE project_id = ?",
            (project_id,)
        )
        conn.execute(
            "DELETE FROM cti_departments WHERE project_id = ?",
            (project_id,)
        )
        conn.execute(
            "DELETE FROM cti_projects WHERE id = ?",
            (project_id,)
        )
def database_path(app=None):
    app = app or current_app
    configured = app.config.get('CTI_DATABASE')
    path = Path(configured) if configured else Path(app.instance_path) / 'cti.db'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect(app=None):
    conn = sqlite3.connect(database_path(app))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


@contextmanager
def connection(app=None):
    conn = connect(app)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(app):
    with app.app_context():
        with connection(app) as conn:
            conn.executescript(SCHEMA)
            _migrate_schema(conn)
            row = conn.execute('SELECT version FROM schema_version LIMIT 1').fetchone()
            if row is None:
                conn.execute('INSERT INTO schema_version(version) VALUES (?)', (SCHEMA_VERSION,))
            elif row["version"] < SCHEMA_VERSION:
                conn.execute('UPDATE schema_version SET version = ?', (SCHEMA_VERSION,))
            _backfill_departments(conn)


def _migrate_schema(conn):
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(cti_projects)").fetchall()
    }
    if "lifecycle_phase" not in columns:
        conn.execute(
            "ALTER TABLE cti_projects ADD COLUMN lifecycle_phase TEXT NOT NULL DEFAULT 'Phase 1'"
        )
    if "scope_change" not in columns:
        conn.execute(
            "ALTER TABLE cti_projects ADD COLUMN scope_change TEXT"
        )
    conn.execute(
        """
        UPDATE cti_projects
        SET lifecycle_phase = 'Phase 1'
        WHERE lifecycle_phase IS NULL OR TRIM(lifecycle_phase) = ''
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cti_lifecycle_phase ON cti_projects(lifecycle_phase)"
    )
    project_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(cti_projects)").fetchall()
    }
    if "extraction_json" not in project_columns:
        conn.execute(
            "ALTER TABLE cti_projects ADD COLUMN extraction_json TEXT NOT NULL DEFAULT '{}'"
        )
    draft_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(cti_drafts)").fetchall()
    }
    if "extraction_json" not in draft_columns:
        conn.execute(
            "ALTER TABLE cti_drafts ADD COLUMN extraction_json TEXT NOT NULL DEFAULT '{}'"
        )


def _backfill_departments(conn):
    rows = conn.execute(
        "SELECT id, raw_data_json FROM cti_projects"
    ).fetchall()
    for row in rows:
        try:
            data = json.loads(row["raw_data_json"] or "{}")
        except (TypeError, ValueError):
            continue
        departments = data.get("departments", [])
        for department in dict.fromkeys(
            str(value).strip()
            for value in departments
            if str(value).strip()
        ):
            exists = conn.execute(
                """
                SELECT 1
                FROM cti_departments
                WHERE project_id = ? AND department = ?
                """,
                (row["id"], department),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO cti_departments (project_id, department)
                    VALUES (?, ?)
                    """,
                    (row["id"], department),
                )


def _json(value):
    return json.dumps({} if value is None else value, default=str, ensure_ascii=False)


def create_draft(token, data=None, current_step=1, source=None, warnings=None, extraction=None):
    source = source or {}
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO cti_drafts
            (token, current_step, data_json, source_file, source_type,
             template_version, warnings_json, extraction_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (token, current_step, _json(data), source.get("file_name"),
             source.get("source_type"), source.get("template_version"),
             _json(warnings or []), _json(extraction or {})),
        )


def fetch_draft(token):
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM cti_drafts WHERE token = ?", (token,)
        ).fetchone()
    if not row:
        return None
    draft = dict(row)
    draft["data"] = json.loads(draft.pop("data_json") or "{}")
    draft["warnings"] = json.loads(draft.pop("warnings_json") or "[]")
    draft["extraction"] = json.loads(draft.pop("extraction_json") or "{}")
    return draft


def save_draft(token, data, current_step, source=None, warnings=None, extraction=None):
    source = source or {}
    with connection() as conn:
        conn.execute(
            """
            UPDATE cti_drafts
            SET current_step = ?, data_json = ?, source_file = COALESCE(?, source_file),
                source_type = COALESCE(?, source_type),
                template_version = COALESCE(?, template_version),
                warnings_json = ?, extraction_json = ?, modified_utc = CURRENT_TIMESTAMP
            WHERE token = ?
            """,
            (current_step, _json(data), source.get("file_name"),
             source.get("source_type"), source.get("template_version"),
             _json(warnings or []), _json(extraction or {}), token),
        )


def delete_draft(token):
    with connection() as conn:
        conn.execute("DELETE FROM cti_drafts WHERE token = ?", (token,))


def save_project(
    data,
    qualification=None,
    scoring=None,
    confidence=None,
    source=None,
    warnings=None,
    extraction=None
):

    qualification = qualification or {}
    scoring = scoring or {}
    confidence = confidence or {}
    source = source or {}

    factors = scoring.get("factors") or {}

    def factor(name):

        value = factors.get(name, 0)

        if isinstance(value, dict):
            return value.get("score")

        return value

    tier = (
        qualification.get("code")
        or qualification.get("tier")
        or data.get("qualification")
        or "D"
    )

    tier = str(tier).upper()

    if tier not in {"M1", "M2", "D"}:
        tier = "D"

    values = {
        "external_id": data.get("external_id"),
        "title": data.get("title") or "Untitled CTI",
        "program": data.get("program"),
        "driver": data.get("driver"),
        "phase": data.get("phase"),
        "lifecycle_phase": data.get("lifecycle_phase") or DEFAULT_LIFECYCLE_PHASE,
        "qualification": tier,
        "status": data.get("status") or "Active",
        "ops": scoring.get("ops", data.get("ops")),
        "confidence": confidence.get(
            "score",
            data.get("confidence")
        ),
        "urgency": factor("urgency"),
        "operational": factor("operational"),
        "customer_fleet": factor("customer_fleet"),
        "financial": factor("financial"),
        "breadth": factor("breadth"),
        "readiness": factor("readiness"),
        "need_by": data.get("need_by"),
        "target_date": data.get("target_date"),
        "engineering_hours": data.get("engineering_hours"),
        "five_year_npv": data.get("five_year_npv"),
        "functions_involved": data.get("functions_involved"),
        "aog_events": data.get("aog_events"),
        "prevented_deliveries": data.get("prevented_deliveries"),
        "delivery_delays": data.get("delivery_delays"),
        "line_interruptions": data.get("line_interruptions"),
        "repeat_rework": data.get("repeat_rework"),
        "affected_fleet_pct": data.get("affected_fleet_pct"),
        "evidence_count": int(
            data.get("evidence_count") or 0
        ),
        "milestone_count": int(
            data.get("milestone_count") or 0
        ),
        "problem_statement":
            data.get("problem_statement"),
        "scope_change":
            data.get("scope_change"),
        "business_case":
            data.get("business_case"),
        "source_file":
            source.get("file_name"),
        "source_type":
            source.get("source_type"),
        "template_version":
            source.get("template_version"),
        "warnings_json":
            _json(warnings or []),
        "raw_data_json":
            _json(data),
        "scoring_json":
            _json(scoring),
        "confidence_json":
            _json(confidence),
        "extraction_json":
            _json(extraction or {}),
    }

    with connection() as conn:

        #
        # DUPLICATE CHECK
        #

        duplicate = conn.execute(
            """
            SELECT id
            FROM cti_projects
            WHERE title = ?
              AND IFNULL(program,'') = IFNULL(?, '')
              AND IFNULL(need_by,'') = IFNULL(?, '')
            """,
            (
                data.get("title"),
                data.get("program"),
                data.get("need_by")
            )
        ).fetchone()

        if duplicate:
            conn.execute(
                """
                UPDATE cti_projects
                SET lifecycle_phase = ?, extraction_json = ?,
                    modified_utc = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    data.get("lifecycle_phase") or DEFAULT_LIFECYCLE_PHASE,
                    _json(extraction or {}),
                    duplicate["id"],
                ),
            )
            save_departments(
                conn,
                duplicate["id"],
                data.get("departments", []),
            )
            return duplicate["id"]

        columns = ",".join(values.keys())

        marks = ",".join(
            "?"
            for _ in values
        )

        cur = conn.execute(
            f"""
            INSERT INTO cti_projects
            ({columns})
            VALUES
            ({marks})
            """,
            tuple(values.values())
        )

        project_id = cur.lastrowid

        save_departments(
            conn,
            project_id,
            data.get(
                "departments",
                []
            )
        )

        conn.execute(
            """
            INSERT INTO cti_history
            (
                project_id,
                action,
                details_json
            )
            VALUES
            (?,?,?)
            """,
            (
                project_id,
                "created",
                _json(
                    {
                        "source": source,
                        "departments": data.get(
                            "departments",
                            []
                        )
                    }
                )
            )
        )

    return project_id
def fetch_projects(include_archived=False):
    sql = 'SELECT * FROM cti_projects'
    params = []
    if not include_archived:
        sql += ' WHERE archived = 0'
    sql += ' ORDER BY created_utc DESC, id DESC'
    with connection() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_project(project_id):
    with connection() as conn:
        row = conn.execute('SELECT * FROM cti_projects WHERE id=?', (project_id,)).fetchone()
        return dict(row) if row else None


def set_archived(project_id, archived):
    with connection() as conn:
        conn.execute('UPDATE cti_projects SET archived=?, modified_utc=CURRENT_TIMESTAMP WHERE id=?', (1 if archived else 0, project_id))
        conn.execute('INSERT INTO cti_history(project_id, action, details_json) VALUES (?,?,?)',
                     (project_id, 'archived' if archived else 'restored', '{}'))


def update_lifecycle_phase(project_id, lifecycle_phase):
    with connection() as conn:
        conn.execute(
            """
            UPDATE cti_projects
            SET lifecycle_phase = ?, modified_utc = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (lifecycle_phase, project_id),
        )
        conn.execute(
            """
            INSERT INTO cti_history(project_id, action, details_json)
            VALUES (?, ?, ?)
            """,
            (project_id, "lifecycle_phase_updated", _json({"lifecycle_phase": lifecycle_phase})),
        )


def update_project(
    project_id,
    data,
    qualification,
    scoring,
    confidence,
):
    qualification = qualification or {}
    scoring = scoring or {}
    confidence = confidence or {}

    factors = scoring.get("factors") or {}

    def factor(name):
        value = factors.get(name, 0)
        return value.get("score") if isinstance(value, dict) else value

    values = {
        "title": data.get("title") or "Untitled CTI",
        "program": data.get("program"),
        "driver": data.get("driver"),
        "phase": data.get("phase"),
        "lifecycle_phase": data.get("lifecycle_phase") or DEFAULT_LIFECYCLE_PHASE,
        "status": data.get("status") or "Active",
        "qualification": qualification.get("code", "D"),
        "ops": scoring.get("ops"),
        "confidence": confidence.get("score"),
        "urgency": factor("urgency"),
        "operational": factor("operational"),
        "customer_fleet": factor("customer_fleet"),
        "financial": factor("financial"),
        "breadth": factor("breadth"),
        "readiness": factor("readiness"),
        "need_by": data.get("need_by"),
        "target_date": data.get("target_date"),
        "engineering_hours": data.get("engineering_hours"),
        "five_year_npv": data.get("five_year_npv"),
        "functions_involved": data.get("functions_involved"),
        "aog_events": data.get("aog_events"),
        "prevented_deliveries": data.get("prevented_deliveries"),
        "delivery_delays": data.get("delivery_delays"),
        "line_interruptions": data.get("line_interruptions"),
        "repeat_rework": data.get("repeat_rework"),
        "affected_fleet_pct": data.get("affected_fleet_pct"),
        "evidence_count": int(data.get("evidence_count") or 0),
        "milestone_count": int(data.get("milestone_count") or 0),
        "problem_statement": data.get("problem_statement"),
        "business_case": data.get("business_case"),
        "raw_data_json": _json(data),
        "scoring_json": _json(scoring),
        "confidence_json": _json(confidence),
    }

    assignments = ", ".join(f"{column} = ?" for column in values)
    with connection() as conn:
        before = conn.execute(
            "SELECT * FROM cti_projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not before:
            return False
        changed = {
            key: value for key, value in values.items()
            if str(before[key]) != str(value)
        }
        conn.execute(
            f"""
            UPDATE cti_projects
            SET {assignments}, modified_utc = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (*values.values(), project_id),
        )
        conn.execute(
            "DELETE FROM cti_departments WHERE project_id = ?", (project_id,)
        )
        save_departments(conn, project_id, data.get("departments", []))
        conn.execute(
            """
            INSERT INTO cti_history(project_id, action, details_json)
            VALUES (?, ?, ?)
            """,
            (project_id, "updated", _json({"fields": sorted(changed)})),
        )
    return True


def fetch_project_history(project_id):
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM cti_history
            WHERE project_id = ?
            ORDER BY id DESC
            """,
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def fetch_project_departments(project_id):
    with connection() as conn:
        rows = conn.execute(
            "SELECT department FROM cti_departments WHERE project_id = ? ORDER BY department",
            (project_id,),
        ).fetchall()
        return [row["department"] for row in rows]


def save_departments(
    conn,
    project_id,
    departments
):

    for department in dict.fromkeys(
        str(value).strip() for value in (departments or []) if str(value).strip()
    ):

        conn.execute(
            """
            INSERT OR IGNORE INTO
            cti_departments
            (
                project_id,
                department
            )
            VALUES
            (?,?)
            """,
            (
                project_id,
                department
            )
        )

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
