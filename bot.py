import json
import re
import time
import hashlib
from typing import Optional, Dict, Any, List

import requests
import xml.etree.ElementTree as ET

RSS_URL = "https://rsshub.app/vk/user/pp4farmtrof"

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"
CACHE_FILE = "translate_cache.json"


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


def discord_post(webhook_url: str, content: str):
    payload = {"content": content}
    r = requests.post(webhook_url, json=payload, timeout=25)
    r.raise_for_status()


def mymemory_translate_short(text_ru: str, cache: dict) -> str:
    text_ru = (text_ru or "").strip()
    if not text_ru:
        return ""

    short = text_ru[:350]
    key = hashlib.md5(short.encode("utf-8")).hexdigest()

    if key in cache:
        return cache[key]

    base = "https://api.mymemory.translated.net/get"
    params = {"q": short, "langpair": "ru|fr"}

    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()

    fr = j.get("responseData", {}).get("translatedText", "") or short
    cache[key] = fr
    return fr


def fetch_rss_posts():
    r = requests.get(RSS_URL, timeout=30)
    r.raise_for_status()

    root = ET.fromstring(r.content)

    posts = []

    for item in root.findall(".//item"):
        title = item.find("title").text or ""
        link = item.find("link").text or ""
        description = item.find("description").text or ""

        text = title + "\n" + description

        post_id = hashlib.md5(link.encode("utf-8")).hexdigest()

        posts.append({
            "id": post_id,
            "url": link,
            "text": text
        })

    return posts


def main():
    config = load_json(CONFIG_FILE, {})
    routes = {norm(k): v for k, v in config.get("routes", {}).items()}
    default_webhook = config.get("default_webhook")

    if not default_webhook:
        raise SystemExit("default_webhook manquant dans config.json")

    state = load_json(STATE_FILE, {"seen": []})
    seen = set(state.get("seen", []))
    cache = load_json(CACHE_FILE, {})

    posts = fetch_rss_posts()

    print("Posts RSS récupérés =", len(posts))

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

        fr = mymemory_translate_short(p["text"], cache)

        msg = (
            f"🎣 Nouvelle capture\n"
            f"📍 Lac : {lake_fr} ({lake_tag})\n"
            f"🔗 {p['url']}\n\n"
            f"🇫🇷 {fr}"
        )

        discord_post(webhook, msg)

        seen.add(p["id"])
        sent += 1
        time.sleep(1)

        if sent >= 5:
            break

    state["seen"] = list(seen)[-5000:]
    save_json(STATE_FILE, state)
    save_json(CACHE_FILE, cache)


if __name__ == "__main__":
    main()
