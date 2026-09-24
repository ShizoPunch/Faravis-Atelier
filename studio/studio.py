#!/usr/bin/env python3
"""Faravis Atelier — Instagram gönderi stüdyosu.

Ürün fotoğrafının arka planını kaldırır, markaya uygun bir sahneye yerleştirir,
gerçekçi gölge ekler ve Instagram ölçülerinde dışa aktarır.

Örnekler:
  python studio/studio.py foto.jpg                          # varsayılan sahne (kum), 4:5
  python studio/studio.py foto.jpg --scene mermer --format square
  python studio/studio.py foto.jpg --scene kemer --title "Yeni Sezon" --subtitle "El yapımı"
  python studio/studio.py foto.jpg --all                    # tüm sahneleri üret + karşılaştırma panosu
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "brand" / "brand.json").read_text())
PAL = BRAND["palette"]

FORMATS = {
    "portrait": (1080, 1350),  # 4:5 — feed için en çok alan kaplayan oran
    "square": (1080, 1080),
    "story": (1080, 1920),  # 9:16 — story / reels kapağı
}


# ---------------------------------------------------------------- yardımcılar
def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def mix(a, b, t):
    return a * (1 - t) + b * t


def font(key: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / BRAND["fonts"][key]), size)


def fractal_noise(w: int, h: int, octaves: int = 5, base: int = 4, seed: int = 7) -> np.ndarray:
    """0..1 arası yumuşak değer gürültüsü (çok oktavlı)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = base * 2**o
        grid = rng.random((cells, max(2, int(cells * w / h)))).astype(np.float32)
        layer = np.asarray(
            Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
            np.float32,
        ) / 255.0
        out += layer * amp
        total += amp
        amp *= 0.5
    return out / total


