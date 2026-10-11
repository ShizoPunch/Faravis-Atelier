#!/usr/bin/env python3
"""Faravis Atelier — Instagram profil ızgarası önizlemesi ve ton dengesi.

Gönderileri profilde göründükleri gibi 3 sütunlu ızgaraya dizer (Instagram profil ızgarası
gönderileri 3:4 oranında kırpar) ve ton dengesini ölçer: açık / orta / koyu dağılımı,
yan yana gelen benzer tonlar, sıcak-soğuk dengesi.

İlk verilen görsel en yeni gönderidir (profilde sol üst).

  python studio/feed.py output/*_portrait.jpg
  python studio/feed.py output/*.jpg --sirala          # ton dengesi en iyi sırayı önerir
  python studio/feed.py yeni.jpg eski/*.jpg --out output/feed.jpg
"""
from __future__ import annotations

import argparse
import itertools
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

import studio as S

PAL = S.PAL
GW = 1080  # önizleme genişliği (telefon ekranı)
GAP = 3


def tile(path: Path, w: int) -> Image.Image:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return ImageOps.fit(im, (w, int(w * 4 / 3)), Image.LANCZOS, centering=(0.5, 0.45))


def tone(im: Image.Image) -> tuple[float, float]:
    """Ortalama açıklık (L 0-100) ve sıcaklık (b*: + sıcak / − soğuk)."""
    lab = S.to_lab(np.asarray(im.resize((64, 85)), np.float32).reshape(-1, 3))
    return float(lab[:, 0].mean()), float(lab[:, 2].mean())


def band(L: float) -> str:
    return "açık" if L >= 68 else "koyu" if L < 42 else "orta"


def neighbours(n: int, cols: int = 3):
    for i in range(n):
        if (i + 1) % cols and i + 1 < n:
            yield i, i + 1
        if i + cols < n:
            yield i, i + cols


def balance(Ls: list[float]) -> float:
    """0-100: komşu gönderiler arasındaki açıklık farkı ve açık/koyu dağılımı."""
    if len(Ls) < 2:
        return 100.0
    pairs = list(neighbours(len(Ls)))
    contrast = np.mean([min(abs(Ls[a] - Ls[b]), 30) / 30 for a, b in pairs])
    counts = [sum(band(L) == k for L in Ls) for k in ("açık", "orta", "koyu")]
    spread = 1 - (max(counts) - min(counts)) / len(Ls)
    return float(100 * (0.7 * contrast + 0.3 * spread))


def best_order(Ls: list[float], tries: int = 4000) -> list[int]:
    """Ton dengesini en yükseğe çıkaran sıra (9 gönderiye kadar tam arama yerine rastgele iyileştirme)."""
    n = len(Ls)
    if n <= 7:
        return list(max(itertools.permutations(range(n)), key=lambda o: balance([Ls[i] for i in o])))
    rng = random.Random(7)
    order = list(range(n)); score = balance(Ls)
    for _ in range(tries):
        a, b = rng.sample(range(n), 2)
        order[a], order[b] = order[b], order[a]
        s = balance([Ls[i] for i in order])
        if s >= score:
            score = s
        else:
            order[a], order[b] = order[b], order[a]
    return order


