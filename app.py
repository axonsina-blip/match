
from flask import Flask, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote
import json
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
import database

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key' # Replace with a strong secret key
socketio = SocketIO(app)

base_url = "https://fancode.bdixtv24.com/"
TV_CHANNELS_URL = "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/main/Channels_data.json"

# Global counter for connected users
connected_users = 0

def fetch_tv_channels():
    """Fetches TV channel data from the JSON source and updates the database."""
    print("Attempting to fetch and update TV channels...")
    try:
        response = requests.get(TV_CHANNELS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        channels = data.get("channels", [])
        
        # Add a default logo if it's missing
        for channel in channels:
            if "logo" not in channel or not channel["logo"]:
                channel["logo"] = "https://via.placeholder.com/150/000000/FFFFFF/?text=TV"
        
        # Update the database with the new channel list
        database.update_channels(channels)
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching TV channels: {e}")
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON from the TV channels URL.")


def process_page(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    matches_data = []

    for match_div in soup.find_all('div', class_='match-card'):
        category = match_div.get('data-category')
        match_id = match_div.get('data-id')
        status = match_div.get('data-status')
        adfree_url = match_div.get('data-adfree-url')

        img_tag = match_div.find('img')
        image_url = img_tag['src'] if img_tag else 'No Image'
        title = match_div.find('h3').text.strip() if match_div.find('h3') else 'No Title'
        
        paragraphs = match_div.find_all('p')
        description = paragraphs[0].text.strip() if len(paragraphs) > 0 else ''
        start_time = paragraphs[3].text.replace('Start Time: ', '').strip() if len(paragraphs) > 3 else ''

        m3u8_link = None
        if status == 'LIVE':
            if adfree_url:
                m3u8_link = adfree_url.replace("https://in-mc-fdlive.fancode.com", "https://bd-mc-fdlive.fancode.com")
            else:
                match_url = f"https://fancode.bdixtv24.com/play.php?id={match_id}"
                try:
                    match_response = requests.get(match_url, timeout=10)
                    match_soup = BeautifulSoup(match_response.text, 'html.parser')
                    scripts = match_soup.find_all('script')
                    for script in scripts:
                        if script.string and "setupPlayer" in script.string:
                            match_url_encoded = re.search(r'setupPlayer\("proxy\.php\?url=([^"]+)"', script.string)
                            if match_url_encoded:
                                m3u8_link_encoded = match_url_encoded.group(1)
                                m3u8_link = unquote(m3u8_link_encoded)
                                m3u8_link = m3u8_link.replace("https://in-mc-fdlive.fancode.com", "https://bd-mc-fdlive.fancode.com")
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching play page: {e}")


        matches_data.append({
            "title": title,
            "description": description,
            "image": image_url,
            "status": status,
            "category": category,
            "start_time": start_time,
            "m3u8_link": m3u8_link
        })
        
    return matches_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/matches')
def get_matches():
    match_list = process_page(base_url)
    return jsonify(match_list)

@app.route('/api/tv')
def get_tv_channels():
    channels = database.get_all_channels()
    return jsonify(channels)

@socketio.on('connect')
def handle_connect():
    global connected_users
    connected_users += 1
    emit('user_count', {'count': connected_users}, broadcast=True)
    print(f"Client connected. Total users: {connected_users}")

@socketio.on('disconnect')
def handle_disconnect():
    global connected_users
    connected_users -= 1
    emit('user_count', {'count': connected_users}, broadcast=True)
    print(f"Client disconnected. Total users: {connected_users}")

if __name__ == "__main__":
    # Initialize the database
    database.init_db()
    
    # Fetch initial data at startup
    fetch_tv_channels()

    # Set up the scheduler to fetch data periodically
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_tv_channels, 'interval', hours=6)
    scheduler.start()
    
    socketio.run(app, debug=True)
