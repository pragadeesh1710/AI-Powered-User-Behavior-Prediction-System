import sqlite3
import os

DATABASE_NAME = os.path.join("/tmp", "database.db")


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            difficulty TEXT DEFAULT 'Beginner',
            duration TEXT DEFAULT 'Self-paced',
            rating REAL DEFAULT 4.5
        )
    """)

    # Safe upgrade for databases created by earlier versions.
    existing = {r["name"] for r in cursor.execute("PRAGMA table_info(courses)").fetchall()}
    for column, definition in [
        ("difficulty", "TEXT DEFAULT 'Beginner'"),
        ("duration", "TEXT DEFAULT 'Self-paced'"),
        ("rating", "REAL DEFAULT 4.5"),
    ]:
        if column not in existing:
            cursor.execute(f"ALTER TABLE courses ADD COLUMN {column} {definition}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_activity (
            activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS course_time (
            time_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            seconds INTEGER NOT NULL DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, course_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            favorite_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, course_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, course_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_course ON user_activity(course_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity(activity_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_user ON search_history(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_user ON course_time(user_id)")

    connection.commit()
    connection.close()