def grain(img: Image.Image, strength: float = 5.0, seed: int = 3) -> Image.Image:
    """Film greni — dijital düzlüğü kırar, premium his verir."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(img, np.float32)
    n = rng.normal(0, strength, arr.shape[:2])[..., None]
    return Image.fromarray(np.clip(arr + n, 0, 255).astype(np.uint8))


def vignette(w: int, h: int, cx=0.5, cy=0.45, power=1.0) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x / w - cx) * 1.1) ** 2 + ((y / h - cy)) ** 2)
    return np.clip(1 - d * power, 0, 1)


# ---------------------------------------------------------------- sahneler
@dataclass
class Scene:
    bg: Image.Image  # RGB
    floor_y: float  # ürünün tabanının oturacağı yükseklik (0..1)
    max_h: float  # ürünün en fazla kaplayacağı yükseklik oranı
    max_w: float
    shadow: float  # gölge opaklığı
    ink: str  # yazı rengi
    light: Image.Image | None = None  # ürünün üstüne de düşecek ışık/gölge deseni (L, 0..255, 128=nötr)
    fixed_floor: bool = False  # podyumlu sahnelerde zemin yazı için kaydırılmaz
    mode: str = "stand"  # stand: ürün zeminde duruyor (yandan çekim) · flat: üstten çekim (flat-lay)


def studio_sweep(w, h, wall, floor, horizon=0.66, glow=0.10) -> np.ndarray:
    """Sonsuz fon: duvar → yumuşak kıvrım → zemin."""
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    t = np.clip((y - (horizon - 0.08)) / 0.16, 0, 1)
    t = t * t * (3 - 2 * t)
    col = mix(hex_rgb(wall)[None, None], hex_rgb(floor)[None, None], t[..., None])
    col = np.broadcast_to(col, (h, w, 3)).copy()
    v = vignette(w, h, 0.5, 0.42, 0.9)[..., None]
    col = col * (1 - glow) + col * glow * 2 * v  # ortada hafif ışık, kenarlarda düşüş
    return col


def scene_kum(w, h):
    col = studio_sweep(w, h, PAL["ivory"], PAL["sand"], glow=0.14)
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.80, 0.62, 0.78, 0.55, PAL["espresso"])


def scene_pudra(w, h):
    col = studio_sweep(w, h, "#F3E4DD", PAL["blush"], glow=0.12)
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.80, 0.62, 0.78, 0.45, PAL["espresso"])


def scene_adacayi(w, h):
    col = studio_sweep(w, h, "#D5D9C8", PAL["sage"], glow=0.12)
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.80, 0.62, 0.78, 0.5, PAL["charcoal"])


def scene_keten(w, h):
    """Keten dokulu kumaş fon."""
    col = studio_sweep(w, h, "#EDE4D6", "#E2D5C2", glow=0.12)
    rng = np.random.default_rng(11)
    warp = rng.normal(0, 1, (1, w)).astype(np.float32)
    weft = rng.normal(0, 1, (h, 1)).astype(np.float32)
    weave = (np.repeat(warp, h, 0) + np.repeat(weft, w, 1)) * 1.3
    weave = np.asarray(Image.fromarray(np.uint8(np.clip(weave * 20 + 128, 0, 255))).filter(ImageFilter.GaussianBlur(0.7)), np.float32)
    weave = (weave - 128) / 20
    slub = (fractal_noise(w, h, 5, 10, 5) - 0.5) * 10
    col = col + (weave + slub)[..., None]
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.80, 0.62, 0.78, 0.5, PAL["espresso"])


def scene_mermer(w, h):
    """Beyaz mermer zemin + krem duvar."""
    base = studio_sweep(w, h, "#EFEBE5", "#F2F0EC", horizon=0.62, glow=0.1)
    n = fractal_noise(w, h, 6, 3, 21)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    veins = np.abs(np.sin((x * 0.004 + y * 0.0065 + n * 6.0) * math.pi))
    veins = (1 - veins) ** 6  # yumuşak ana damarlar
    veins2 = (1 - np.abs(np.sin((x * 0.0022 - y * 0.003 + n * 4.0) * math.pi))) ** 14
    v = Image.fromarray(np.clip((veins * 0.6 + veins2 * 0.4) * 255, 0, 255).astype(np.uint8))
    v = np.asarray(v.filter(ImageFilter.GaussianBlur(2.2)), np.float32) / 255.0
    marble = hex_rgb("#F4F2EE")[None, None] - (v * 30)[..., None] * np.array([0.95, 0.95, 1.0])
    marble += ((fractal_noise(w, h, 5, 8, 4) - 0.5) * 10)[..., None]
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    t = np.clip((yy - 0.58) / 0.08, 0, 1)
    col = mix(base, marble, t)
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.80, 0.60, 0.78, 0.5, PAL["charcoal"])


def scene_gece(w, h):
    """Koyu, lüks — spot ışıklı espresso fon. Açık renkli ürünlerde çok güçlü."""
    col = studio_sweep(w, h, "#2E2724", "#241E1B", glow=0.0)
    spot = vignette(w, h, 0.5, 0.52, 1.35) ** 1.6
    col = col + (spot * 70)[..., None] * np.array([1.0, 0.86, 0.72])
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.80, 0.62, 0.78, 0.75, PAL["ivory"])


def window_light(w, h, seed=1) -> Image.Image:
    """Pencere + yaprak gölgesi deseni (L, 128=nötr). Güneşli 'golden hour' hissi."""
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    # pencere camları (iki sütun, dört satır) — ışığın düştüğü alanlar
    for c in range(2):
        for r in range(3):
            x0 = int(w * (0.10 + c * 0.30))
            y0 = int(h * (0.02 + r * 0.24))
            d.rectangle([x0, y0, x0 + int(w * 0.26), y0 + int(h * 0.21)], fill=255)
    m = m.transform((w, h), Image.AFFINE, (1, 0.45, -w * 0.12, 0.05, 1, 0), Image.BICUBIC)
    # yaprak siluetleri
    rng = np.random.default_rng(seed)
    leaves = Image.new("L", (w, h), 0)
    ld = ImageDraw.Draw(leaves)
    for _ in range(26):
        cx, cy = rng.uniform(0.45, 1.05) * w, rng.uniform(-0.05, 0.6) * h
        L, W = rng.uniform(0.08, 0.16) * w, rng.uniform(0.025, 0.045) * w
        a = rng.uniform(0, math.pi)
        pts = []
        for t in np.linspace(0, 2 * math.pi, 40):
            px, py = L / 2 * math.cos(t), W / 2 * math.sin(t) * (1 - 0.3 * math.cos(t))
            pts.append((cx + px * math.cos(a) - py * math.sin(a), cy + px * math.sin(a) + py * math.cos(a)))
        ld.polygon(pts, fill=255)
    m = ImageChops.subtract(m, leaves)
    m = m.filter(ImageFilter.GaussianBlur(w * 0.012))
    arr = np.asarray(m, np.float32) / 255.0
    return Image.fromarray((128 + (arr - 0.5) * 70).astype(np.uint8))


def scene_golge(w, h):
    col = studio_sweep(w, h, "#EFE3D3", "#E7D6C1", glow=0.08)
    light = window_light(w, h)
    lf = (np.asarray(light, np.float32) - 128) / 128.0
    col = col * (1 + lf[..., None] * np.array([0.28, 0.25, 0.20]))
    col = col + (lf.clip(0) * 18)[..., None] * np.array([1.0, 0.8, 0.5])  # ılık güneş
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.80, 0.62, 0.78, 0.55, PAL["espresso"], light)


def scene_kemer(w, h):
    """Kemerli niş + silindir podyum — editoryal, modern butik görünümü."""
    col = studio_sweep(w, h, "#EADFD2", "#E1D3C3", horizon=0.72, glow=0.06)
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
    # kemer
    aw, ah = int(w * 0.62), int(h * 0.62)
    ax, ay = (w - aw) // 2, int(h * 0.14)
    arch = Image.new("L", (w, h), 0)
    ad = ImageDraw.Draw(arch)
    ad.ellipse([ax, ay, ax + aw, ay + aw], fill=255)
    ad.rectangle([ax, ay + aw // 2, ax + aw, ay + ah], fill=255)
    arch_col = np.asarray(img, np.float32) * 0 + hex_rgb(PAL["clay"])
    shade = np.linspace(1.05, 0.9, h, dtype=np.float32)[:, None, None]
    arch_img = Image.fromarray(np.clip(arch_col * shade, 0, 255).astype(np.uint8))
    img.paste(arch_img, (0, 0), arch.filter(ImageFilter.GaussianBlur(1)))
    # podyum (silindir)
    pw, ph = int(w * 0.50), int(h * 0.11)
    px = (w - pw) // 2
    ey = int(h * 0.70)  # üst elips merkezi
    eh = int(pw * 0.16)
    body = Image.new("L", (w, h), 0)
    bd = ImageDraw.Draw(body)
    bd.rectangle([px, ey, px + pw, ey + ph], fill=255)
    bd.ellipse([px, ey + ph - eh // 2, px + pw, ey + ph + eh // 2], fill=255)
    xs = np.linspace(-1, 1, pw)
    cyl = np.full((h, w), 0.8, np.float32)
    cyl[:, px : px + pw] = 1.0 - 0.18 * xs**2 - 0.06 * xs  # soldan ışık
    pod = hex_rgb("#F1E9DF")[None, None] * cyl[..., None]
    # podyumun zemine düşen gölgesi
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).ellipse([px - pw * 0.05, ey + ph - eh * 0.2, px + pw * 1.12, ey + ph + eh * 0.9], fill=110)
    img = Image.composite(Image.new("RGB", (w, h), (70, 55, 45)), img, sh.filter(ImageFilter.GaussianBlur(w * 0.02)))
    img.paste(Image.fromarray(np.clip(pod, 0, 255).astype(np.uint8)), (0, 0), body)
    top = Image.new("L", (w, h), 0)
    ImageDraw.Draw(top).ellipse([px, ey - eh // 2, px + pw, ey + eh // 2], fill=255)
    img.paste(Image.new("RGB", (w, h), (248, 243, 236)), (0, 0), top)
    return Scene(img, ey / h + 0.004, 0.44, 0.44, 0.5, PAL["espresso"], fixed_floor=True)


# ---- üstten çekim (flat-lay) sahneleri: ürün yüzeyin üzerinde yatıyor
def flat_light(w, h, base, glow=0.10):
    col = np.broadcast_to(hex_rgb(base)[None, None], (h, w, 3)).astype(np.float32)
    v = vignette(w, h, 0.42, 0.38, 0.8)[..., None]  # sol üstten gelen ışık
    return col * (1 - glow) + col * glow * 2 * v


def scene_traverten(w, h):
    """Açık traverten taş — sıcak, doğal, mimari."""
    col = flat_light(w, h, "#E9DECD", 0.12)
    bands = fractal_noise(w // 8, h, 5, 6, 31)  # yatay katmanlaşma
    bands = np.asarray(Image.fromarray((bands * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    col += ((bands - 0.5) * 26)[..., None] * np.array([1.0, 0.95, 0.85])
    col += ((fractal_noise(w, h, 6, 12, 8) - 0.5) * 10)[..., None]
    # travertene özgü küçük gözenekler
    pits = Image.new("L", (w, h), 0)
    pd = ImageDraw.Draw(pits)
    rng = np.random.default_rng(5)
    for _ in range(int(w * h / 16000)):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        L, T = rng.gamma(1.5, w * 0.0025), rng.uniform(0.5, 1.6)
        pts = [(x + L * math.cos(t) * rng.uniform(0.6, 1.3), y + T * math.sin(t) * rng.uniform(0.5, 1.4))
               for t in np.linspace(0, 2 * math.pi, 9)[:-1]]
        pd.polygon(pts, fill=int(rng.uniform(40, 120)))
    pits = np.asarray(pits.filter(ImageFilter.GaussianBlur(0.9)), np.float32) / 255
    col -= (pits * 34)[..., None] * np.array([0.8, 1.0, 1.2])
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.5, 0.64, 0.84, 0.5, PAL["espresso"], mode="flat")


def scene_serme(w, h):
    """Üstten keten kumaş."""
    col = flat_light(w, h, "#EEE6DA", 0.12)
    rng = np.random.default_rng(12)
    weave = rng.normal(0, 1, (1, w)).astype(np.float32) + rng.normal(0, 1, (h, 1)).astype(np.float32)
    weave = np.asarray(Image.fromarray(np.uint8(np.clip(weave * 26 + 128, 0, 255))).filter(ImageFilter.GaussianBlur(0.7)), np.float32)
    col += ((weave - 128) / 20 * 1.3)[..., None]
    col += ((fractal_noise(w, h, 5, 10, 6) - 0.5) * 12)[..., None]
    # hafif kumaş kırışıklıkları
    folds = fractal_noise(w, h, 3, 2, 17)
    col += (np.sin(folds * 9) * 5)[..., None]
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.5, 0.64, 0.84, 0.45, PAL["espresso"], mode="flat")


def scene_isik(w, h):
    """Üstten çekim + pencere ışığı; gölge ürünün üstüne de düşer."""
    sc = scene_traverten(w, h)
    col = np.asarray(sc.bg, np.float32)
    light = window_light(w, h, seed=4)
    lf = (np.asarray(light, np.float32) - 128) / 128.0
    col = col * (1 + lf[..., None] * np.array([0.26, 0.23, 0.18])) + (lf.clip(0) * 16)[..., None] * np.array([1.0, 0.8, 0.5])
    sc.bg, sc.light = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), light
    return sc


def flat_plaster(w, h, base, ink, shadow, seed):
    """Düz renk, mineral sıva / kağıt dokulu yüzey."""
    col = flat_light(w, h, base, 0.16)
    col += ((fractal_noise(w, h, 6, 6, seed) - 0.5) * 16)[..., None]
    col += ((fractal_noise(w, h, 3, 24, seed + 1) - 0.5) * 6)[..., None]
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.5, 0.64, 0.84, shadow, ink, mode="flat")


def scene_zeytin(w, h):
    """Derin zeytin yeşili — doğal ahşapla tamamlayıcı kontrast."""
    return flat_plaster(w, h, "#5F604A", PAL["ivory"], 0.8, 41)


def scene_kil(w, h):
    """Pişmiş toprak / terrakota — sıcak, Akdeniz."""
    return flat_plaster(w, h, "#B98A6E", PAL["ivory"], 0.7, 43)


def scene_kadife(w, h):
    """Koyu espresso kadife — altın detayları parlatır."""
    col = flat_light(w, h, "#2F2622", 0.0)
    col += (vignette(w, h, 0.45, 0.42, 1.1) ** 1.5 * 38)[..., None] * np.array([1.0, 0.85, 0.72])
    col += ((fractal_noise(w, h, 6, 16, 9) - 0.5) * 9)[..., None]  # kadife havı
    return Scene(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), 0.5, 0.64, 0.84, 0.8, PAL["ivory"], mode="flat")


SCENES = {
    "kum": scene_kum,
    "keten": scene_keten,
    "mermer": scene_mermer,
    "pudra": scene_pudra,
    "adacayi": scene_adacayi,
    "golge": scene_golge,
    "kemer": scene_kemer,
    "gece": scene_gece,
    # üstten çekim (flat-lay) fotoğraflar için
    "traverten": scene_traverten,
    "serme": scene_serme,
    "isik": scene_isik,
    "kadife": scene_kadife,
    "zeytin": scene_zeytin,
    "kil": scene_kil,
}


# ---------------------------------------------------------------- ürün
_session = None


def cutout(path: Path, cache_dir: Path) -> Image.Image:
    """Arka planı kaldırılmış RGBA ürün (önbellekli)."""
    global _session
    cache = cache_dir / f"{path.stem}_cutout.png"
    if cache.exists() and cache.stat().st_mtime > path.stat().st_mtime:
        return Image.open(cache).convert("RGBA")
    from rembg import new_session, remove

    if _session is None:
        _session = new_session("birefnet-general")  # ince tel/mandal detaylarında en iyisi
    src = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    src.thumbnail((2400, 2400), Image.LANCZOS)
    out = remove(src, session=_session, post_process_mask=True)
    # yalnızca ana ürünü tut: arka plandaki küçük parçaları at
    a = keep_main(out.getchannel("A"))
    # kenar hâlesini azalt: alfa'yı çok hafif daralt
    a = a.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    out.putalpha(a)
    bbox = a.point(lambda v: 255 if v > 10 else 0).getbbox()
    out = out.crop(bbox)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out.save(cache)
    return out


def keep_main(a: Image.Image, keep_ratio: float = 0.10) -> Image.Image:
    """En büyük parçayı ve ona yakın büyüklükteki parçaları (ör. çift küpe) korur."""
    from scipy import ndimage

    arr = np.asarray(a)
    lab, n = ndimage.label(arr > 40)
    if n <= 1:
        return a
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.where(sizes >= sizes.max() * keep_ratio)[0])
    keep = ndimage.binary_dilation(keep, iterations=3)
    return Image.fromarray(np.where(keep, arr, 0).astype(np.uint8))


def enhance(prod: Image.Image) -> Image.Image:
    """Hafif rötuş: yalnızca mikro keskinlik. Ürün rengine dokunmuyoruz —
    müşterinin gördüğü renk, eline gelen renk olmalı."""
    rgb, a = prod.convert("RGB"), prod.getchannel("A")
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.4, percent=45, threshold=2))
    rgb.putalpha(a)
    return rgb


def apply_light(prod_rgb: Image.Image, scene: Scene, x: int, y: int, k: float = 0.22) -> Image.Image:
    if scene.light is None:
        return prod_rgb
    pw, ph = prod_rgb.size
    lf = (np.asarray(scene.light.crop((x, y, x + pw, y + ph)), np.float32) - 128) / 128.0
    arr = np.asarray(prod_rgb, np.float32) * (1 + lf[..., None] * k)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def compose_flat(prod: Image.Image, scene: Scene, W: int, H: int, scale: float = 1.0) -> Image.Image:
    """Üstten çekim: ürün yüzeye yatık; gölge sağ-alta, iki katmanlı."""
    canvas = scene.bg.convert("RGB").copy()
    pw, ph = prod.size
    s = min(scene.max_h * H / ph, scene.max_w * W / pw) * scale
    prod = prod.resize((max(1, int(pw * s)), max(1, int(ph * s))), Image.LANCZOS)
    pw, ph = prod.size
    x, y = (W - pw) // 2, int(scene.floor_y * H - ph / 2)
    alpha = prod.getchannel("A")
    u = W / 1080
    shadow = Image.new("L", (W, H), 0)
    for dx, dy, blur, op in ((14, 20, 16, 0.55), (4, 6, 3.5, 0.6)):  # yumuşak + temas
        lay = Image.new("L", (W, H), 0)
        lay.paste(alpha, (x + int(dx * u), y + int(dy * u)))
        lay = lay.filter(ImageFilter.GaussianBlur(blur * u)).point(lambda v, op=op: int(v * op))
        shadow = ImageChops.lighter(shadow, lay)
    shadow = shadow.point(lambda v: int(v * scene.shadow))
    canvas = Image.composite(Image.new("RGB", (W, H), (35, 26, 20)), canvas, shadow)
    canvas.paste(apply_light(prod.convert("RGB"), scene, x, y), (x, y), alpha)
    return canvas


def compose(prod: Image.Image, scene: Scene, W: int, H: int, scale: float = 1.0) -> Image.Image:
    if scene.mode == "flat":
        return compose_flat(prod, scene, W, H, scale)
    canvas = scene.bg.convert("RGB").copy()
    pw, ph = prod.size
    s = min(scene.max_h * H / ph, scene.max_w * W / pw) * scale
    prod = prod.resize((max(1, int(pw * s)), max(1, int(ph * s))), Image.LANCZOS)
    pw, ph = prod.size
    x = (W - pw) // 2
    y = int(scene.floor_y * H) - ph
    alpha = prod.getchannel("A")

    # 1) yumuşak düşen gölge — ürün silüeti zemine yatırılmış
    cast_h = max(1, int(ph * 0.22))
    cast = alpha.resize((pw, cast_h), Image.BICUBIC)
    cast = cast.transform((int(pw * 1.3), cast_h), Image.AFFINE, (1, -0.9, 0, 0, 1, 0), Image.BICUBIC)
    layer = Image.new("L", (W, H), 0)
    layer.paste(cast, (x, y + ph - cast_h), cast)
    layer = layer.filter(ImageFilter.GaussianBlur(max(6, pw * 0.035)))
    # 2) temas gölgesi — ürünün yere değdiği yerde koyu, dar
    contact = Image.new("L", (W, H), 0)
    base_row = np.asarray(alpha)[-max(2, ph // 40) :].max(axis=0) > 60
    cols = np.where(base_row)[0]
    if len(cols):
        cx0, cx1 = x + cols[0], x + cols[-1]
    else:
        cx0, cx1 = x + pw * 0.2, x + pw * 0.8
    eh = max(6, int((cx1 - cx0) * 0.07))
    ImageDraw.Draw(contact).ellipse([cx0 - 4, y + ph - eh // 2, cx1 + 4, y + ph + eh // 2], fill=255)
    contact = contact.filter(ImageFilter.GaussianBlur(max(3, eh * 0.6)))
    shadow = ImageChops.lighter(layer.point(lambda v: v * 0.55), contact.point(lambda v: v * 0.9))
    shadow = shadow.point(lambda v: int(v * scene.shadow))
    dark = Image.new("RGB", (W, H), (40, 30, 25))
    canvas = Image.composite(dark, canvas, shadow)

    # ürün
    canvas.paste(apply_light(prod.convert("RGB"), scene, x, y), (x, y), alpha)  # pencere ışığı ürüne de düşer
    return canvas


# ---------------------------------------------------------------- tipografi
def spaced(draw, xy, text, fnt, fill, tracking, anchor="center"):
    """Harf aralıklı metin (Instagram'da lüks marka dili)."""
    return _spaced(draw, xy, text, fnt, fill, tracking, anchor)


def _spaced(draw, xy, text, fnt, fill, tracking, anchor):
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if anchor == "center":
        x -= total / 2
    for c, cw in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill, anchor="ls")
        x += cw + tracking
    return total