def render(files: list[Path], out: Path, title: str = "Profil önizlemesi") -> Path:
    tw = (GW - 2 * GAP) // 3
    tiles = [tile(f, tw) for f in files]
    tones = [tone(t) for t in tiles]
    Ls = [t[0] for t in tones]
    rows = (len(tiles) + 2) // 3
    th = tiles[0].height
    head, panel = 250, 300
    img = Image.new("RGB", (GW, head + rows * (th + GAP) + panel), (255, 255, 255))
    d = ImageDraw.Draw(img)
    # profil başlığı (sayılar yok: yalnızca görünüm)
    r = 66
    d.ellipse([40, 40, 40 + 2 * r, 40 + 2 * r], fill=tuple(int(v) for v in S.hex_rgb(PAL["ivory"])), outline=(220, 214, 206), width=2)
    if S.LOGO.exists():
        src = Image.open(S.LOGO).convert("RGBA")
        lw = int(r * 1.5)
        a = src.getchannel("A").resize((lw, round(src.height * lw / src.width)), Image.LANCZOS)
        img.paste(Image.new("RGB", a.size, PAL["espresso"]), (40 + r - lw // 2, 40 + r - a.height // 2), a)
    d.text((200, 70), "faravisatelier", font=S.font("sans_medium", 30), fill=(20, 20, 20))
    d.text((200, 112), "Faravis Atelier · Ahşap askı üreticisi", font=S.font("sans_light", 22), fill=(60, 60, 60))
    d.text((200, 146), "faravisatelier.com", font=S.font("sans_light", 22), fill=(0, 55, 107))
    d.line([(0, head - 2), (GW, head - 2)], fill=(219, 219, 219), width=1)
    # ızgara
    for i, t in enumerate(tiles):
        rr, c = divmod(i, 3)
        img.paste(t, (c * (tw + GAP), head + rr * (th + GAP)))
    # ton paneli
    y0 = head + rows * (th + GAP) + 24
    d.rectangle([0, y0 - 24, GW, img.height], fill=(250, 247, 243))
    d.text((40, y0 + 8), "Ton dengesi", font=S.font("sans_medium", 30), fill=S.PAL["espresso"])
    sc = balance(Ls)
    d.text((GW - 40, y0 + 8), f"{sc:.0f} / 100", font=S.font("sans_medium", 30), fill=S.PAL["espresso"], anchor="ra")
    cell = 46
    for i, (L, b) in enumerate(tones):
        rr, c = divmod(i, 3)
        x, y = 40 + c * (cell + 6), y0 + 70 + rr * (cell + 6)
        g = int(L * 2.55)
        d.rectangle([x, y, x + cell, y + cell], fill=(g, g, g))
        d.text((x + cell / 2, y + cell / 2), f"{L:.0f}", font=S.font("sans_medium", 15), fill=(255, 255, 255) if L < 55 else (30, 30, 30), anchor="mm")
    counts = {k: sum(band(L) == k for L in Ls) for k in ("açık", "orta", "koyu")}
    warm = sum(b > 6 for _, b in tones)
    same = [(a, b) for a, b in neighbours(len(Ls)) if abs(Ls[a] - Ls[b]) < 8]
    notes = [f"Açık {counts['açık']} · orta {counts['orta']} · koyu {counts['koyu']}",
             f"Sıcak tonlu {warm} / {len(Ls)} gönderi" + (" — soğuk bir gönderi (lacivert, beton) dengeyi açar" if warm == len(Ls) and len(Ls) > 3 else "")]
    if same:
        notes.append(f"Yan yana çok benzer tonda {len(same)} çift: " + ", ".join(f"{a + 1}-{b + 1}" for a, b in same[:4]))
    else:
        notes.append("Yan yana gelen gönderilerin tonları ayrışıyor")
    if max(counts.values()) > len(Ls) * 0.6:
        notes.append("Tek bir tonda yoğunlaşma var; arada " + ("koyu" if counts["açık"] >= counts["koyu"] else "açık") + " sahne kullanın")
    for i, t in enumerate(notes):
        d.text((260, y0 + 72 + i * 40), t, font=S.font("sans_light", 22), fill=S.PAL["espresso"])
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out


def main():
    ap = argparse.ArgumentParser(description="Instagram profil ızgarası önizlemesi + ton dengesi")
    ap.add_argument("images", nargs="+", type=Path, help="en yeni gönderi ilk sırada")
    ap.add_argument("--sirala", action="store_true", help="ton dengesini en iyi yapan sırayı öner")
    ap.add_argument("--out", type=Path, default=S.ROOT / "output" / "feed.jpg")
    a = ap.parse_args()
    files = a.images[:12]
    print(render(files, a.out))
    if a.sirala:
        Ls = [tone(tile(f, 120))[0] for f in files]
        order = best_order(Ls)
        better = [files[i] for i in order]
        print(f"Önerilen sıra (ton dengesi {balance(Ls):.0f} → {balance([Ls[i] for i in order]):.0f}):")
        for i, f in enumerate(better, 1):
            print(f"  {i}. {f.name}")
        print(render(better, a.out.with_name(a.out.stem + "_onerilen" + a.out.suffix)))


if __name__ == "__main__":
    main()
