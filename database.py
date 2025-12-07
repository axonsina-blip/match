import json
import os
import threading

# Define the path for the data directory
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
channels_path = os.path.join(data_dir, 'tv_channels.json')
matches_path = os.path.join(data_dir, 'sports_matches.json')

# A lock for thread-safe file writing
file_lock = threading.Lock()

def init_db():
    """Initializes the JSON database files."""
    with file_lock:
        try:
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            if not os.path.exists(channels_path):
                with open(channels_path, 'w') as f:
                    json.dump([], f)
            
            if not os.path.exists(matches_path):
                with open(matches_path, 'w') as f:
                    json.dump([], f)
            
            print("JSON Database initialized successfully.")
        except IOError as e:
            print(f"Database error during initialization: {e}")

def _read_json(file_path):
    """Reads a JSON file."""
    with file_lock:
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return []

def _write_json(file_path, data):
    """Writes data to a JSON file."""
    with file_lock:
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"Error writing to {file_path}: {e}")


def update_channels(channels):
    """Replaces the list of channels with a new one, adding unique IDs."""
    
    # Filter out channels that are missing 'name' or 'url'
    valid_channels = [ch for ch in channels if ch.get('name') and ch.get('url')]
    
    # Assign a simple integer ID to each channel
    for i, channel in enumerate(valid_channels):
        channel['id'] = i + 1
        
    _write_json(channels_path, valid_channels)
    print(f"Successfully updated with {len(valid_channels)} TV channels.")

def get_all_channels():
    """Retrieves all TV channels from the JSON file."""
    return _read_json(channels_path)

def get_channel_by_id(channel_id):
    """Retrieves a single TV channel by its ID."""
    all_channels = _read_json(channels_path)
    for channel in all_channels:
        if channel.get('id') == channel_id:
            return channel
    return None

def update_matches(matches):
    """Replaces the list of matches with a new one, adding unique IDs."""
    
    # Assign a simple integer ID to each match
    for i, match in enumerate(matches):
        match['id'] = i + 1
        
    _write_json(matches_path, matches)
    print(f"Successfully updated with {len(matches)} sports matches.")


def get_all_matches():
    """Retrieves all sports matches from the JSON file."""
    return _read_json(matches_path)

def get_match_by_id(match_id):
    """Retrieves a single sports match by its ID."""
    all_matches = _read_json(matches_path)
    for match in all_matches:
        if match.get('id') == match_id:
            return match
    return None
