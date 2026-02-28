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

UA = "RF4FR-DiscordRelay/1.0"


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
        raise SystemExit("VK_TOKEN manquant dans GitHub Secrets")

    url = "https://api.vk.com/method/wall.get"
    params = {
        "domain": VK_DOMAIN,
        "count": count,
        "v": VK_API_VERSION,
        "access_token": VK_TOKEN
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    j = r.json()

    if "error" in j:
        raise RuntimeError(j["error"])

    return j["response"]["items"]


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

    sent = 0

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
        sent += 1
        time.sleep(1)

        if sent >= 5:
            break

    state["seen"] = list(seen)[-5000:]
    save_json(STATE_FILE, state)
    save_json(CACHE_FILE, cache)


if __name__ == "__main__":
    main()import json
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


def safe_snip(s: str, n: int = 400) -> str:
    s = (s or "").replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def pick_best_img_from_container(container) -> Optional[str]:
    # VK mobile: img src parfois en //... ou https://...
    imgs = container.select("img[src]")
    if not imgs:
        return None

    # on prend la 1ère image "grande" si possible, sinon la 1ère
    best = None
    best_len = -1
    for img in imgs:
        src = img.get("src")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if "userapi" in src or "vkuser" in src or "vk.com" in src:
            score = len(src)
        else:
            score = len(src)
        if score > best_len:
            best_len = score
            best = src
    return best


def find_post_container(a_tag):
    """
    On remonte dans les parents pour trouver un bloc qui ressemble à un post.
    Heuristique: un parent qui contient du texte + potentiellement images.
    """
    cur = a_tag
    for _ in range(8):
        if not cur:
            break
        # si le bloc contient plusieurs liens wall ou beaucoup de texte, c'est probablement un post
        text = cur.get_text(" ", strip=True)
        wall_links = cur.select('a[href*="/wall"]')
        if len(text) > 80 and len(wall_links) >= 1:
            return cur
        cur = cur.parent
    return a_tag.parent


def fetch_posts_mobile(limit=12) -> List[dict]:
    print("Connexion à VK mobile...")
    r = requests.get(VK_MOBILE_URL, headers=HEADERS, timeout=30)
    print("Statut HTTP VK =", r.status_code)
    r.raise_for_status()

    html = r.text or ""
    print("Taille HTML =", len(html))

    soup = BeautifulSoup(html, "html.parser")

    # DEBUG: page title et un bout de texte
    title = soup.title.get_text(strip=True) if soup.title else "(pas de title)"
    body_text = soup.get_text(" ", strip=True)
    print("Titre page =", safe_snip(title, 120))
    print("Extrait texte page =", safe_snip(body_text, 250))

    # Nouvelle stratégie: trouver tous les liens vers /wall (posts)
    wall_as = soup.select('a[href*="/wall"]')
    print("Nombre de liens /wall trouvés =", len(wall_as))

    # Si 0, on affiche un extrait HTML pour adapter ensuite
    if len(wall_as) == 0:
        print("DEBUG HTML (début) =", safe_snip(html, 500))
        # on tente aussi une recherche d'autres patterns
        for pat in ["wall", "post", "Запись", "Войти", "Sign in", "login"]:
            if pat.lower() in html.lower():
                print("DEBUG: pattern trouvé dans HTML =", pat)
        return []

    posts_by_id: Dict[str, dict] = {}

    for a in wall_as:
        href = a.get("href") or ""
        # ex: /wall-123_456 ou /wall-123_456?reply=...
        m = re.search(r"/wall(-?\d+_\d+)", href)
        if not m:
            continue
        pid = m.group(1)

        if pid in posts_by_id:
            continue

        container = find_post_container(a)
        text = container.get_text(" ", strip=True)
        img_url = pick_best_img_from_container(container)

        post_url = "https://vk.com" + href if href.startswith("/") else href
        posts_by_id[pid] = {
            "id": pid,
            "url": post_url,
            "text": text,
            "image_url": img_url
        }

    posts = list(posts_by_id.values())

    # On garde ceux qui ont au moins un hashtag (ton besoin)
    posts = [p for p in posts if "#" in (p.get("text") or "")]

    print("Posts uniques trouvés (avec #) =", len(posts))
    if posts:
        print("Exemple post id =", posts[0]["id"])
        print("Exemple post texte =", safe_snip(posts[0]["text"], 220))

    return posts[:limit]


def main():
    config = load_json(CONFIG_FILE, {})
    routes = {norm(k): v for k, v in config.get("routes", {}).items()}
    default_webhook = config.get("default_webhook")

    if not default_webhook:
        raise SystemExit("default_webhook manquant dans config.json")

    # Email MyMemory optionnel via secrets.json (si tu l'as configuré)
    secrets = load_json("secrets.json", {})
    mymemory_email = secrets.get("MYMEMORY_EMAIL")

    state = load_json(STATE_FILE, {"seen": [], "tested": False})
    seen = set(state.get("seen", []))
    cache = load_json(CACHE_FILE, {})

    # Envoi test Discord UNE SEULE FOIS (évite de spam)
    if not state.get("tested", False):
        discord_post(default_webhook, "✅ Test : le bot démarre correctement.")
        print("Message test envoyé sur Discord (une seule fois).")
        state["tested"] = True
        save_json(STATE_FILE, state)

    posts = fetch_posts_mobile(limit=12)
    print("VK: posts récupérés =", len(posts))

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

        fr = mymemory_translate_short(p["text"], cache, mymemory_email)

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
