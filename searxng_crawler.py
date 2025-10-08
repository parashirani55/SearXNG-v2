import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def scrape_website(base_url, limit=5):
    urls_to_visit = [base_url]
    visited = set()
    scraped_data = []

    while urls_to_visit and len(scraped_data) < limit:
        url = urls_to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            text = ' '.join([p.get_text() for p in soup.find_all('p')])
            scraped_data.append({'url': url, 'content': text})

            for a in soup.find_all('a', href=True):
                next_url = urljoin(base_url, a['href'])
                if base_url in next_url:
                    urls_to_visit.append(next_url)
        except Exception as e:
            print(f"Error scraping {url}: {e}")

    return scraped_data
