from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

from flask import Flask, jsonify, render_template, abort, request, Response, stream_with_context, redirect
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
logging.basicConfig(level=logging.INFO)

# --- Global Session for Connection Pooling ---
# Reusing connections significantly speeds up streaming (avoiding repeated SSL handshakes)
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=50, pool_maxsize=50)
session.mount("https://", adapter)
session.mount("http://", adapter)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- URL Constants ---
base_url = "https://fancode.bdixtv24.com/"
TV_CHANNELS_URL = "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/main/Channels_data.json"
SPORT_TV_CHANNELS_URL = "https://raw.githubusercontent.com/abusaeeidx/CricHd-playlists-Auto-Update-permanent/main/api.json"
M3U_URL = "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/BD.m3u"

# --- Cache ---
cache = {
    'channels': [],
    'matches': [],
    'last_updated_channels': 0,
    'last_updated_matches': 0
}
CACHE_TIMEOUT = 300 # 5 minutes

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
        response = requests.get(SPORT_TV_CHANNELS_URL, timeout=5) # Reduced timeout for failsafe
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
        print(f"An error occurred in fetch_sport_tv_channels (Link might be down): {e}")
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

from concurrent.futures import ThreadPoolExecutor

# ... (other imports remain the same) ...

# This new function checks if a URL is accessible
def is_url_accessible(channel):
    """Checks if a channel's URL is accessible by making a HEAD request."""
    url = channel.get('url')
    if not url:
        return False
    try:
        # Use a short timeout to avoid long waits
        # The stream=True parameter avoids downloading the full content
        response = requests.head(url, timeout=5, stream=True, allow_redirects=True)
        # Check for a successful status code (2xx)
        if response.status_code >= 200 and response.status_code < 300:
            print(f"URL is accessible: {url}")
            return True
        else:
            print(f"URL is not accessible (Status: {response.status_code}): {url}")
            return False
    except requests.RequestException as e:
        # This catches connection errors, timeouts, etc.
        print(f"Failed to connect to URL: {url} ({e})")
        return False

def fetch_and_update_all_channels():
    """Fetches channels from all sources, validates them, and updates the database."""
    print("Fetching and updating all channels...")
    
    all_channels = []
    all_channels.extend(fetch_tv_channels())
    all_channels.extend(fetch_sport_tv_channels())
    all_channels.extend(fetch_m3u_channels())
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_channels = []
    for channel in all_channels:
        if channel.get('url') and channel['url'] not in seen_urls:
            unique_channels.append(channel)
            seen_urls.add(channel['url'])

    print(f"Found {len(unique_channels)} unique channels. Now validating...")

    # Validate channels in parallel to speed up the process
    accessible_channels = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Map the is_url_accessible function to each channel
        results = executor.map(is_url_accessible, unique_channels)
        # Collect channels that returned True
        for channel, is_accessible in zip(unique_channels, results):
            if is_accessible:
                accessible_channels.append(channel)

    print(f"Found {len(accessible_channels)} accessible channels after validation.")
            
    if accessible_channels:
        database.update_channels(accessible_channels)
        cache['channels'] = accessible_channels # Update memory cache
    else:
        print("No accessible channels found to update.")

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
        time.sleep(9600)

def update_sports_periodically():
    """Periodically fetches and updates sports matches in the database."""
    while True:
        print("Periodically updating sports matches...")
        matches = process_sports_on_demand()
        if matches:
            database.update_matches(matches)
        time.sleep(10000)

def rewrite_m3u8(content, base_url, referer, origin):
    lines = content.decode('utf-8', errors='ignore').split('\n')
    rewritten_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # Determine if the line is a URI (not empty, not a comment tag)
        # HLS spec: lines not starting with # are URIs
        if line_stripped and not line_stripped.startswith('#'):
             # It's a Segment or Playlist URI. Rewrite it to go through proxy.
             # This ensures both Variant Streams (ABR) and Segments work, even without .m3u8/.ts extensions.
             full_url = urljoin(base_url, line_stripped)
             proxied_url = f"/stream?url={quote(full_url)}&referer={quote(referer)}&origin={quote(origin)}"
             rewritten_lines.append(proxied_url)
        else:
             # Pass comments/tags through unchanged
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
        # Disable SSL verification due to SSLCertVerificationError.
        # WARNING: Disabling SSL verification can expose the application to man-in-the-middle attacks.
        # This is used as a temporary workaround for problematic certificates.
        # Use session.get for connection pooling
        r = session.get(url, headers=headers, stream=True, timeout=10, verify=False)
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
        
        return Response(stream_with_context(r.iter_content(chunk_size=512*1024)), content_type=r.headers['Content-Type'], headers={'Access-Control-Allow-Origin': '*'}) 

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching stream: {e}")
        return f"Error fetching stream: {e}", 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in stream(): {e}")
        return f"An unexpected error occurred: {e}", 500

