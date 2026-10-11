#!/usr/bin/env python3
"""Faravis Atelier — Instagram carousel (kaydırmalı gönderi) şablonu.

Tek ürün fotoğrafından 4 kare üretir, hepsi aynı sahnede:
  1. Kapak        ürün + başlık
  2. Detay        ürünün en ayrıntılı bölgesi yakın plan (kanca, mandal, logo…)
  3. Ölçü/malzeme ürün + genişlik ölçü çizgisi + özellik listesi
  4. Fiyat/çağrı  paket fiyatları (kdv/katalog.json'dan) + sipariş çağrısı

Örnek:
  python studio/carousel.py gelen/askı.jpg --scene kum \\
      --baslik "Omuzlu Ceket Askısı" --alt "Ceviz · lama kanca" \\
      --detay "Fırınlanmış kayın gövde, el zımparası" \\
      --olcu "Genişlik: 44 cm; Gövde: 4 cm; Kanca: 9 cm" --malzeme "%100 fırınlanmış kayın" \\
      --urun "omuzlu ceket lama"
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import studio as S

W, H = S.FORMATS["portrait"]
U = W / 1080


# ---------------------------------------------------------------- yardımcılar
def suffix(n: int) -> str:
    """Türkçe sayı eki: 12'li, 6'lı, 10'lu, 100'lü (son okunan kelimenin ünlüsüne göre)."""
    ones = {1: "li", 2: "li", 3: "lü", 4: "lü", 5: "li", 6: "lı", 7: "li", 8: "li", 9: "lu"}
    tens = {1: "lu", 2: "li", 3: "lu", 4: "lı", 5: "li", 6: "lı", 7: "li", 8: "li", 9: "lı"}
    if n % 10:
        return ones[n % 10]
    if n % 100:
        return tens[(n % 100) // 10]
    if n % 1000:
        return "lü"  # yüz
    return "li"  # bin


def tl(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "₺" + (s[:-3] if s.endswith(",00") else s)


def catalog_prices(query: str) -> tuple[str, list[tuple[int, float]]] | None:
    """kdv/katalog.json'da ürünü bulur; paket boyu → paket fiyatı (KDV dahil) listesi döner."""
    path = S.ROOT / "kdv" / "katalog.json"
    if not path.exists():
        return None
    words = query.lower().split()
    items = json.loads(path.read_text())["items"]
    hit = next((x for x in items if all(w in x["name"].lower() for w in words)), None)
    if not hit:
        return None
    m = re.match(r"Paket: ([\d, ]+) adet", hit.get("note", ""))
    if not m:
        return hit["name"], [(1, hit["price"])]
    packs = [int(p) for p in m.group(1).split(",")]
    unit = {packs[0]: hit["price"], **{t["min"]: t["price"] for t in hit.get("tiers", [])}}
    return hit["name"], [(p, round(unit.get(p, hit["price"]) * p, 2)) for p in packs]


def base(scene_name: str, logo=True) -> tuple[Image.Image, S.Scene]:
    sc = S.SCENES[scene_name](W, H)
    img = sc.bg.convert("RGB").copy()
    if logo:
        img = S.add_type(img, sc, None, None, True, W, H)
    return img, sc


def page_mark(img: Image.Image, sc: S.Scene, i: int, n: int = 4):
    """Sağ üstte sayfa göstergesi: 2 / 4."""
    d = ImageDraw.Draw(img)
    S.spaced(d, (W - 96 * U, 96 * U), f"{i} / {n}", S.font("sans_light", int(15 * U)), sc.ink, 3 * U)


def eyebrow(d, xy, text, sc, size=15):
    S.spaced(d, xy, S.tr_upper(text), S.font("sans_medium", int(size * U)), sc.ink, 6 * U)


