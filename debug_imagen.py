import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

url = "https://diaonline.supermercadosdia.com.ar/leche-semi-descremada-dia-larga-vida-1-lt-504/p"

response = requests.get(url, headers=HEADERS, timeout=20)
print(f"Status: {response.status_code}")

soup = BeautifulSoup(response.text, 'html.parser')

print("\n=== Buscando todas las imágenes ===")
imgs = soup.find_all('img')
for i, img in enumerate(imgs[:15]):
    src = img.get('src') or img.get('data-src')
    cls = img.get('class')
    print(f"{i}. class: {cls}")
    print(f"   src: {src[:100] if src else 'None'}...")
    print()

print("\n=== Buscando en scripts JSON ===")
import re
for script in soup.find_all('script'):
    text = script.string or ""
    if 'image' in text.lower() or 'Image' in text:
        matches = re.findall(r'"image"[^:]*:\s*"([^"]+)"', text)
        for m in matches[:5]:
            print(f"Script image: {m}")
        matches2 = re.findall(r'"imageUrl"[^:]*:\s*"([^"]+)"', text)
        for m in matches2[:5]:
            print(f"Script imageUrl: {m}")
