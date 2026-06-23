from database.db import get_connection
from datetime import datetime

def save_incident(run_id, workflow_name, classification):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO incidents(
            run_id,
            workflow_name,
            category,
            matched_pattern,
            file_name,
            snippet
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            workflow_name,
            classification["category"],
            classification["matched_pattern"],
            classification["file"],
            classification["snippet"]
        )
    )
    incident_id = cursor.lastrowid

    print("saved incident to database")

    conn.commit()
    conn.close()

    return incident_id

def mark_incident_resolved(
    incident_id,
    pr_number,
    workflow_run_id
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE incidents
        SET
            status = ?,
            resolution_type = ?,
            pr_number = ?,
            resolved_workflow_run = ?,
            resolved_at = ?
        WHERE id = ?
        """,
        (
            "resolved",
            "auto_remediation",
            pr_number,
            workflow_run_id,
            datetime.utcnow().isoformat(),
            incident_id
        )
    )

    conn.commit()
    conn.close()

    print(
        f"Incident {incident_id} marked as resolved"
    )