# --- Cache Helpers ---
def create_slug(text):
    """Generates a URL-friendly slug from text."""
    if not text:
        return ""
    # slugify: lowercase, replace non-alphanumeric with underscores 
    # (User requested underscores: gopal_var_24_7)
    slug = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')
    return slug

def augment_with_slugs(items):
    """Adds unique slugs to a list of items."""
    seen_slugs = {}
    for item in items:
        name = item.get('name') or item.get('title') or 'untitled'
        base_slug = create_slug(name)
        slug = base_slug
        counter = 1
        
        # Ensure uniqueness
        while slug in seen_slugs:
            slug = f"{base_slug}_{counter}"
            counter += 1
            
        seen_slugs[slug] = True
        item['slug'] = slug
    return items

def get_cached_channels():
    if not cache['channels']:
        cache['channels'] = augment_with_slugs(database.get_all_channels())
    return cache['channels']

def get_cached_matches():
    if not cache['matches']:
        cache['matches'] = augment_with_slugs(database.get_all_matches())
    return cache['matches']

# --- Main Routes ---
@app.route('/')
def index():
    all_channels = get_cached_channels()
    all_matches = get_cached_matches()

    categorized_channels = {}
    for channel in all_channels:
        category = channel.get('category', 'Uncategorized')
        if category not in categorized_channels:
            categorized_channels[category] = []
        categorized_channels[category].append(channel)
    
    live_matches = [match for match in all_matches if match.get('status') == 'LIVE']

    return render_template('index.html', categorized_channels=categorized_channels, live_matches=live_matches)

@app.route('/update')
def update():
    fetch_and_update_all_channels()
    matches = process_sports_on_demand()
    if matches:
        database.update_matches(matches)
        # Update cache immediately and re-augment slugs
        cache['matches'] = augment_with_slugs(matches)
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

    all_channels = get_cached_channels()
    all_matches = get_cached_matches()

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

    results = items_with_slugs = channel_results + match_results
    
    return render_template('search.html', query=query, results=results)

@app.route('/sport-tv')
def sport_tv():
    channels = [ch for ch in get_cached_channels() if ch.get('category') == 'Sport TV']
    return render_template('sport_tv.html', channels=channels)

@app.route('/play/<string:content_type>/<string:slug_or_id>')
def play(content_type, slug_or_id):
    content = None
    related_content = []
    
    # Helper to find by slug or ID
    def find_content(items, identifier):
        # 1. Try match by slug
        found = next((i for i in items if i.get('slug') == identifier), None)
        if found: return found
        
        # 2. Try match by ID (backward compatibility)
        if identifier.isdigit():
            id_int = int(identifier)
            return next((i for i in items if i.get('id') == id_int), None)
        return None

    if content_type == 'tv':
        all_channels = get_cached_channels()
        content = find_content(all_channels, slug_or_id)
        
        # Fallback to DB if not in cache (rare, but handles misses)
        if not content and slug_or_id.isdigit():
             content = database.get_channel_by_id(int(slug_or_id))
             if content:
                 # Manually slugify for consistency if found directly from DB
                 content['slug'] = create_slug(content['name'])

        if content:
            content = content.copy() # Prevent modifying cache in place
            content['type'] = 'tv'
            content['url'] = f"/stream?url={quote(content['url'])}&referer={quote(content.get('referer') or '')}&origin={quote(content.get('origin') or '')}"
            related_content = [ch for ch in all_channels if ch.get('id') != content.get('id') and ch.get('category') == content.get('category')]
            for item in related_content:
                item['type'] = 'tv'

    elif content_type == 'sport':
        all_matches = get_cached_matches()
        content = find_content(all_matches, slug_or_id)
        
        if not content and slug_or_id.isdigit():
            content = database.get_match_by_id(int(slug_or_id))

        if content:
            content = content.copy() # Prevent modifying cache in place
            content['name'] = content.pop('title', content.get('name')) 
            content['url'] = content.pop('m3u8_link', content.get('url'))
            content['type'] = 'sport'
            # Manually slugify if missing
            if 'slug' not in content:
                 content['slug'] = create_slug(content['name'])

            related_content = [match for match in all_matches if match.get('status') == 'LIVE' and match.get('id') != content.get('id')]
            for item in related_content:
                item['type'] = 'sport'
                item['name'] = item.pop('title')
                if 'slug' not in item: item['slug'] = create_slug(item['name'])
    
    if not content:
        abort(404)
    
    return render_template('player.html', content=content, related_content=related_content)

