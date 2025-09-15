import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
from urllib.parse import urljoin, urlparse

# URL target
BASE_URL = "https://www.liputan6.com/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/91.0.4472.124 Safari/537.36"
}

def get_soup(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Gagal akses {url}: {e}")
        return None

def extract_article_metadata(article_url):
    """Ambil metadata artikel dari halaman Liputan6."""
    soup = get_soup(article_url)
    if not soup:
        return None

    # Judul
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    else:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "Tidak ada judul"

    # Ringkasan
    summary = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        summary = meta_desc["content"].strip()
    else:
        p = soup.find("p")
        summary = p.get_text(strip=True) if p else "Tidak ada ringkasan"

    # Author
    author = None
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author["content"].strip()
    else:
        author_tag = soup.find(class_="read__author") or soup.find(class_="author")
        author = author_tag.get_text(strip=True) if author_tag else "Tidak diketahui"

    # Waktu publikasi
    publication_time = None
    meta_time = soup.find("meta", property="article:published_time")
    if meta_time and meta_time.get("content"):
        publication_time = meta_time["content"].strip()
    else:
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            publication_time = time_tag["datetime"].strip()
        elif time_tag:
            publication_time = time_tag.get_text(strip=True)
        else:
            publication_time = "Tidak ada waktu"

    # Gambar
    image_url = None
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        image_url = og_image["content"].strip()
    else:
        img_tag = soup.find("img")
        image_url = urljoin(article_url, img_tag["src"]) if img_tag and img_tag.get("src") else "Tidak ada gambar"

    return {
        "title": title,
        "link": article_url,
        "publication_time": publication_time,
        "author": author,
        "image_url": image_url,
        "summary": summary,
    }

def collect_article_links_from_home():
    """Kumpulkan link artikel dari beranda Liputan6."""
    soup = get_soup(BASE_URL)
    if not soup:
        return []

    links = set()

    # Cari semua anchor
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href:
            continue
        parsed = urlparse(href)
        # buat absolute
        if not parsed.netloc:
            href = urljoin(BASE_URL, href)
            parsed = urlparse(href)
        if "liputan6.com" in parsed.netloc:
            # heuristik: artikel biasanya mengandung /read/ atau /show/
            if "/read/" in parsed.path:
                links.add(href)

    unique_links = list(dict.fromkeys(links))  # dedup
    print(f"Menemukan {len(unique_links)} link kandidat artikel dari beranda.")
    return unique_links

def main():
    collected_data = []
    article_links = collect_article_links_from_home()

    MAX_ARTICLES = 50
    count = 0

    for link in article_links:
        if count >= MAX_ARTICLES:
            break
        print(f"Memproses: {link}")
        meta = extract_article_metadata(link)
        if meta:
            collected_data.append(meta)
            count += 1
        time.sleep(0.4)  # jeda agar tidak membebani server

    if not collected_data:
        print("Tidak ada data yang berhasil di-scrape.")
        return

    file_name_base = "list_post_liputan6"
    output_json_data = {"list_post": collected_data}
    with open(f"{file_name_base}.json", "w", encoding="utf-8") as f:
        json.dump(output_json_data, f, ensure_ascii=False, indent=4)
    print(f"Data berhasil diekspor ke {file_name_base}.json")

    df = pd.DataFrame(collected_data)
    df.to_csv(f"{file_name_base}.csv", index=False, encoding="utf-8")
    print(f"Data berhasil diekspor ke {file_name_base}.csv")

    try:
        df.to_excel(f"{file_name_base}.xlsx", index=False)
        print(f"Data berhasil diekspor ke {file_name_base}.xlsx")
    except Exception as e:
        print(f"[WARNING] Gagal ekspor Excel: {e}")

if __name__ == "__main__":
    main()