def add_type(img: Image.Image, scene: Scene, title: str | None, subtitle: str | None, logo: bool, W: int, H: int):
    d = ImageDraw.Draw(img)
    ink = scene.ink
    if logo:
        u = W / 1080
        mark = BRAND["wordmark"]
        if mark.get("position", "topleft") == "topleft":
            x0, y0 = 64 * u, 104 * u
            tw = spaced(d, (x0, y0), mark["primary"], font("display_medium", int(38 * u)), ink, 11 * u, anchor="left")
            if mark.get("symbol"):  # tescil işareti, üst simge olarak
                d.text((x0 + tw + 5 * u, y0 - 24 * u), mark["symbol"], font=font("sans_light", int(14 * u)), fill=ink, anchor="ls")
            spaced(d, (x0 + 2 * u, y0 + 30 * u), mark["secondary"], font("sans_light", int(12 * u)), ink, 12.4 * u, anchor="left")
        else:
            tw = spaced(d, (W / 2, 92 * u), mark["primary"], font("display_medium", int(40 * u)), ink, 14 * u)
            if mark.get("symbol"):
                d.text((W / 2 + tw / 2 + 5 * u, 92 * u - 24 * u), mark["symbol"], font=font("sans_light", int(14 * u)), fill=ink, anchor="ls")
            spaced(d, (W / 2, 124 * u), mark["secondary"], font("sans_light", int(13 * u)), ink, 9 * u)
    if title:
        u = W / 1080
        ty = H - 128 * u
        d.text((W / 2, ty), title, font=font("display_italic", int(58 * u)), fill=ink, anchor="ms")
        if subtitle:
            spaced(d, (W / 2, ty + 48 * u), subtitle.upper(), font("sans_light", int(15 * u)), ink, 5 * u)
    elif subtitle:
        u = W / 1080
        spaced(d, (W / 2, H - 70 * u), subtitle.upper(), font("sans_light", int(15 * u)), ink, 5 * u)
    return img