# --- API Routes ---
@app.route('/api/matches')
def get_matches():
    matches = get_cached_matches()
    return jsonify(matches)

@app.route('/api/tv')
def get_tv_channels():
    # Now returns all channels. The frontend will handle categories.
    channels = get_cached_channels()
    return jsonify(channels)

@app.route('/api/categories')
def get_categories():
    all_channels = get_cached_channels()
    categories = sorted(list(set(ch['category'] for ch in all_channels if 'category' in ch)))
    return jsonify(categories)

@app.route('/api/sport-tv')
def get_sport_tv_channels():
    channels = [ch for ch in get_cached_channels() if ch.get('category') == 'Sport TV']
    return jsonify(channels)

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])

    all_channels = get_cached_channels()
    all_matches = get_cached_matches()

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
        m['name'] = m.get('title')

    results = channel_results + match_results
    
    return jsonify(results)

@app.route('/api/play/<string:content_type>/<string:slug_or_id>')
def get_play_data(content_type, slug_or_id):
    content = None
    related_content = []
    
    # Helper (reused - in real app should be shared function)
    def find_content(items, identifier):
        found = next((i for i in items if i.get('slug') == identifier), None)
        if found: return found
        if identifier.isdigit():
            id_int = int(identifier)
            return next((i for i in items if i.get('id') == id_int), None)
        return None

    if content_type == 'tv':
        all_channels = get_cached_channels()
        content = find_content(all_channels, slug_or_id)
        
        if not content and slug_or_id.isdigit():
             content = database.get_channel_by_id(int(slug_or_id))

        if content:
            content = content.copy() # Prevent modifying cache in place
            content['type'] = 'tv'
            content['url'] = f"/stream?url={quote(content['url'])}&referer={quote(content.get('referer') or '')}&origin={quote(content.get('origin') or '')}"
            related_content = [ch for ch in all_channels if ch.get('id') != content.get('id') and ch.get('category') == content.get('category')]
            for item in related_content:
                item['type'] = 'tv'
    elif content_type == 'sport':
        all_matches = get_cached_matches()
        content = find_content(all_matches, slug_or_id)
        
        if not content and slug_or_id.isdigit():
            content = database.get_match_by_id(int(slug_or_id))

        if content:
            content = content.copy() # Prevent modifying cache in place
            content['name'] = content.pop('title', content.get('name'))
            content['url'] = content.pop('m3u8_link', content.get('url'))
            content['type'] = 'sport'
            related_content = [match for match in all_matches if match['status'] == 'LIVE' and match.get('id') != content.get('id')]
            for item in related_content:
                item['type'] = 'sport'
                item['name'] = item.pop('title')

    if not content:
        return jsonify({"error": "Content not found"}), 404
    
    # Ensure slug is present in response
    if 'slug' not in content:
        content['slug'] = create_slug(content.get('name', ''))

    return jsonify({"content": content, "related": related_content})

# --- Redirect Route ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """Redirect all traffic to apontv.vercel.app"""
    return redirect('https://apontv.vercel.app/', code=302)

# --- Initial Setup ---
def init_app():
    # database.init_db() # No longer needed after migrating to Supabase
    # Periodically update all channels
    threading.Thread(target=update_all_channels_periodically).start()
    # Periodically update sports matches
    threading.Thread(target=update_sports_periodically).start()

init_app()

if __name__ == "__main__":
    # Run in threaded mode for better concurrent handling of video segments
    # Disable debug mode for performance (removes overhead)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
