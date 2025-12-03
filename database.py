import sqlite3
import os

# Define the path for the database in the instance folder
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptv.db')

def init_db():
    """Initializes the database and creates the tv_channels table if it doesn't exist."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tv_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                logo TEXT
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
    """
    Deletes all existing channels and replaces them with a new list.
    
    Args:
        channels (list): A list of channel dictionaries, each with 'name', 'url', and 'logo'.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Start a transaction
        cursor.execute("BEGIN TRANSACTION;")
        
        # Delete all existing records
        cursor.execute("DELETE FROM tv_channels;")
        
        # Insert new records
        insert_query = "INSERT INTO tv_channels (name, url, logo) VALUES (?, ?, ?);"
        channels_to_insert = [
            (ch.get('name'), ch.get('url'), ch.get('logo'))
            for ch in channels if ch.get('name') and ch.get('url')
        ]
        
        cursor.executemany(insert_query, channels_to_insert)
        
        # Commit the transaction
        conn.commit()
        print(f"Successfully updated database with {len(channels_to_insert)} channels.")
        
    except sqlite3.Error as e:
        print(f"Database error during channel update: {e}")
        if conn:
            conn.rollback() # Rollback on error
    finally:
        if conn:
            conn.close()

def get_all_channels():
    """
    Retrieves all TV channels from the database.
    
    Returns:
        list: A list of channel dictionaries.
    """
    channels = []
    try:
        conn = sqlite3.connect(db_path)
        # Row factory to get results as dictionaries
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, url, logo FROM tv_channels;")
        rows = cursor.fetchall()
        
        # Convert row objects to dictionaries
        channels = [dict(row) for row in rows]
        
    except sqlite3.Error as e:
        print(f"Database error while fetching channels: {e}")
    finally:
        if conn:
            conn.close()
            
    return channels

