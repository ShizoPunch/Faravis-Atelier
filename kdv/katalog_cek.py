#!/usr/bin/env python3
"""faravisatelier.com'daki ürünleri okuyup KDV uygulaması için katalog.json üretir.

Kullanım:
    python kdv/katalog_cek.py                       # tüm site (sitemap.xml üzerinden)
    python kdv/katalog_cek.py --kdv 20 --limit 50   # ilk 50 ürün sayfası
    python kdv/katalog_cek.py --site https://faravisatelier.com --cikti kdv/katalog.json

Ürün sayfalarındaki yapılandırılmış veriyi (schema.org Product / JSON-LD, ikas'ın
__NEXT_DATA__ verisi, og/product meta etiketleri) okur. Sitedeki fiyatlar KDV dahil
kabul edilir. Maliyet sitede yoktur; uygulamanın Katalog ekranından bir kez girilir
ve yeniden yüklemede silinmez.
"""
import argparse
import datetime as dt
import gzip
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "Mozilla/5.0 (compatible; FaravisKatalog/1.0; +https://faravisatelier.com)"
SKIP = re.compile(r"/(blog|pages|sayfa|hesap|account|sepet|cart|checkout|arama|search|iletisim|kategori)(/|$)", re.I)


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or data[:2] == b"\x1f\x8b":
                    data = gzip.decompress(data)
                return data.decode(r.headers.get_content_charset() or "utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None
            err = e
        except Exception as e:  # ağ hatası: bekleyip tekrar dene
            err = e
        time.sleep(1.5 * (i + 1))
    print(f"  ! alınamadı: {url} ({err})", file=sys.stderr)
    return None


def sitemap_urls(site):
    """sitemap.xml (ve iç içe sitemap'ler) içindeki tüm sayfa adresleri."""
    todo, seen, pages = [urllib.parse.urljoin(site, "/sitemap.xml")], set(), []
    robots = get(urllib.parse.urljoin(site, "/robots.txt")) or ""
    todo += re.findall(r"(?im)^sitemap:\s*(\S+)", robots)
    while todo:
        u = todo.pop(0)
        if u in seen:
            continue
        seen.add(u)
        body = get(u)
        if not body:
            continue
        try:
            root = ET.fromstring(body.encode("utf-8"))
        except ET.ParseError:
            continue
        for loc in root.iter():
            if loc.tag.endswith("loc") and loc.text:
                link = loc.text.strip()
                (todo if link.endswith(".xml") or "sitemap" in link.rsplit("/", 1)[-1] else pages).append(link)
    host = urllib.parse.urlparse(site).netloc.replace("www.", "")
    out = []
    for p in pages:
        pu = urllib.parse.urlparse(p)
        if pu.netloc.replace("www.", "") == host and pu.path not in ("", "/") and not SKIP.search(pu.path) and p not in out:
            out.append(p)
    return out


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.,]", "", str(v))
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def from_jsonld(page, url):
    found = []
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(html.unescape(raw.strip()))
        except ValueError:
            continue
        for o in walk(data):
            t = o.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                offers = o.get("offers") or {}
                offer_list = offers if isinstance(offers, list) else [offers]
                variants = o.get("hasVariant") or []
                if variants and isinstance(variants, list):
                    for v in variants:
                        vo = v.get("offers") or {}
                        vo = vo[0] if isinstance(vo, list) and vo else vo
                        found.append(item(v.get("name") or o.get("name"), v.get("sku") or o.get("sku"),
                                          num(vo.get("price") or vo.get("lowPrice")), v.get("url") or url))
                    continue
                for of in offer_list:
                    price = num(of.get("price") or of.get("lowPrice"))
                    found.append(item(o.get("name"), o.get("sku") or of.get("sku"), price, o.get("url") or url))
                    break
    return [f for f in found if f["name"] and f["price"]]


def from_next_data(page, url):
    """ikas vitrinleri Next.js; ürün verisi __NEXT_DATA__ içinde durur."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    found = []
    for o in walk(data):
        variants = o.get("variants") if isinstance(o.get("variants"), list) else None
        if not (variants and isinstance(o.get("name"), str)):
            continue
        for v in variants:
            if not isinstance(v, dict):
                continue
            prices = v.get("prices") or []
            p = prices[0] if prices and isinstance(prices[0], dict) else {}
            price = num(p.get("discountPrice")) or num(p.get("sellPrice"))
            vals = [x.get("name") for x in (v.get("variantValues") or []) if isinstance(x, dict) and x.get("name")]
            name = o["name"] + (" – " + " / ".join(vals) if vals and len(variants) > 1 else "")
            found.append(item(name, v.get("sku"), price, url))
        if found:
            break
    return [f for f in found if f["name"] and f["price"]]


def from_meta(page, url):
    def meta(prop):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']*)' % re.escape(prop), page, re.I)
        return html.unescape(m.group(1)) if m else None
    price = num(meta("product:price:amount") or meta("og:price:amount"))
    name = meta("og:title")
    if name and price:
        return [item(re.sub(r"\s*[|–-]\s*Faravis.*$", "", name, flags=re.I), None, price, url)]
    return []


def item(name, sku, price, url):
    return {"name": html.unescape(str(name or "")).strip(), "sku": str(sku or "").strip(), "price": price, "url": url}


def parse_product(page, url):
    return from_jsonld(page, url) or from_next_data(page, url) or from_meta(page, url)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default="https://faravisatelier.com")
    ap.add_argument("--cikti", default=str(Path(__file__).with_name("katalog.json")))
    ap.add_argument("--kdv", type=float, default=20, help="ürünlere yazılacak KDV oranı (varsayılan 20)")
    ap.add_argument("--limit", type=int, default=0, help="en fazla kaç sayfa okunsun (0 = hepsi)")
    ap.add_argument("--bekle", type=float, default=0.4, help="istekler arası saniye (siteyi yormamak için)")
    a = ap.parse_args()

    urls = sitemap_urls(a.site)
    if not urls:
        sys.exit("sitemap.xml okunamadı ya da boş. Siteye erişim var mı?")
    if a.limit:
        urls = urls[: a.limit]
    print(f"{len(urls)} sayfa taranacak…")

    items, seen = [], set()
    for i, u in enumerate(urls, 1):
        page = get(u)
        time.sleep(a.bekle)
        if not page:
            continue
        for it in parse_product(page, u):
            key = it["sku"] or it["name"].lower()
            if key in seen:
                continue
            seen.add(key)
            it.update(mode="gross", rate=a.kdv)
            items.append(it)
        if i % 10 == 0:
            print(f"  {i}/{len(urls)} sayfa · {len(items)} ürün")

    items.sort(key=lambda x: x["name"].lower())
    out = {"source": urllib.parse.urlparse(a.site).netloc, "updated": dt.date.today().strftime("%d.%m.%Y"), "items": items}
    Path(a.cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} ürün → {a.cikti}")


if __name__ == "__main__":
    main()
