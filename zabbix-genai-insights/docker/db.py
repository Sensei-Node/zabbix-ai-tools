import sqlite3
import os
import json

DB_PATH = "/app/data/genai_insights.db"

def get_db_conn():
    """Returns a database connection with WAL mode enabled for concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    """Initializes the database schema."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insights (
            event_id TEXT PRIMARY KEY,
            insight TEXT,
            raw_data TEXT,
            status TEXT DEFAULT 'COMPLETED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Check if status column exists (for upgrades)
    cursor.execute("PRAGMA table_info(insights)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute("ALTER TABLE insights ADD COLUMN status TEXT DEFAULT 'COMPLETED'")
    
    conn.commit()
    conn.close()

def prune_old_outputs(max_outputs):
    """Prune oldest outputs if limit is reached."""
    if max_outputs <= 0:
        return []

    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM insights")
    count = cursor.fetchone()[0]
    
    deleted_ids = []
    if count >= max_outputs:
        to_delete = (count - max_outputs) + 1
        cursor.execute("SELECT event_id FROM insights ORDER BY created_at ASC LIMIT ?", (to_delete,))
        deleted_ids = [row[0] for row in cursor.fetchall()]
        
        for oid in deleted_ids:
            cursor.execute("DELETE FROM insights WHERE event_id = ?", (oid,))
        conn.commit()
    conn.close()
    return deleted_ids

def save_pending_insight(event_id, raw_data):
    """Inserts a pending insight into the database."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO insights (event_id, insight, raw_data, status) VALUES (?, ?, ?, ?)",
        (event_id, "Processing insight...", json.dumps(raw_data), "PENDING")
    )
    conn.commit()
    conn.close()

def update_insight_status(event_id, insight, status):
    """Updates an existing insight with analysis results and status."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE insights SET insight = ?, status = ? WHERE event_id = ?",
        (insight, status, event_id)
    )
    conn.commit()
    conn.close()

def list_all_insights():
    """Retrieves all insights ordered by creation date."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT event_id, created_at, insight, raw_data, status FROM insights ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_insight_by_id(event_id):
    """Retrieves a specific insight by its ID."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT insight, status FROM insights WHERE event_id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    return row
