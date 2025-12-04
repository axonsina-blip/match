import sqlite3
import os

# Define the path for the database in the instance folder
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptv.db')

def init_db():
    """Initializes the database and creates/updates tables."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # TV Channels Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tv_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                logo TEXT,
                cookie TEXT,
                category TEXT,
                referer TEXT,
                origin TEXT
            )
        ''')
        try:
            # Ensure cookie column exists from older versions
            cursor.execute("ALTER TABLE tv_channels ADD COLUMN cookie TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE tv_channels ADD COLUMN category TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE tv_channels ADD COLUMN referer TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE tv_channels ADD COLUMN origin TEXT;")
        except sqlite3.OperationalError:
            pass

        # Sports Matches Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sports_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                image TEXT,
                status TEXT,
                category TEXT,
                start_time TEXT,
                m3u8_link TEXT
            )
        ''')
            
        conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

def update_channels(channels):
    """Deletes all existing channels and replaces them with a new list."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("BEGIN TRANSACTION;")
        
        insert_query = "INSERT OR REPLACE INTO tv_channels (name, url, logo, category, referer, origin) VALUES (?, ?, ?, ?, ?, ?);"
        channels_to_insert = [
            (ch.get('name'), ch.get('url'), ch.get('logo'), ch.get('category', 'Live TV'), ch.get('referer'), ch.get('origin'))
            for ch in channels if ch.get('name') and ch.get('url')
        ]
        
        cursor.executemany(insert_query, channels_to_insert)
        conn.commit()
        print(f"Successfully updated database with {len(channels_to_insert)} TV channels.")
        
    except sqlite3.Error as e:
        print(f"Database error during channel update: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def get_all_channels():
    """Retrieves all TV channels from the database."""
    channels = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, url, logo, category, referer, origin FROM tv_channels;")
        rows = cursor.fetchall()
        
        channels = [dict(row) for row in rows]
        
    except sqlite3.Error as e:
        print(f"Database error while fetching channels: {e}")
    finally:
        if conn:
            conn.close()
            
    return channels

def get_channel_by_id(channel_id):
    """Retrieves a single TV channel by its ID."""
    channel = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, url, logo, category, referer, origin FROM tv_channels WHERE id = ?;", (channel_id,))
        row = cursor.fetchone()
        if row:
            channel = dict(row)
            
    except sqlite3.Error as e:
        print(f"Database error while fetching channel by ID: {e}")
    finally:
        if conn:
            conn.close()
            
    return channel

def update_matches(matches):
    """Deletes all existing matches and replaces them with a new list."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("DELETE FROM sports_matches;")
        
        insert_query = "INSERT INTO sports_matches (title, description, image, status, category, start_time, m3u8_link) VALUES (?, ?, ?, ?, ?, ?, ?);"
        matches_to_insert = [
            (m.get('title'), m.get('description'), m.get('image'), m.get('status'), m.get('category'), m.get('start_time'), m.get('m3u8_link'))
            for m in matches
        ]
        
        cursor.executemany(insert_query, matches_to_insert)
        conn.commit()
        print(f"Successfully updated database with {len(matches_to_insert)} sports matches.")
        
    except sqlite3.Error as e:
        print(f"Database error during match update: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def get_all_matches():
    """Retrieves all sports matches from the database."""
    matches = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, title, description, image, status, category, start_time, m3u8_link FROM sports_matches;")
        rows = cursor.fetchall()
        
        matches = [dict(row) for row in rows]
        
    except sqlite3.Error as e:
        print(f"Database error while fetching matches: {e}")
    finally:
        if conn:
            conn.close()
            
    return matches

def get_match_by_id(match_id):
    """Retrieves a single sports match by its ID."""
    match = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, title, description, image, status, category, start_time, m3u8_link FROM sports_matches WHERE id = ?;", (match_id,))
        row = cursor.fetchone()
        if row:
            match = dict(row)
            
    except sqlite3.Error as e:
        print(f"Database error while fetching match by ID: {e}")
    finally:
        if conn:
            conn.close()
            
    return match