# ---------------------------------------------------------------- çıktı
def render(path: Path, scene_name: str, fmt: str, out_dir: Path, title=None, subtitle=None, logo=True, scale=1.0, rotate=0.0):
    W, H = FORMATS[fmt]
    scene = SCENES[scene_name](W, H)
    if fmt == "story":  # dikey kadrajda ürün nefes alsın
        scene.max_h *= 0.82  # yalnızca yükseklik; geniş ürünler zaten enden sınırlı
    if (title or subtitle) and not scene.fixed_floor:  # yazıya yer aç
        scene.floor_y -= 0.05
        scene.max_h -= 0.06
    prod = enhance(cutout(path, out_dir / ".cache"))
    if rotate:  # eğik çekilmiş ürünü düzelt (derece, + saat yönünün tersi)
        prod = prod.rotate(rotate, Image.BICUBIC, expand=True)
        prod = prod.crop(prod.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox())
    img = compose(prod, scene, W, H, scale)
    img = grain(img, 3.2)
    img = add_type(img, scene, title, subtitle, logo, W, H)
    out = out_dir / f"{path.stem}_{scene_name}_{fmt}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=95, subsampling=0, optimize=True)
    return out


def contact_sheet(files: list[Path], out: Path, cols=4):
    thumbs = [Image.open(f) for f in files]
    tw = 360
    th = int(thumbs[0].height * tw / thumbs[0].width)
    rows = math.ceil(len(thumbs) / cols)
    pad, lab = 16, 34
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad + lab) + pad), (250, 247, 243))
    d = ImageDraw.Draw(sheet)
    for i, (f, t) in enumerate(zip(files, thumbs)):
        r, c = divmod(i, cols)
        x, y = pad + c * (tw + pad), pad + r * (th + pad + lab)
        sheet.paste(t.resize((tw, th), Image.LANCZOS), (x, y))
        name = f.stem.split("_")[-2]
        d.text((x + tw / 2, y + th + 24), name, font=font("sans_medium", 16), fill=PAL["espresso"], anchor="ms")
    sheet.save(out, quality=92)
    return out


def main():
    ap = argparse.ArgumentParser(description="Faravis Atelier Instagram stüdyosu")
    ap.add_argument("images", nargs="+", type=Path)
    ap.add_argument("--scene", default="kum", choices=list(SCENES))
    ap.add_argument("--format", default="portrait", choices=list(FORMATS))
    ap.add_argument("--all", action="store_true", help="tüm sahneleri üret + karşılaştırma panosu")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--no-logo", action="store_true")
    ap.add_argument("--scale", type=float, default=1.0, help="ürün boyutu çarpanı")
    ap.add_argument("--rotate", type=float, default=0.0, help="ürünü döndür (derece)")
    ap.add_argument("--out", type=Path, default=ROOT / "output")
    a = ap.parse_args()

    for p in a.images:
        scenes = list(SCENES) if a.all else [a.scene]
        outs = [render(p, s, a.format, a.out, a.title, a.subtitle, not a.no_logo, a.scale, a.rotate) for s in scenes]
        for o in outs:
            print(o.relative_to(ROOT) if o.is_relative_to(ROOT) else o)
        if a.all:
            print(contact_sheet(outs, a.out / f"{p.stem}_pano.jpg"))


if __name__ == "__main__":
    main()
