import os
import json
import re
import time
import hashlib
from typing import Optional, Dict, Any, List

import requests

VK_DOMAIN = "pp4farmtrof"
VK_API_VERSION = "5.131"

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"
CACHE_FILE = "translate_cache.json"

VK_TOKEN = os.environ.get("VK_TOKEN")


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


def vk_wall_get(count=10) -> list[dict]:
    if not VK_TOKEN:
        raise SystemExit("VK_TOKEN manquant")

    url = "https://api.vk.com/method/wall.get"
    params = {
        "domain": VK_DOMAIN,
        "count": count,
        "v": VK_API_VERSION,
        "access_token": VK_TOKEN
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    return data["response"]["items"]


def pick_best_photo_url(item: dict) -> Optional[str]:
    for att in item.get("attachments", []):
        if att.get("type") == "photo":
            sizes = att.get("photo", {}).get("sizes", [])
            if sizes:
                best = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
                return best.get("url")
    return None


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


def main():
    config = load_json(CONFIG_FILE, {})
    routes = {norm(k): v for k, v in config.get("routes", {}).items()}
    default_webhook = config.get("default_webhook")

    if not default_webhook:
        raise SystemExit("default_webhook manquant dans config.json")

    state = load_json(STATE_FILE, {"seen": []})
    seen = set(state.get("seen", []))
    cache = load_json(CACHE_FILE, {})

    items = vk_wall_get(count=15)

    print("Posts récupérés depuis VK =", len(items))

    for it in reversed(items):
        post_id = f"{it.get('owner_id')}_{it.get('id')}"

        if post_id in seen:
            continue

        text_ru = it.get("text", "")
        tags = extract_hashtags(text_ru)

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

        photo_url = pick_best_photo_url(it)
        post_url = f"https://vk.com/wall{post_id}"

        fr = mymemory_translate_short(text_ru, cache)

        msg = (
            f"🎣 Nouvelle capture\n"
            f"📍 Lac : {lake_fr} ({lake_tag})\n"
            f"🔗 {post_url}\n\n"
            f"🇫🇷 {fr}"
        )

        discord_post(webhook, msg, image_url=photo_url)

        seen.add(post_id)
        time.sleep(1)

    state["seen"] = list(seen)[-5000:]
    save_json(STATE_FILE, state)
    save_json(CACHE_FILE, cache)


if __name__ == "__main__":
    main()
