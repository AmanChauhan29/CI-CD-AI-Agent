import sqlite3

DB_NAME = "incidents.db"


def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id TEXT,

            workflow_name TEXT,

            category TEXT,

            matched_pattern TEXT,

            file_name TEXT,

            snippet TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            incident_id INTEGER,

            root_cause TEXT,

            suggested_fix TEXT,

            confidence REAL,

            raw_response TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (incident_id)
            REFERENCES incidents(id)
        )
        """)
    conn.commit()
    conn.close()