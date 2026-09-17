CREATE TABLE IF NOT EXISTS cti_departments (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project_id INTEGER NOT NULL,
 department TEXT NOT NULL,
 created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(project_id) REFERENCES cti_projects(id)
);
CREATE INDEX IF NOT EXISTS idx_cti_departments_dept ON cti_departments(department);
