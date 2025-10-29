
import sqlite3

def init_db():
    conn = sqlite3.connect('matches.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        image TEXT,
        status TEXT,
        category TEXT,
        start_time TEXT,
        m3u8_link TEXT
    )""")
    conn.commit()
    conn.close()
