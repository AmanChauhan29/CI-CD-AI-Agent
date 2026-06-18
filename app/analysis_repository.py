from database.db import get_connection


def save_analysis(
    incident_id,
    analysis
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO analyses(
            incident_id,
            root_cause,
            suggested_fix,
            confidence,
            raw_response
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            analysis["root_cause"],
            analysis["suggested_fix"],
            analysis["confidence"],
            str(analysis)
        )
    )

    conn.commit()
    conn.close()

    print("saved analysis to database")