def wrap(d, text, fnt, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) > width and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def detail_box(prod: Image.Image, frac=0.46) -> tuple[int, int, int, int]:
    """Ürünün en çok kenar/ayrıntı barındıran kare bölgesi (kanca, mandal, logo baskısı)."""
    from scipy import ndimage

    a = np.asarray(prod.getchannel("A"), np.float32) / 255
    g = np.asarray(prod.convert("L"), np.float32)
    e = (np.abs(ndimage.sobel(g, 0)) + np.abs(ndimage.sobel(g, 1))) * a
    e += np.abs(ndimage.sobel(a, 0)) * 40 + np.abs(ndimage.sobel(a, 1)) * 40  # silüet kıvrımları
    h, w = a.shape
    s = int(max(h, w) * frac)
    s = min(s, h, w) if min(h, w) > s * 0.6 else max(min(h, w), int(s * 0.6))
    ii = e.cumsum(0).cumsum(1)
    best, bx, by = -1, 0, 0
    step = max(4, s // 12)
    for y in range(0, max(1, h - s + 1), step):
        for x in range(0, max(1, w - s + 1), step):
            y1, x1 = min(h, y + s) - 1, min(w, x + s) - 1
            v = ii[y1, x1] - (ii[y - 1, x1] if y else 0) - (ii[y1, x - 1] if x else 0) + (ii[y - 1, x - 1] if x and y else 0)
            if v > best:
                best, bx, by = v, x, y
    return bx, by, min(w, bx + s), min(h, by + s)


def paste_product(img, sc, prod, box_w, box_h, cx, cy, shadow=True):
    pw, ph = prod.size
    k = min(box_w / pw, box_h / ph)
    p = prod.resize((max(1, int(pw * k)), max(1, int(ph * k))), Image.LANCZOS)
    x, y = int(cx - p.width / 2), int(cy - p.height / 2)
    a = p.getchannel("A")
    if shadow:
        sh = Image.new("L", (W, H), 0)
        sh.paste(a, (x + int(10 * U), y + int(16 * U)))
        sh = sh.filter(ImageFilter.GaussianBlur(16 * U)).point(lambda v: int(v * 0.42 * sc.shadow))
        img = Image.composite(Image.new("RGB", (W, H), (35, 26, 20)), img, sh)
    rgb = S.match_light(p.convert("RGB"), a, img, x, y)
    img.paste(rgb, (x, y), a)
    return img, (x, y, x + p.width, y + p.height)


# ---------------------------------------------------------------- kareler
def slide_cover(path, scene, title, subtitle, out_dir):
    W_, H_ = W, H
    sc = S.SCENES[scene](W_, H_)
    if (title or subtitle) and not sc.fixed_floor:
        sc.floor_y -= 0.05; sc.max_h -= 0.06
    prod = S.enhance(S.cutout(path, out_dir / ".cache"))
    img = S.compose(prod, sc, W_, H_)
    img = S.grain(img, 3.2)
    img = S.add_type(img, sc, title, subtitle, True, W_, H_)
    d = ImageDraw.Draw(img)
    S.spaced(d, (W - 150 * U, H - 40 * U), "KAYDIR  →", S.font("sans_light", int(13 * U)), sc.ink, 4 * U)
    return img


def slide_detail(prod, scene, text):
    """Büyüteç: ürünün en ayrıntılı bölgesi yuvarlak çerçevede yakın plan; kırpma kenarları çemberin dışında kalır."""
    img, sc = base(scene)
    D = int(W * 0.70)
    cx, cy = W // 2, int(H * 0.42)
    x0, y0, x1, y1 = detail_box(prod)
    side = x1 - x0
    side = max(side, int(D / 1.8))  # en fazla 1,8 kat büyüt (kaynak çözünürlük yetmezse bulanıklaşır)
    mx, my = (x0 + x1) // 2, (y0 + y1) // 2
    box = (mx - side // 2, my - side // 2, mx - side // 2 + side, my - side // 2 + side)
    crop = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    crop.paste(prod.crop((max(0, box[0]), max(0, box[1]), min(prod.width, box[2]), min(prod.height, box[3]))),
               (max(0, -box[0]), max(0, -box[1])))
    crop = crop.resize((D, D), Image.LANCZOS)
    # çemberin içi: sahnenin aynı bölgesi + yakın plan ürün
    lens = img.crop((cx - D // 2, cy - D // 2, cx + D // 2, cy + D // 2)).filter(ImageFilter.GaussianBlur(6 * U))
    a = crop.getchannel("A")
    lens.paste(S.match_light(crop.convert("RGB"), a, lens, 0, 0), (0, 0), a)
    mask = Image.new("L", (D * 4, D * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, D * 4 - 1, D * 4 - 1], fill=255)
    mask = mask.resize((D, D), Image.LANCZOS)  # yumuşak kenarlı çember
    sh = Image.new("L", (W, H), 0)
    sh.paste(mask, (cx - D // 2 + int(8 * U), cy - D // 2 + int(14 * U)))
    sh = sh.filter(ImageFilter.GaussianBlur(22 * U)).point(lambda v: int(v * 0.35 * sc.shadow))
    img = Image.composite(Image.new("RGB", (W, H), (35, 26, 20)), img, sh)
    img.paste(lens, (cx - D // 2, cy - D // 2), mask)
    d = ImageDraw.Draw(img)
    d.ellipse([cx - D // 2, cy - D // 2, cx + D // 2, cy + D // 2], outline=sc.ink, width=max(1, int(1.5 * U)))
    eyebrow(d, (W / 2, H * 0.80), "Detay", sc)
    if text:
        fnt = S.font("display_italic", int(46 * U))
        for i, line in enumerate(wrap(d, text, fnt, W * 0.78)[:3]):
            d.text((W / 2, H * 0.86 + i * 54 * U), line, font=fnt, fill=sc.ink, anchor="ms")
    page_mark(img, sc, 2)
    return S.grain(img, 3.0)


def slide_specs(prod, scene, olcu, malzeme):
    img, sc = base(scene)
    img, (x0, y0, x1, y1) = paste_product(img, sc, prod, W * 0.70, H * 0.40, W / 2, H * 0.36)
    d = ImageDraw.Draw(img)
    specs = [tuple(p.strip() for p in re.split(r":\s*|\s+(?=\d)", s, maxsplit=1)) for s in olcu.split(";") if s.strip()] if olcu else []
    specs = [s for s in specs if len(s) == 2]
    if malzeme:
        specs.append(("Malzeme", malzeme))
    # genişlik ölçü çizgisi (ilk ölçü "genişlik" ise)
    width = next((v for k, v in specs if k.lower().startswith("geniş")), None)
    if width:
        ly = y1 + 34 * U
        d.line([(x0, ly), (x1, ly)], fill=sc.ink, width=max(1, int(1.4 * U)))
        for x in (x0, x1):
            d.line([(x, ly - 9 * U), (x, ly + 9 * U)], fill=sc.ink, width=max(1, int(1.4 * U)))
        S.spaced(d, ((x0 + x1) / 2, ly + 34 * U), S.tr_upper(width), S.font("sans_medium", int(16 * U)), sc.ink, 4 * U)
    eyebrow(d, (W / 2, H * 0.66), "Ölçü & malzeme", sc)
    lab_f, val_f = S.font("sans_light", int(17 * U)), S.font("sans_medium", int(26 * U))  # rakamlar düz (lining)
    rows = specs[:5]
    top = H * 0.71
    for i, (k, v) in enumerate(rows):
        y = top + i * 58 * U
        S.spaced(d, (W * 0.18, y), S.tr_upper(k), lab_f, sc.ink, 4 * U, anchor="left")
        d.text((W * 0.82, y + 4 * U), v, font=val_f, fill=sc.ink, anchor="rs")
        d.line([(W * 0.18, y + 16 * U), (W * 0.82, y + 16 * U)], fill=sc.ink, width=1)
    page_mark(img, sc, 3)
    return S.grain(img, 3.0)


def slide_price(prod, scene, urun, fiyat, cta):
    img, sc = base(scene, logo=False)
    img, _ = paste_product(img, sc, prod, W * 0.46, H * 0.24, W / 2, H * 0.22)
    d = ImageDraw.Draw(img)
    eyebrow(d, (W / 2, H * 0.42), "Toptan fiyatlar", sc)
    rows = []
    found = catalog_prices(urun) if urun else None
    if found:
        rows = [(f"{p}'{suffix(p)} paket" if p > 1 else "Adet", tl(v)) for p, v in found[1]][:6]
    if fiyat:
        rows = [tuple(x.strip() for x in r.split("=", 1)) if "=" in r else (r.strip(), "") for r in fiyat.split(";") if r.strip()]
    lab_f, val_f = S.font("sans_light", int(19 * U)), S.font("sans_medium", int(34 * U))
    top = H * 0.49
    for i, (k, v) in enumerate(rows[:6]):
        y = top + i * 64 * U
        S.spaced(d, (W * 0.2, y), S.tr_upper(k), lab_f, sc.ink, 3 * U, anchor="left")
        d.text((W * 0.8, y + 6 * U), v, font=val_f, fill=sc.ink, anchor="rs")
    if found and not fiyat:
        S.spaced(d, (W / 2, top + len(rows) * 64 * U + 6 * U), S.tr_upper("Fiyatlara KDV dahildir"), S.font("sans_light", int(12 * U)), sc.ink, 3 * U)
    # çağrı + logo
    cy = H * 0.86
    d.text((W / 2, cy), cta, font=S.font("display_italic", int(40 * U)), fill=sc.ink, anchor="ms")
    if S.LOGO.exists():
        src = Image.open(S.LOGO).convert("RGBA")
        lw = int(200 * U)
        a = src.getchannel("A").resize((lw, round(src.height * lw / src.width)), Image.LANCZOS)
        img.paste(Image.new("RGB", a.size, sc.ink), ((W - lw) // 2, int(cy + 34 * U)), a)
    page_mark(img, sc, 4)
    return S.grain(img, 3.0)


def main():
    ap = argparse.ArgumentParser(description="Faravis Atelier carousel şablonu (4 kare)")
    ap.add_argument("image", type=Path)
    ap.add_argument("--scene", default="kum", help="sahne adı ya da auto")
    ap.add_argument("--cekim", default="yan", choices=["yan", "ust"])
    ap.add_argument("--baslik", default="")
    ap.add_argument("--alt", default="")
    ap.add_argument("--detay", default="", help="detay karesinin yazısı")
    ap.add_argument("--olcu", default="", help='"Genişlik: 44 cm; Gövde: 4 cm; Kanca: 9 cm"')
    ap.add_argument("--malzeme", default="")
    ap.add_argument("--urun", default="", help="kdv/katalog.json'da aranacak ürün (paket fiyatları için)")
    ap.add_argument("--fiyat", default="", help='elle fiyat: "12\'li paket=₺1.599; 100\'lü paket=₺11.299"')
    ap.add_argument("--cta", default="Sipariş için DM · faravisatelier.com")
    ap.add_argument("--out", type=Path, default=S.ROOT / "output")
    a = ap.parse_args()

    prod = S.enhance(S.cutout(a.image, a.out / ".cache"))
    scene = a.scene
    if scene == "auto":
        scene = S.suggest(prod, "flat" if a.cekim == "ust" else "stand")[0][1]
        print("sahne:", scene)
    slides = [
        slide_cover(a.image, scene, a.baslik or None, a.alt or None, a.out),
        slide_detail(prod, scene, a.detay),
        slide_specs(prod, scene, a.olcu, a.malzeme),
        slide_price(prod, scene, a.urun, a.fiyat, a.cta),
    ]
    a.out.mkdir(parents=True, exist_ok=True)
    files = []
    for i, im in enumerate(slides, 1):
        f = a.out / f"{a.image.stem}_carousel_{i}.jpg"
        im.save(f, quality=95, subsampling=0, optimize=True)
        files.append(f); print(f)
    strip = Image.new("RGB", (4 * 360 + 5 * 16, 450 + 32), (250, 247, 243))
    for i, f in enumerate(files):
        strip.paste(Image.open(f).resize((360, 450), Image.LANCZOS), (16 + i * 376, 16))
    strip.save(a.out / f"{a.image.stem}_carousel_onizleme.jpg", quality=90)
    print(a.out / f"{a.image.stem}_carousel_onizleme.jpg")


if __name__ == "__main__":
    main()
