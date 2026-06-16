import sqlite3
import json
from pathlib import Path
from config import DB_PATH, SUBMISSION_DIR


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT,
            grade INTEGER,
            department TEXT,
            trip_purpose TEXT,
            title TEXT,
            manager_id TEXT,
            home_base TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            receipt_name TEXT,
            review_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Override table for audit trail
    conn.execute("""
        CREATE TABLE IF NOT EXISTS overrides (
            override_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            original_verdict TEXT,
            new_verdict TEXT,
            comment TEXT NOT NULL,
            overridden_by TEXT DEFAULT 'manager',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES submissions(submission_id)
        )
    """)

    conn.commit()
    conn.close()


def load_seed_employees():
    conn = get_connection()

    for folder in Path(SUBMISSION_DIR).iterdir():
        if not folder.is_dir():
            continue

        employee_file = folder / "employee_info.json"

        if not employee_file.exists():
            continue

        with open(employee_file, "r", encoding="utf-8") as f:
            employee = json.load(f)

        conn.execute("""
            INSERT OR REPLACE INTO employees (
                employee_id,
                name,
                grade,
                department,
                trip_purpose,
                title,
                manager_id,
                home_base
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            employee.get("employee_id"),
            employee.get("name"),
            employee.get("grade"),
            employee.get("department"),
            employee.get("trip_purpose"),
            employee.get("title", ""),
            employee.get("manager_id", ""),
            employee.get("home_base", ""),
        ))

    conn.commit()
    conn.close()


def get_employees():
    conn = get_connection()
    employees = conn.execute("""
        SELECT * FROM employees ORDER BY name
    """).fetchall()
    conn.close()
    return [dict(row) for row in employees]


def get_employee(employee_id):
    conn = get_connection()
    employee = conn.execute("""
        SELECT * FROM employees WHERE employee_id = ?
    """, (employee_id,)).fetchone()
    conn.close()
    return dict(employee) if employee else None


def create_employee(employee_id, name, grade, department,
                    trip_purpose="", title="", manager_id="", home_base=""):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO employees
            (employee_id, name, grade, department, trip_purpose, title, manager_id, home_base)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (employee_id, name, grade, department, trip_purpose, title, manager_id, home_base))
    conn.commit()
    conn.close()


def save_submission(employee_id, receipt_name, review_data):
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO submissions (employee_id, receipt_name, review_json)
        VALUES (?, ?, ?)
    """, (employee_id, receipt_name, json.dumps(review_data)))
    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return submission_id


def get_submissions():
    conn = get_connection()
    submissions = conn.execute("""
        SELECT s.*, e.name AS employee_name
        FROM submissions s
        LEFT JOIN employees e ON s.employee_id = e.employee_id
        ORDER BY s.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in submissions]


def get_submission(submission_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT s.*, e.name AS employee_name
        FROM submissions s
        LEFT JOIN employees e ON s.employee_id = e.employee_id
        WHERE s.submission_id = ?
    """, (submission_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_override(submission_id, original_verdict, new_verdict, comment, overridden_by="manager"):
    conn = get_connection()
    conn.execute("""
        INSERT INTO overrides
            (submission_id, original_verdict, new_verdict, comment, overridden_by)
        VALUES (?, ?, ?, ?, ?)
    """, (submission_id, original_verdict, new_verdict, comment, overridden_by))
    conn.commit()
    conn.close()


def get_overrides(submission_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM overrides
        WHERE submission_id = ?
        ORDER BY created_at DESC
    """, (submission_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_overrides():
    conn = get_connection()
    rows = conn.execute("""
        SELECT o.*, s.receipt_name, e.name AS employee_name
        FROM overrides o
        JOIN submissions s ON o.submission_id = s.submission_id
        LEFT JOIN employees e ON s.employee_id = e.employee_id
        ORDER BY o.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]
