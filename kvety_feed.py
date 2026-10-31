#!/usr/bin/env python3
"""Google Merchant Center feed pre kvetyprevas.sk.

E-shop je na mieru (Laravel) a nemá vlastný feed. Produkty berieme z jeho
interného JSON endpointu kategórií (/kategorie/<slug>/produkty?stranka=N),
ktorý používa aj samotný web. Výstup: RSS 2.0 feed s g: atribútmi.

Použitie: python3 kvety_feed.py [vystup.xml]
"""
import html, json, re, sys, time, urllib.request
from xml.sax.saxutils import escape

BASE = "https://kvetyprevas.sk"
UA = "Mozilla/5.0 (NLS Merchant feed; +https://nextlayer.studio)"
# Alkohol vynechávame — v Shopping reklamách je obmedzený a hrozí zamietnutie účtu.
EXCLUDE_CATEGORIES = {"vino", "s-vinom"}
MIN_PRICE = 20.0
EXCLUDE_NAME = re.compile(r"vín(o|a|om)?\b|prosecco|šampan|sekt|\bpiv[oa]?\b|pivov|pivn|whisk|rum\b|likér|borovičk|slivovic", re.I)
# Hlavné skupiny pre custom_label_0 (delenie PMax / Shopping podľa sortimentu).
GROUPS = [  # regexy nad textom bez diakritiky; poradie = priorita
    ("smutocne", r"smut|venie?c|venc|truhl|spomien|zapich|dusick"),
    ("doplnky", r"balon|vaz[ay]?\b|sviec|cokolad|toffifee|medved|keramik|poukaz|plysak|cukrik|pralink"),
    ("kose", r"\bkos\b|kosik|kose\b"),
    ("boxy", r"\bbox|stabiliz"),
    ("ruze", r"\bruz[iea]\b|\bruz\b|trsov"),
    ("kytice", r"kytic|\bset\b|gerber|frez|hortenz|karafiat|lali|slnecn|tulip|orchid|aranzman"),
]

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)

def categories():
    req = urllib.request.Request(BASE + "/", headers={"User-Agent": UA})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    return sorted(set(re.findall(r"https://kvetyprevas\.sk/kategorie/([A-Za-z0-9-]+)", page)))

def num(price_text, fallback):
    m = re.search(r"\d+(?:[.,]\d+)?", str(price_text or ""))
    return float(m.group(0).replace(",", ".")) if m else float(fallback)

def _norm(t):
    return t.lower().translate(str.maketrans("áäčďéíĺľňóôŕšťúýž", "aacdeillnoorstuyz"))

def group_for(name, own_category, others):
    # Najprv názov produktu, potom jeho vlastná kategória, až potom ostatné zaradenia.
    for text in (name, own_category, " ".join(others)):
        t = _norm(text)
        for group, pattern in GROUPS:
            if re.search(pattern, t):
                return group
    return "ostatne"

def price_bucket(p):
    if p < 35: return "do-35"
    if p < 60: return "35-60"
    if p < 100: return "60-100"
    return "nad-100"

def collect():
    products, seen_in = {}, {}
    for cat in categories():
        page = 1
        while True:
            try:
                d = get_json(f"{BASE}/kategorie/{cat}/produkty?stranka={page}")
            except Exception as e:
                print(f"! {cat} str.{page}: {e}", file=sys.stderr)
                break
            for p in d.get("data", []):
                products.setdefault(p["id"], p)
                seen_in.setdefault(p["id"], set()).add(cat)
            if page >= d.get("meta", {}).get("last_page", 1):
                break
            page += 1
            time.sleep(0.3)
    return products, seen_in

def build(products, seen_in):
    items, skipped = [], 0
    for pid, p in sorted(products.items()):
        eco = p.get("ecommerce") or {}
        cats = seen_in.get(pid, set())
        if cats & EXCLUDE_CATEGORIES or EXCLUDE_NAME.search(p.get("name", "")):
            skipped += 1
            continue
        price = num(p.get("thumbnail_price"), p.get("price") or eco.get("price") or 0)
        # Doručenie je možné až od košíka 20 € — lacnejšie doplnky samostatne kúpiť nejde.
        if price < MIN_PRICE or not p.get("image_url"):
            skipped += 1
            continue
        types = [eco.get(k) for k in ("item_category", "item_category2", "item_category3", "item_category4", "item_category5") if eco.get(k)]
        cat_name = (p.get("category") or {}).get("name", "")
        group = group_for(p.get("name", ""), cat_name, [*types, *cats])
        title = html.unescape(p["name"]).strip()
        desc = f"{title} od rodinného kvetinárstva Kvety pre Vás v Bratislave. Čerstvo viazané v deň objednávky, doručenie po Bratislave a okolí do 1–2 hodín, 365 dní v roku."
        if types:
            desc += " Kategória: " + ", ".join(types) + "."
        stock = p.get("stock")
        avail = "out_of_stock" if (stock is not None and stock <= 0) else "in_stock"
        items.append({
            "id": str(eco.get("item_id") or pid), "title": title[:150], "description": desc[:5000],
            "link": p["url"], "image_link": p["image_url"], "price": f"{price:.2f} EUR",
            "availability": avail, "brand": "Kvety pre Vás", "condition": "new",
            "identifier_exists": "no", "product_type": " > ".join(types[:3]) or cat_name,
            "custom_label_0": group, "custom_label_1": price_bucket(price),
            "custom_label_2": "do-2-hodin" if "dorucenie-do-2-hodin" in cats else "standard",
            "custom_label_3": "najoblubenejsie" if any(t.get("slug") == "najoblubenejsie" for t in p.get("tags") or []) else "",
        })
    return items, skipped

def to_rss(items):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel>',
           "<title>Kvety pre Vás – produkty</title><link>https://kvetyprevas.sk</link>",
           "<description>Google Merchant Center feed (generuje NextLayer Studio)</description>"]
    for it in items:
        out.append("<item>")
        for k, v in it.items():
            if not v:
                continue
            tag = k if k in ("title", "link", "description") else "g:" + k
            out.append(f"<{tag}>{escape(v)}</{tag}>")
        out.append("</item>")
    out.append("</channel></rss>")
    return "\n".join(out)

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else "kvety-google-feed.xml"
    products, seen_in = collect()
    items, skipped = build(products, seen_in)
    if len(items) < 350:  # ochrana: pri výpadku webu radšej neprepísať dobrý feed polovičným
        sys.exit(f"Iba {len(items)} produktov — feed neprepisujem.")
    tmp = dest + ".tmp"
    open(tmp, "w", encoding="utf-8").write(to_rss(items))
    import os; os.replace(tmp, dest)
    from collections import Counter
    print(f"OK {len(items)} produktov (vynechané {skipped}) -> {dest}")
    print(dict(Counter(i["custom_label_0"] for i in items)))
