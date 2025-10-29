
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler

base_url = "https://fancode.bdixtv24.com/"

def process_page(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'lxml')
    
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
                    match_soup = BeautifulSoup(match_response.text, 'lxml')
                    scripts = match_soup.find_all('script')
                    for script in scripts:
                        if script.string and "setupPlayer" in script.string:
                            match_url_encoded = re.search(r'setupPlayer\("proxy\.php\?url=([^\"]+)"', script.string)
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

def update_matches_db():
    print("Updating matches database...")
    matches = process_page(base_url)
    
    conn = sqlite3.connect('matches.db')
    c = conn.cursor()
    
    c.execute("DELETE FROM matches")
    
    for match in matches:
        c.execute("INSERT INTO matches (title, description, image, status, category, start_time, m3u8_link) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (match['title'], match['description'], match['image'], match['status'], match['category'], match['start_time'], match['m3u8_link']))
    
    conn.commit()
    conn.close()
    print("Matches database updated.")

def start_worker():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_matches_db, 'interval', minutes=2)
    scheduler.start()
    print("Worker started.")

