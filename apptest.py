import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote
import json

base_url = "https://fancode.bdixtv24.com/"

def process_page(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    matches_data = []

    # Process Live Matches
    live_matches_container = soup.find('div', id='liveMatches')
    if live_matches_container:
        live_matches = live_matches_container.find_all('div', attrs={'data-id': True})
        for match in live_matches:
            match_id = match['data-id']
            title_element = match.find('h2', class_='text-light')
            title = title_element.text.strip() if title_element else "No Title"
            
            image_element = match.find('img')
            image_url = image_element['src'] if image_element else "No Image"

            match_url = f"https://fancode.bdixtv24.com/play.php?id={match_id}"
            match_response = requests.get(match_url, timeout=10)
            match_soup = BeautifulSoup(match_response.text, 'html.parser')
            
            m3u8_link = None
            scripts = match_soup.find_all('script')
            for script in scripts:
                if script.string and "setupPlayer" in script.string:
                    match_url_encoded = re.search(r'setupPlayer\("proxy\.php\?url=([^"]+)"', script.string)
                    if match_url_encoded:
                        m3u8_link_encoded = match_url_encoded.group(1)
                        m3u8_link = unquote(m3u8_link_encoded)
                        m3u8_link = m3u8_link.replace("https://in-mc-fdlive.fancode.com", "https://bd-mc-fdlive.fancode.com")

            matches_data.append({
                "title": title,
                "image": image_url,
                "status": "LIVE",
                "m3u8_link": m3u8_link
            })

    # Process Upcoming Matches
    upcoming_matches_container = soup.find('div', id='upcomingMatches')
    if upcoming_matches_container:
        upcoming_matches = upcoming_matches_container.find_all('div', attrs={'data-id': True})
        for match in upcoming_matches:
            title_element = match.find('h2', class_='text-light')
            title = title_element.text.strip() if title_element else "No Title"
            
            image_element = match.find('img')
            image_url = image_element['src'] if image_element else "No Image"

            matches_data.append({
                "title": title,
                "image": image_url,
                "status": "UPCOMING",
                "m3u8_link": None
            })
        
    return matches_data

if __name__ == "__main__":
    match_list = process_page(base_url)
    print(json.dumps(match_list, indent=4))