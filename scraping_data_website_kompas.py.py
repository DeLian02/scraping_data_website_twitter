import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
from urllib.parse import urljoin, urlparse

# URL target
BASE_URL = 'https://www.kompas.com/'

# Headers (sebagai browser)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/91.0.4472.124 Safari/537.36'
}

def get_soup(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Gagal akses {url}: {e}")
        return None

def extract_article_metadata(article_url):
    """Ambil metadata artikel dari halaman artikel Kompas."""
    soup = get_soup(article_url)
    if not soup:
        return None

    # Ambil title: prioritas meta og:title, lalu <title>
    title = None
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title = og_title['content'].strip()
    if not title:
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else 'Tidak ada judul'

    # Ambil description/summary: meta description atau og:description
    summary = None
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    og_desc = soup.find('meta', property='og:description')
    if meta_desc and meta_desc.get('content'):
        summary = meta_desc['content'].strip()
    elif og_desc and og_desc.get('content'):
        summary = og_desc['content'].strip()
    else:
        # fallback: paragraf pertama
        p = soup.find('p')
        summary = p.get_text(strip=True) if p else 'Tidak ada ringkasan'

    # Ambil author: meta name='author' atau meta property='article:author'
    author = None
    meta_author = soup.find('meta', attrs={'name': 'author'})
    art_author = soup.find('meta', property='article:author')
    if meta_author and meta_author.get('content'):
        author = meta_author['content'].strip()
    elif art_author and art_author.get('content'):
        author = art_author['content'].strip()
    else:
        # Kadang ada di elemen dengan class 'read__author' atau 'author'
        a_tag = soup.find(class_='read__author') or soup.find(class_='author')
        author = a_tag.get_text(strip=True) if a_tag else 'Tidak diketahui'

    # Ambil publication time: meta property article:published_time atau time tag
    publication_time = None
    meta_time = soup.find('meta', property='article:published_time')
    if meta_time and meta_time.get('content'):
        publication_time = meta_time['content'].strip()
    else:
        time_tag = soup.find('time')
        if time_tag and time_tag.get('datetime'):
            publication_time = time_tag['datetime'].strip()
        elif time_tag:
            publication_time = time_tag.get_text(strip=True)
        else:
            publication_time = 'Tidak ada waktu'

    # Ambil image utama: og:image
    image_url = None
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        image_url = og_image['content'].strip()
    else:
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            image_url = urljoin(article_url, img_tag['src'])
        else:
            image_url = 'Tidak ada gambar'

    return {
        'title': title,
        'link': article_url,
        'publication_time': publication_time,
        'author': author,
        'image_url': image_url,
        'summary': summary
    }

def collect_article_links_from_home():
    """Kumpulkan link artikel dari halaman utama Kompas.
       Menggunakan beberapa heuristik untuk menemukan link artikel yang valid."""
    soup = get_soup(BASE_URL)
    if not soup:
        return []

    links = set()

    # 1) Cari tag <article> dan ambil <a> di dalamnya
    for art in soup.find_all('article'):
        a = art.find('a', href=True)
        if a:
            href = urljoin(BASE_URL, a['href'])
            links.add(href)

    # 2) Cari semua <a> yang menuju ke domain kompas.com dan mengandung pola /read/ atau /travel/ dll.
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href:
            continue
        parsed = urlparse(href)
        # buat absolute
        if not parsed.netloc:
            href = urljoin(BASE_URL, href)
            parsed = urlparse(href)
        if 'kompas.com' in parsed.netloc:
            # filter internal navigasi (ke subseksi yang bukan artikel) dengan heuristik:
            if '/read/' in parsed.path or '/travel/' in parsed.path or '/sains/' in parsed.path or '/internasional/' in parsed.path or '/tekno/' in parsed.path or '/health/' in parsed.path or '/edu/' in parsed.path:
                links.add(href)
            else:
                # jika teks anchor mengandung huruf dan panjang > 20, kemungkinan judul artikel
                text = a.get_text(strip=True)
                if len(text) > 30:
                    links.add(href)

    # Bersihkan dan urutkan
    cleaned = [l.split('#')[0] for l in links]  # hapus fragment
    unique_links = list(dict.fromkeys(cleaned))  # jaga urutan & dedup
    print(f"Menemukan {len(unique_links)} link kandidat artikel dari beranda.")
    return unique_links

def main():
    collected_data = []
    article_links = collect_article_links_from_home()

    # Batasi jumlah artikel yang diambil (opsional). Hapus atau ubah sesuai kebutuhan.
    MAX_ARTICLES = 50
    count = 0

    for link in article_links:
        if count >= MAX_ARTICLES:
            break
        # hanya proses link yang sepertinya artikel (cek path)
        if not ('kompas.com' in urlparse(link).netloc):
            continue

        print(f"Memproses: {link}")
        meta = extract_article_metadata(link)
        if meta:
            collected_data.append(meta)
            count += 1
        # jeda singkat agar tidak membebani server
        time.sleep(0.4)

    # Ekspor hasil
    if not collected_data:
        print("Tidak ada data yang berhasil di-scrape.")
        return

    file_name_base = 'list_post_kompas_lengkap'
    output_json_data = {"list_post": collected_data}
    with open(f'{file_name_base}.json', 'w', encoding='utf-8') as f:
        json.dump(output_json_data, f, ensure_ascii=False, indent=4)
    print(f"Data berhasil diekspor ke {file_name_base}.json")

    df = pd.DataFrame(collected_data)
    df.to_csv(f'{file_name_base}.csv', index=False, encoding='utf-8')
    print(f"Data berhasil diekspor ke {file_name_base}.csv")

    try:
        df.to_excel(f'{file_name_base}.xlsx', index=False)
        print(f"Data berhasil diekspor ke {file_name_base}.xlsx")
    except Exception as e:
        print(f"[WARNING] Gagal ekspor Excel: {e}")

if __name__ == '__main__':
    main()
