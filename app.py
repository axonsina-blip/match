from flask import Flask, jsonify, render_template, abort, request, Response
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote, urljoin, quote
import json
import random
import time
from flask_socketio import SocketIO, emit
import database
import threading
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
logging.basicConfig(level=logging.INFO)

# --- URL Constants ---
base_url = "https://fancode.bdixtv24.com/"
TV_CHANNELS_URL = "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/main/Channels_data.json"
SPORT_TV_CHANNELS_URL = "https://raw.githubusercontent.com/abusaeeidx/CricHd-playlists-Auto-Update-permanent/main/api.json"
M3U_URL = "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/BD.m3u"

def fetch_tv_channels():
    """Fetches TV channel data from the JSON source."""
    print("Attempting to fetch TV channels from JSON source...")
    try:
        response = requests.get(TV_CHANNELS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        channels = data.get("channels", [])
        
        cleaned_channels = []
        for channel in channels:
            if "name" in channel and channel["name"]:
                channel["name"] = re.sub(r'[^a-zA-Z0-9/ ]', '', channel["name"]).strip()
                if "logo" not in channel or not channel["logo"]:
                    channel["logo"] = "/static/tv.jpg"
                channel['category'] = channel.get('category', 'Live TV')
                cleaned_channels.append(channel)
        return cleaned_channels
    except Exception as e:
        print(f"An error occurred in fetch_tv_channels: {e}")
        return []

def fetch_sport_tv_channels():
    """Fetches Sport TV channel data from the JSON source."""
    print("Attempting to fetch Sport TV channels...")
    try:
        response = requests.get(SPORT_TV_CHANNELS_URL, timeout=10)
        response.raise_for_status()
        channels = response.json()
        
        cleaned_channels = []
        for channel in channels:
            if "name" in channel and channel.get("link"):
                channel['url'] = channel.pop('link')
                channel['category'] = 'Sport TV'
                cleaned_channels.append(channel)
        return cleaned_channels
    except Exception as e:
        print(f"An error occurred in fetch_sport_tv_channels: {e}")
        return []

def fetch_m3u_channels():
    """Fetches TV channel data from the M3U source."""
    print("Attempting to fetch TV channels from M3U source...")
    try:
        response = requests.get(M3U_URL, timeout=10)
        response.raise_for_status()
        content = response.text
        
        lines = content.split('\n')
        channels = []
        
        for i in range(len(lines)):
            if lines[i].startswith('#EXTINF'):
                info_line = lines[i]
                url_line = lines[i+1].strip()
                
                # Extract name from the part after the last comma
                name_part = info_line.split(',')[-1]
                name = name_part.strip()

                logo_match = re.search(r'tvg-logo="([^"]*)"', info_line)
                category_match = re.search(r'group-title="([^"]*)"', info_line)
                
                logo = logo_match.group(1) if logo_match else "/static/tv.jpg"
                category = category_match.group(1) if category_match else "Uncategorized"
                
                channels.append({
                    "name": name,
                    "url": url_line,
                    "logo": logo.strip(),
                    "category": category.strip()
                })
        return channels
    except Exception as e:
        print(f"An error occurred in fetch_m3u_channels: {e}")
        return []

def fetch_and_update_all_channels():
    """Fetches channels from all sources, combines them, and updates the database."""
    print("Fetching and updating all channels...")
    
    all_channels = []
    all_channels.extend(fetch_tv_channels())
    all_channels.extend(fetch_sport_tv_channels())
    all_channels.extend(fetch_m3u_channels())
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_channels = []
    for channel in all_channels:
        if channel['url'] not in seen_urls:
            unique_channels.append(channel)
            seen_urls.add(channel['url'])
            
    if unique_channels:
        database.update_channels(unique_channels)
    else:
        print("No channels found from any source.")

def process_sports_on_demand():
    """Scrapes sports match data on demand and returns it."""
    print("Scraping sports matches on demand...")
    try:
        response = requests.get(base_url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
    
        matches_data = []
        for match_div in soup.find_all('div', class_='match-card'):
            m3u8_link = None
            if match_div.get('data-status') == 'LIVE':
                adfree_url = match_div.get('data-adfree-url')
                if adfree_url:
                    m3u8_link = adfree_url.replace("https://in-mc-fdlive.fancode.com", "https://bd-mc-fdlive.fancode.com")
                else:
                    match_id = match_div.get('data-id')
                    match_url = f"https://fancode.bdixtv24.com/play.php?id={match_id}"
                    try:
                        match_response = requests.get(match_url, timeout=5)
                        match_soup = BeautifulSoup(match_response.text, 'html.parser')
                        for script in match_soup.find_all('script'):
                            if script.string and "setupPlayer" in script.string:
                                match = re.search(r'setupPlayer\("proxy\.php\?url=([^\"]+)"', script.string)
                                if match:
                                    m3u8_link = unquote(match.group(1)).replace("https://in-mc-fdlive.fancode.com", "https://bd-mc-fdlive.fancode.com")
                    except Exception:
                        pass # Ignore errors for individual play pages
            
            matches_data.append({
                "title": match_div.find('h3').text.strip() if match_div.find('h3') else 'No Title',
                "description": match_div.find_all('p')[0].text.strip() if match_div.find_all('p') else '',
                "image": match_div.find('img')['src'] if match_div.find('img') else None,
                "status": match_div.get('data-status'),
                "category": match_div.get('data-category'),
                "start_time": match_div.find_all('p')[3].text.replace('Start Time: ', '').strip() if len(match_div.find_all('p')) > 3 else '',
                "m3u8_link": m3u8_link
            })
        return matches_data
    except Exception as e:
        print(f"Could not scrape sports page: {e}")
        return []

def update_all_channels_periodically():
    """Periodically fetches and updates all channels in the database."""
    while True:
        print("Periodically updating all channels...")
        fetch_and_update_all_channels()
        time.sleep(300)

def update_sports_periodically():
    """Periodically fetches and updates sports matches in the database."""
    while True:
        print("Periodically updating sports matches...")
        matches = process_sports_on_demand()
        if matches:
            database.update_matches(matches)
        time.sleep(120)

def rewrite_m3u8(content, base_url, referer, origin):
    lines = content.decode('utf-8', errors='ignore').split('\n')
    rewritten_lines = []
    for line in lines:
        if line.strip().endswith('.ts') or line.strip().endswith('.m3u8'):
            rewritten_lines.append(f"/stream?url={quote(urljoin(base_url, line))}&referer={quote(referer)}&origin={quote(origin)}")
        else:
            rewritten_lines.append(line)
    return '\n'.join(rewritten_lines)

@app.route('/stream')
def stream():
    url = request.args.get('url')
    referer = request.args.get('referer', '')
    origin = request.args.get('origin', '')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }
    if referer:
        headers['Referer'] = referer
    if origin:
        headers['Origin'] = origin

    app.logger.info(f"Streaming URL: {url}")
    app.logger.info(f"Streaming headers: {headers}")

    try:
        r = requests.get(url, headers=headers, stream=True, timeout=10)
        r.raise_for_status()
        
        app.logger.info(f"Remote server status code: {r.status_code}")
        
        content_type = r.headers.get('Content-Type', '')
        app.logger.info(f"Remote server content type: {content_type}")

        if 'application/vnd.apple.mpegurl' in content_type or '.m3u8' in url:
            try:
                rewritten_content = rewrite_m3u8(r.content, url, referer, origin)
                return Response(rewritten_content, mimetype='application/vnd.apple.mpegurl', headers={'Access-Control-Allow-Origin': '*'})
            except Exception as e:
                app.logger.error(f"Error in rewrite_m3u8: {e}")
                return f"Error rewriting M3U8: {e}", 500
        
        return Response(r.iter_content(chunk_size=1024), content_type=r.headers['Content-Type'], headers={'Access-Control-Allow-Origin': '*'})

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching stream: {e}")
        return f"Error fetching stream: {e}", 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in stream(): {e}")
        return f"An unexpected error occurred: {e}", 500

# --- Main Routes ---
@app.route('/')
def index():
    all_channels = database.get_all_channels()
    # This part might need adjustment based on how we want to display channels on the homepage
    live_tv_channels = [ch for ch in all_channels if ch.get('category') == 'Live TV']
    sport_tv_channels = [ch for ch in all_channels if ch.get('category') == 'Sport TV']
    return render_template('index.html', live_tv_channels=live_tv_channels, sport_tv_channels=sport_tv_channels)

@app.route('/update')
def update():
    fetch_and_update_all_channels()
    matches = process_sports_on_demand()
    if matches:
        database.update_matches(matches)
    return "Update initiated."

@app.route('/sports')
def sports():
    return render_template('sports.html')

@app.route('/live-tv')
def live_tv():
    # This will now show all channels. We will filter by category on the frontend.
    return render_template('tv.html')

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    
    if not query:
        return render_template('search.html', query=query, results=[])

    all_channels = database.get_all_channels()
    all_matches = database.get_all_matches()

    channel_results = [
        ch for ch in all_channels 
        if query.lower() in ch.get('name', '').lower()
    ]
    for ch in channel_results:
        ch['type'] = 'tv'

    match_results = [
        m for m in all_matches
        if query.lower() in m.get('title', '').lower()
    ]
    for m in match_results:
        m['type'] = 'sport'
        m['name'] = m['title']

    results = channel_results + match_results
    
    return render_template('search.html', query=query, results=results)

@app.route('/sport-tv')
def sport_tv():
    channels = [ch for ch in database.get_all_channels() if ch.get('category') == 'Sport TV']
    return render_template('sport_tv.html', channels=channels)

@app.route('/play/<string:content_type>/<int:content_id>')
def play(content_type, content_id):
    content = None
    related_content = []
    if content_type == 'tv':
        content = database.get_channel_by_id(content_id)
        if content:
            content['type'] = 'tv'
            content['url'] = f"/stream?url={quote(content['url'])}&referer={quote(content.get('referer') or '')}&origin={quote(content.get('origin') or '')}"
            related_content = [ch for ch in database.get_all_channels() if ch['id'] != content_id and ch.get('category') == content.get('category')]
            for item in related_content:
                item['type'] = 'tv'
    elif content_type == 'sport':
        content = database.get_match_by_id(content_id)
        if content:
            content['name'] = content.pop('title')
            content['url'] = content.pop('m3u8_link')
            content['type'] = 'sport'
            related_content = [match for match in database.get_all_matches() if match['status'] == 'LIVE' and match['id'] != content_id]
            for item in related_content:
                item['type'] = 'sport'
                item['name'] = item.pop('title')
    
    if not content:
        abort(404)
    
    return render_template('player.html', content=content, related_content=related_content)

# --- API Routes ---
@app.route('/api/matches')
def get_matches():
    matches = database.get_all_matches()
    return jsonify(matches)

@app.route('/api/tv')
def get_tv_channels():
    # Now returns all channels. The frontend will handle categories.
    channels = database.get_all_channels()
    return jsonify(channels)

@app.route('/api/categories')
def get_categories():
    all_channels = database.get_all_channels()
    categories = sorted(list(set(ch['category'] for ch in all_channels if 'category' in ch)))
    return jsonify(categories)

@app.route('/api/sport-tv')
def get_sport_tv_channels():
    channels = [ch for ch in database.get_all_channels() if ch.get('category') == 'Sport TV']
    return jsonify(channels)

@app.route('/api/play/<string:content_type>/<int:content_id>')
def get_play_data(content_type, content_id):
    content = None
    related_content = []
    if content_type == 'tv':
        content = database.get_channel_by_id(content_id)
        if content:
            content['type'] = 'tv'
            content['url'] = f"/stream?url={quote(content['url'])}&referer={quote(content.get('referer') or '')}&origin={quote(content.get('origin') or '')}"
            related_content = [ch for ch in database.get_all_channels() if ch['id'] != content_id and ch.get('category') == content.get('category')]
            for item in related_content:
                item['type'] = 'tv'
    elif content_type == 'sport':
        content = database.get_match_by_id(content_id)
        if content:
            content['name'] = content.pop('title')
            content['url'] = content.pop('m3u8_link')
            content['type'] = 'sport'
            related_content = [match for match in database.get_all_matches() if match['status'] == 'LIVE' and match['id'] != content_id]
            for item in related_content:
                item['type'] = 'sport'
                item['name'] = item.pop('title')

    if not content:
        return jsonify({"error": "Content not found"}), 404
    return jsonify({"content": content, "related": related_content})

# --- Initial Setup ---
def init_app():
    database.init_db()
    # Periodically update all channels
    threading.Thread(target=update_all_channels_periodically).start()
    # Periodically update sports matches
    threading.Thread(target=update_sports_periodically).start()

init_app()

if __name__ == "__main__":
    app.run(debug=True)
