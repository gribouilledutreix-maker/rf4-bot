import json
import re
import time
import hashlib
from typing import Optional, Dict, Any, List

import requests
from bs4 import BeautifulSoup

VK_MOBILE_URL = "https://m.vk.com/pp4farmtrof"

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"
CACHE_FILE = "translate_cache.json"

UA = "RF4FR-DiscordRelay/1.0"
HEADERS = {"User-Agent": UA}


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def norm(s: str) -> str:
    return (s or "").strip().lower().replace("ё", "е")


def extract_hashtags(text: str) -> List[str]:
    raw = re.findall(r"#([0-9A-Za-zА-Яа-яЁё_\.]+)", text or "")
    return [norm("#" + t) for t in raw]


def discord_post(webhook_url: str, content: str, image_url: Optional[str] = None):
    payload: Dict[str, Any] = {"content": content}
    if image_url:
        payload["embeds"] = [{"image": {"url": image_url}}]
    r = requests.post(webhook_url, json=payload, timeout=25)
    r.raise_for_status()


def mymemory_translate_short(text_ru: str, cache: dict, email: Optional[str]) -> str:
    text_ru = (text_ru or "").strip()
    if not text_ru:
        return ""

    short = text_ru[:350]
    key = hashlib.md5(short.encode("utf-8")).hexdigest()

    if key in cache:
        return cache[key]

    base = "https://api.mymemory.translated.net/get"
    params = {"q": short, "langpair": "ru|fr"}

    if email:
        params["de"] = email

    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()

    fr = j.get("responseData", {}).get("translatedText", "") or short
    cache[key] = fr
    return fr


def fetch_posts_mobile(limit=12) -> List[dict]:
    print("Connexion à VK mobile...")
    r = requests.get(VK_MOBILE_URL, headers=HEADERS, timeout=30)
    print("Statut HTTP VK =", r.status_code)

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select(".wall_item")

    print("Nombre d'éléments .wall_item trouvés =", len(items))

    posts = []

    for it in items:
        text = it.get_text(" ", strip=True)

        if "#" not in text:
            continue

        a = it.select_one('a[href*="/wall"]')
        href = a.get("href") if a else ""
        m = re.search(r"/wall(-?\d+_\d+)", href or "")
        post_id = m.group(1) if m else hashlib.md5(text.encode("utf-8")).hexdigest()

        post_url = "https://vk.com" + href if href.startswith("/") else VK_MOBILE_URL

        img = it.select_one("img")
        img_url = img.get("src") if img else None
        if img_url and img_url.startswith("//"):
            img_url = "https:" + img_url

        posts.append({
            "id": post_id,
            "url": post_url,
            "text": text,
            "image_url": img_url
        })

    return posts[:limit]


def main():
    config = load_json(CONFIG_FILE, {})
    routes = {norm(k): v for k, v in config.get("routes", {}).items()}
    default_webhook = config.get("default_webhook")

    if not default_webhook:
        raise SystemExit("default_webhook manquant dans config.json")

    # === TEST DISCORD ===
    discord_post(default_webhook, "✅ Test : le bot démarre correctement.")
    print("Message test envoyé sur Discord.")

    state = load_json(STATE_FILE, {"seen": []})
    seen = set(state.get("seen", []))
    cache = load_json(CACHE_FILE, {})

    posts = fetch_posts_mobile(limit=12)

    print("VK: posts récupérés =", len(posts))

    if posts:
        print("Exemple texte VK :", posts[0]["text"][:200])

    sent = 0

    for p in reversed(posts):
        if p["id"] in seen:
            continue

        tags = extract_hashtags(p["text"])
        chosen = None

        for t in tags:
            if t in routes:
                chosen = (t, routes[t])
                break

        if chosen:
            lake_tag, route = chosen
            lake_fr = route.get("lake_fr", "Lac inconnu")
            webhook = route.get("webhook", default_webhook)
        else:
            lake_tag, lake_fr, webhook = "(non détecté)", "À trier", default_webhook

        fr = mymemory_translate_short(p["text"], cache, None)

        msg = (
            f"🎣 Nouvelle capture\n"
            f"📍 Lac : {lake_fr} ({lake_tag})\n"
            f"🔗 {p['url']}\n\n"
            f"🇫🇷 {fr}"
        )

        discord_post(webhook, msg, image_url=p.get("image_url"))

        seen.add(p["id"])
        sent += 1
        time.sleep(1)

        if sent >= 3:
            break

    state["seen"] = list(seen)[-5000:]
    save_json(STATE_FILE, state)
    save_json(CACHE_FILE, cache)


if __name__ == "__main__":
    main()
