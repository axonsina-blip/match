from flask import Flask, jsonify, render_template, request, Response
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote, urljoin, quote
import json
import random
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
import database

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key' # Replace with a strong secret key
socketio = SocketIO(app)

base_url = "https://fancode.bdixtv24.com/"
TV_CHANNELS_URL = "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/main/Channels_data.json"
CANDY_API_URL = "https://raw.githubusercontent.com/hasanhabibmottakin/candy/main/rest_api.json"

# Global counter for connected users
connected_users = 0

def fetch_tv_channels():
    print("Attempting to fetch and update TV channels from all sources...")
    
    combined_channels = []

    # --- Source 1: Mrgify ---
    try:
        response1 = requests.get(TV_CHANNELS_URL, timeout=10)
        response1.raise_for_status()
        data1 = response1.json()
        channels1 = data1.get("channels", [])
        
        for channel in channels1:
            if "name" in channel and channel["name"]:
                channel["name"] = re.sub(r'[^a-zA-Z0-9 ]', '', channel["name"]).strip()
                if "logo" not in channel or not channel["logo"]:
                    channel["logo"] = "/static/tv.jpg"
                channel["cookie"] = None # No cookie for this source
                combined_channels.append(channel)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching TV channels from Mrgify: {e}")
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON from Mrgify URL.")

    # --- Source 2: Candy ---
    try:
        response2 = requests.get(CANDY_API_URL, timeout=10)
        response2.raise_for_status()
        data2 = response2.json()
        channels2 = data2.get("response", [])

        for channel in channels2:
            if "name" in channel and channel["name"] and "link" in channel and channel["link"]:
                clean_name = re.sub(r'[^a-zA-Z0-9 ]', '', channel["name"]).strip()
                # Remap keys to match our database schema
                formatted_channel = {
                    "name": clean_name,
                    "url": channel["link"],
                    "logo": channel.get("logo") or "/static/tv.jpg",
                    "cookie": channel.get("cookie")
                }
                combined_channels.append(formatted_channel)
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching TV channels from Candy: {e}")
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON from Candy URL.")
    
    # --- Update Database ---
    if combined_channels:
        database.update_channels(combined_channels)
    else:
        print("No channels fetched, database not updated.")


def fetch_and_process_sports_matches():
    print("Attempting to fetch and process sports matches...")
    try:
        response = requests.get(base_url, timeout=10)
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
                                match_url_encoded = re.search(r'setupPlayer\("proxy\.php\?url=([^\"]+)"', script.string)
                                if match_url_encoded:
                                    m3u8_link_encoded = match_url_encoded.group(1)
                                    m3u8_link = unquote(m3u8_link_encoded)
                                    m3u8_link = m3u8_link.replace("https://in-mc-fdlive.fancode.com", "https://bd-mc-fdlive.fancode.com")
                    except requests.exceptions.RequestException as e:
                        print(f"Error fetching play page for match ID {match_id}: {e}")

            matches_data.append({
                "title": title,
                "description": description,
                "image": image_url,
                "status": status,
                "category": category,
                "start_time": start_time,
                "m3u8_link": m3u8_link
            })
        
        if matches_data:
            database.update_matches(matches_data)
        else:
            print("No sports matches found during scrape.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching main sports page: {e}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sports')
def sports():
    return render_template('sports.html')

@app.route('/live-tv')
def live_tv():
    return render_template('tv.html')


@app.route('/play')
def play():
    return render_template('player.html')

@app.route('/stream')
def stream():
    url = request.args.get('url')
    original_url = request.args.get('original_url')

    if not url:
        return "Missing URL parameter", 400

    # The lookup_url should always be the master playlist URL.
    # The first request has it in 'url', subsequent requests have it in 'original_url'.
    lookup_url = original_url if original_url else url
    
    # Find the channel in the database to get the cookie.
    channels = database.get_all_channels()
    channel_data = next((c for c in channels if c['url'] == lookup_url), None)

    headers = {}
    if channel_data and channel_data.get('cookie'):
        headers['Cookie'] = channel_data['cookie']

    try:
        # If it's a playlist, we need to parse it and rewrite URLs
        if '.m3u8' in url:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            
            lines = r.text.splitlines()
            new_lines = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('#EXT-X-KEY'):
                    # Logic to find and rewrite the URI in the key tag
                    uri_start = line.find('URI="') + 5
                    uri_end = line.find('"', uri_start)
                    if uri_start > 4 and uri_end > uri_start:
                        key_uri = line[uri_start:uri_end]
                        absolute_key_uri = urljoin(url, key_uri)
                        # Ensure the original master playlist URL is passed along
                        proxied_key_uri = f"/stream?url={quote(absolute_key_uri)}&original_url={quote(lookup_url)}"
                        new_line = line.replace(key_uri, proxied_key_uri)
                        new_lines.append(new_line)
                    else:
                        new_lines.append(line)
                elif line and not line.startswith('#'):
                    # This is a URL to a segment or another playlist
                    absolute_segment_url = urljoin(url, line)
                    # Ensure the original master playlist URL is passed along
                    proxied_segment = f"/stream?url={quote(absolute_segment_url)}&original_url={quote(lookup_url)}"
                    new_lines.append(proxied_segment)
                else:
                    new_lines.append(line)
            
            return Response('\n'.join(new_lines), mimetype='application/x-mpegURL')

        # If it's a segment (.ts) or key file, just stream it with the cookie
        else:
            req = requests.get(url, headers=headers, stream=True, timeout=10)
            req.raise_for_status()
            return Response(req.iter_content(chunk_size=1024), content_type=req.headers.get('content-type'))

    except requests.exceptions.RequestException as e:
        print(f"Error in proxy stream for url {url}: {e}")
        return "Error fetching stream content.", 500


@app.route('/api/matches')
def get_matches():
    matches = database.get_all_matches()
    return jsonify(matches)

@app.route('/api/tv')
def get_tv_channels():
    channels = database.get_all_channels()
    random.shuffle(channels) # Shuffle the list
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
    fetch_and_process_sports_matches()

    # Set up the scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_tv_channels, 'interval', minutes=1)
    scheduler.add_job(fetch_and_process_sports_matches, 'interval', minutes=1)
    scheduler.start()
    
    socketio.run(app, debug=True)
