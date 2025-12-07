import requests

url = "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/BD.m3u"

try:
    response = requests.get(url)
    response.raise_for_status()
    
    lines = response.text.split('\n')
    for i in range(min(20, len(lines))):
        print(lines[i])

except requests.exceptions.RequestException as e:
    print(f"Error fetching URL: {e}")