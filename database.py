import os
from supabase import create_client, Client
import json

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") # Use ANON_KEY for client-side operations

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL and Key must be set as environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Define table names
TV_CHANNELS_TABLE = "tv_channels"
SPORTS_MATCHES_TABLE = "sports_matches"

def _insert_or_update_data(table_name, data_list):
    """Inserts or updates a list of items into a Supabase table."""
    try:
        # For simplicity, we'll delete existing data and insert new data.
        # In a real application, you might want more granular updates (upsert).
        
        # First, delete all existing rows in the table
        supabase.from_(table_name).delete().gt("id", 0).execute() # Deletes all where id > 0
        
        # Then, insert the new data
        if data_list: # Only insert if data_list is not empty
            response = supabase.from_(table_name).insert(data_list).execute()
            if response.data:
                print(f"Successfully updated {len(response.data)} items in {table_name}.")
            elif response.error:
                print(f"Error inserting data into {table_name}: {response.error}")
        else:
            print(f"No data to insert into {table_name}.")
        return True
    except Exception as e:
        print(f"Database error during insert/update for {table_name}: {e}")
        return False

def _get_all_data(table_name):
    """Retrieves all data from a Supabase table."""
    try:
        response = supabase.from_(table_name).select("*").execute()
        if response.data:
            return response.data
        elif response.error:
            print(f"Error retrieving data from {table_name}: {response.error}")
            return []
        return []
    except Exception as e:
        print(f"Database error during retrieval for {table_name}: {e}")
        return []

def _get_data_by_id(table_name, item_id):
    """Retrieves a single item by its ID from a Supabase table."""
    try:
        response = supabase.from_(table_name).select("*").eq("id", item_id).single().execute()
        if response.data:
            return response.data
        elif response.error and response.error.code == 'PGRST116': # Not found error
            return None
        elif response.error:
            print(f"Error retrieving item by ID from {table_name}: {response.error}")
            return None
        return None # Should not reach here if single() is used and data is None
    except Exception as e:
        print(f"Database error during retrieval by ID for {table_name}: {e}")
        return None

def update_channels(channels):
    """Replaces the list of channels with a new one, adding unique IDs."""
    valid_channels = [ch for ch in channels if ch.get('name') and ch.get('url')]
    
    # Assign a simple integer ID to each channel. 
    # Supabase usually handles primary keys, but if 'id' is expected in the data, 
    # we can generate it. Otherwise, remove this.
    for i, channel in enumerate(valid_channels):
        channel['id'] = i + 1
        
    return _insert_or_update_data(TV_CHANNELS_TABLE, valid_channels)

def get_all_channels():
    """Retrieves all TV channels from the Supabase table."""
    return _get_all_data(TV_CHANNELS_TABLE)

def get_channel_by_id(channel_id):
    """Retrieves a single TV channel by its ID."""
    return _get_data_by_id(TV_CHANNELS_TABLE, channel_id)

def update_matches(matches):
    """Replaces the list of matches with a new one, adding unique IDs."""
    # Assign a simple integer ID to each match.
    for i, match in enumerate(matches):
        match['id'] = i + 1
        
    return _insert_or_update_data(SPORTS_MATCHES_TABLE, matches)

def get_all_matches():
    """Retrieves all sports matches from the Supabase table."""
    return _get_all_data(SPORTS_MATCHES_TABLE)

def get_match_by_id(match_id):
    """Retrieves a single sports match by its ID."""
    return _get_data_by_id(SPORTS_MATCHES_TABLE, match_id)

# The init_db function is no longer needed as Supabase handles database initialization.
# However, you need to ensure the tables (tv_channels, sports_matches) exist in your Supabase project.
# You can create them manually in the Supabase dashboard or via migrations.