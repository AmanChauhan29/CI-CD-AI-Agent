from database.db import get_connection

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