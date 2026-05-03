# database.py
import sqlite3
import math

DB_PATH = "contact.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            status TEXT DEFAULT 'Incomplete',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            node TEXT NOT NULL,
            error_type TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    conn.commit()
    conn.close()


def save_session(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (session_id, status) VALUES (?, 'Incomplete')",
        (session_id,)
    )
    conn.commit()
    conn.close()


def save_chat(session_id: str, sender: str, message: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chats (session_id, sender, message) VALUES (?, ?, ?)",
        (session_id, sender, message)
    )
    conn.commit()
    conn.close()


def save_error(session_id: str, node: str, error_type: str, message: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO errors (session_id, node, error_type, message) VALUES (?, ?, ?, ?)",
        (session_id, node, error_type, message)
    )
    conn.commit()
    conn.close()


def save_contact(session_id: str, name: str, email: str, phone: str, message: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO contacts (session_id, name, email, phone, message) VALUES (?, ?, ?, ?, ?)",
        (session_id, name, email, phone, message)
    )
    # The only UPDATE in the entire system
    cursor.execute(
        "UPDATE sessions SET status='Completed' WHERE session_id = ?",
        (session_id,)
    )
    conn.commit()
    conn.close()


def get_sessions(page: int = 1, limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()

    offset = (page - 1) * limit

    cursor.execute("SELECT COUNT(*) FROM sessions")
    total = cursor.fetchone()[0]
    total_pages = math.ceil(total / limit) if total > 0 else 1

    cursor.execute(
        "SELECT session_id, status, created_at FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = cursor.fetchall()
    conn.close()

    return {
        "sessions": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


def get_conversation(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, message, timestamp FROM chats WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_errors(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT node, error_type, message, timestamp FROM errors WHERE session_id = ?",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_details(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, email, phone, message FROM contacts WHERE session_id = ?",
        (session_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None