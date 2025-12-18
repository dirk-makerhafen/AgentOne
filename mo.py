import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://ollama.com"
MAX_WORKERS = 16

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

session = requests.Session()
session.headers.update(HEADERS)
from datetime import datetime, timedelta, timezone

def is_older_than_x_days(updated_iso: str, days) -> bool:
    if not updated_iso:
        return True  # treat unknown as old
    updated = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
    return updated < datetime.now(timezone.utc) - timedelta(days=days)

def fetch(url):
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def extract_library_links():
    html = fetch(f"{BASE}/search?o=newest")
    soup = BeautifulSoup(html, "html.parser")

    links = set()
    for a in soup.select('a[href^="/library/"]'):
        href = a["href"]
        parts = href.strip("/").split("/")
        if len(parts) == 2:
            links.add(urljoin(BASE, href))

    return links


def extract_model_variants(model_url):
    html = fetch(model_url)
    soup = BeautifulSoup(html, "html.parser")

    variants = {}

    for row in soup.select('div.sm\\:grid'):
        a = row.select_one('a[href^="/library/"]')
        if not a:
            continue

        href = a["href"]
        if "/tags" in href:
            continue

        name = a.text.strip()
        if ":latest" in name:
            continue
        cols = row.select("p")

        variants[name] = {
            "url": urljoin(BASE, href),
            "filesize": cols[0].text.strip() if len(cols) > 0 else "-1",
            "context": cols[1].text.strip() if len(cols) > 1 else None,
            "modalities": [x.strip() for x in cols[2].text.strip().split(",")] if len(cols) > 2 else [],
        }

    for name, variant in variants.items():
        variant["cloud"] =  variant["filesize"] == "-1" or "cloud" in name

    for name, variant in variants.items():
        variant["parameters"]= ""
        if variant["cloud"]:
            variant["filesize"] = -1
        else:
            if ":" in name:
                variant["parameters"] = name.split(":")[-1].lower().strip().split("-")[0]
            try:
                s = float(re.sub(r"[^0-9.]", "", variant["filesize"]))
                if "g" in variant["filesize"].lower(): s = s * 1000
                if "t" in variant["filesize"].lower(): s = s * 1000 * 1000
                variant["filesize"] = int(s)
            except:
                variant["filesize"] = -2
            

        try:
            c = int(re.sub(r"[^0-9.]", "", variant["context"]))
            if "k" in variant["context"].lower(): c = c * 1000
            if "m" in variant["context"].lower(): c = c * 1000 * 1000
            variant["context"] = int(c)
        except:
             variant["context"] = -2
    return variants

def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")

    updated_span = soup.find("span", attrs={"x-test-updated": True})
    if not updated_span:
        return None

    container = updated_span.find_parent("span")
    if not container:
        return None

    updated_at = container.get("title")
    updated_human = updated_span.get_text(strip=True)

    updated_iso = None
    if updated_at:
        try:
            dt = datetime.strptime(updated_at, "%b %d, %Y %I:%M %p UTC")
            updated_iso = dt.isoformat() + "Z"
        except ValueError:
            pass

    display = soup.find("div", id="display")
    display = display.get_text(separator="\n", strip=True) if display else ""
    return {
        "display_text": display,
        "updated": updated_iso,
        "updated_human": updated_human,
    }



def fetch_variant_html(variant):
    try:
        variant["html"] = fetch(variant["url"])
    except Exception as e:
        variant["error"] = str(e)
    return variant


def fetch_variant_content(variant):
    html = fetch(variant["url"])
    variant.update( extract_text(html))
    return variant


def process_model(model_url):
    model_name = model_url.split("/")[-1]
    result = {
        "url": model_url,
        "variants": {}
    }

    variants = extract_model_variants(model_url)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(fetch_variant_content, v): name
            for name, v in variants.items()
        }

        for f in as_completed(futures):
            name = futures[f]
            r = f.result()
            if not is_older_than_x_days(r["updated"], 365*2):
                result["variants"][name] = r

    return model_name, result


def build_model_index():
    result = {}

    libraries = extract_library_links()
    print(f"Found {len(libraries)} base models")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(process_model, url) for url in libraries]

        for f in as_completed(futures):
            model_name, data = f.result()
            result[model_name] = data
            print(f"Success: {model_name}")
            print(result[model_name])

    for name in list(result.keys()):
        if not result[name]["variants"]:
            del result[name]
    return result


if __name__ == "__main__":
    models = build_model_index()

    with open("ollama_models.json", "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2)

    print("Saved ollama_models.json")