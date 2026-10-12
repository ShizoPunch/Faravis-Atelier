"""Bir kurgu planını (JSON) dikey Reels videosuna çevirir.

    python tvarsiv/montaj.py tvarsiv/planlar/ornek.json          # -> tvarsiv/cikti/ornek.mp4 + _kapak.jpg
    python tvarsiv/montaj.py plan.json --onizleme                # 540x960, hızlı deneme

Plan alanları için tvarsiv/README.md'ye bakın. Plandaki tüm "t" zamanları KAYNAK videonun
saniyesidir (yazılardaki zamanlarla aynı); kesme ve dondurmalar otomatik hesaba katılır.
"""
import argparse
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent))
from yazi import BEYAZ, SARI, render_text, render_words  # noqa: E402
from yaziya_dok import _spread_words  # noqa: E402

ROOT = Path(__file__).parent
FPS = 30
SR = 48000
W, H = 1080, 1920
# Reels arayüzünün kapattığı alanlar: üstte ~220 px, altta ~400 px, sağda ~130 px
GUVENLI_UST, GUVENLI_ALT = 230, 1920 - 420


# ====================================================================== zaman çizelgesi
@dataclass
class Parca:
    kaynak: Path
    bas: float
    son: float
    e0: float = 0.0  # kurgu (kesilmiş) zaman çizelgesindeki başlangıç

    @property
    def sure(self):
        return self.son - self.bas


class Zaman:
    """kaynak sn -> kurgu sn -> çıkış sn dönüşümleri (dondurmalar çıkışa süre ekler)."""

    def __init__(self, parcalar, dondurmalar):
        self.parcalar = parcalar
        e = 0.0
        for p in parcalar:
            p.e0 = e
            e += p.sure
        self.kurgu_sure = e
        self.donma = sorted(dondurmalar)  # [(kurgu_sn, süre)]
        self.sure = e + sum(d for _, d in self.donma)

    def kaynak2kurgu(self, t, kaynak=None):
        for p in self.parcalar:
            if (kaynak is None or p.kaynak == kaynak) and p.bas - 1e-3 <= t <= p.son + 1e-3:
                return p.e0 + min(max(t, p.bas), p.son) - p.bas
        return None

    def kurgu2cikis(self, e):
        return e + sum(d for ef, d in self.donma if ef < e - 1e-6)

    def kaynak2cikis(self, t, kaynak=None):
        e = self.kaynak2kurgu(t, kaynak)
        return None if e is None else self.kurgu2cikis(e)

    def cikis2kurgu(self, T):
        """Çıkış zamanı -> (kurgu zamanı, donmuş mu, donmanın başlangıcından beri geçen süre)."""
        ek = 0.0
        for ef, d in self.donma:
            if T < ef + ek:
                break
            if T < ef + ek + d:
                return ef, True, T - (ef + ek)
            ek += d
        return T - ek, False, 0.0


# ====================================================================== yardımcılar
def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True).stdout
    j = json.loads(out)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def kurgu_filtresi(parcalar, sw, sh, ses):
    """Parçaları kesip uç uca ekleyen ffmpeg filtre grafiği."""
    ins = []
    for p in parcalar:
        ins += ["-ss", f"{p.bas:.3f}", "-t", f"{p.sure:.3f}", "-i", str(p.kaynak)]
    fg = []
    for i in range(len(parcalar)):
        if ses:
            fg.append(f"[{i}:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"asetpts=PTS-STARTPTS[a{i}]")
        else:
            fg.append(f"[{i}:v]fps={FPS},scale={sw}:{sh}:force_original_aspect_ratio=decrease,"
                      f"pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v{i}]")
    n = len(parcalar)
    k = "a" if ses else "v"
    fg.append("".join(f"[{k}{i}]" for i in range(n)) + f"concat=n={n}:v={0 if ses else 1}:a={1 if ses else 0}[o]")
    return ins, ";".join(fg)


# ====================================================================== plan
def yukle_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    rel = lambda s: (ROOT / s) if not Path(s).is_absolute() else Path(s)
    varsayilan = rel(plan["kaynak"]) if "kaynak" in plan else None
    parcalar = []
    for p in plan.get("parcalar") or [{}]:
        k = rel(p["kaynak"]) if "kaynak" in p else varsayilan
        dur = probe(k)[2]
        parcalar.append(Parca(k, float(p.get("bas", 0)), float(p.get("son", dur))))
    return plan, parcalar


def olay_kaynagi(o, parcalar, rel=lambda s: ROOT / s):
    return rel(o["kaynak"]) if "kaynak" in o else None


def altyazi_gruplari(plan, parcalar, zaman):
    """Yazılardan kelimeleri alır, çıkış zamanına çevirir, 1-3 kelimelik gruplara ayırır."""
    if plan.get("altyazi") is False:
        return []
    duzelt = plan.get("duzelt", {})
    metin = plan.get("metin", {})
    kelimeler = []
    for k in dict.fromkeys(p.kaynak for p in parcalar):
        j = ROOT / "yazilar" / f"{k.stem}.json"
        if not j.exists():
            print(f"  ! {j.name} yok, altyazısız devam (önce yaziya_dok.py çalıştırın)")
            continue
        segs = json.loads(j.read_text(encoding="utf-8"))["segments"]
        for i, s in enumerate(segs):
            words = s["words"]
            if str(i) in metin:
                words = _spread_words(metin[str(i)], s["start"], s["end"]) if metin[str(i)] else []
            for w in words:
                txt = w["w"]
                cekirdek = re.sub(r"^\W+|\W+$", "", txt)
                if cekirdek in duzelt:  # yalnız tam kelime eşleşmesi
                    txt = txt.replace(cekirdek, duzelt[cekirdek], 1)
                if not txt.strip():
                    continue
                mid = (w["start"] + w["end"]) / 2
                if zaman.kaynak2kurgu(mid, k) is None:
                    continue  # kesilen kısımda kalmış
                a = zaman.kaynak2cikis(max(w["start"], mid - 1), k)
                b = zaman.kaynak2cikis(min(w["end"], mid + 1), k)
                a = a if a is not None else zaman.kaynak2cikis(mid, k)
                b = b if b is not None else zaman.kaynak2cikis(mid, k) + 0.15
                kelimeler.append({"w": txt, "a": a, "b": max(b, a + 0.08), "son": w is words[-1]})
    kelimeler.sort(key=lambda w: w["a"])
    maxk = int(plan.get("altyazi_kelime", 3))
    gruplar, cur = [], []
    for w in kelimeler:
        uzun = sum(len(x["w"]) for x in cur) + len(w["w"]) > 18
        if cur and (len(cur) >= maxk or uzun or w["a"] - cur[-1]["b"] > 0.35):
            gruplar.append(cur)
            cur = []
        cur.append(w)
        if w["son"] or w["w"][-1] in ".?!,…":
            gruplar.append(cur)
            cur = []
    if cur:
        gruplar.append(cur)
    out = []
    for i, g in enumerate(gruplar):
        a = g[0]["a"]
        b = g[-1]["b"] + 0.35
        if i + 1 < len(gruplar):
            b = min(b, gruplar[i + 1][0]["a"])
        out.append({"a": a, "b": max(b, g[-1]["b"]), "kelimeler": g})
    return out


# ====================================================================== render
class Render:
    def __init__(self, plan, parcalar, olcek=1.0):
        self.plan, self.parcalar, self.s = plan, parcalar, olcek
        self.W, self.H = round(W * olcek / 2) * 2, round(H * olcek / 2) * 2
        sw, sh, _ = probe(parcalar[0].kaynak)
        f = min(1920 / sw, 1.0) if sw >= sh else min(1920 / sh, 1.0)
        self.sw, self.sh = round(sw * f / 2) * 2, round(sh * f / 2) * 2
        self.duzen = plan.get("duzen", "meme")

        # dondurmaları kurgu zamanına çevir
        self.olaylar = []
        donma = []
        for o in plan.get("olaylar", []):
            o = dict(o)
            k = olay_kaynagi(o, parcalar)
            e = self._kurgu(o["t"], k)
            if e is None:
                print(f"  ! t={o['t']} kesilen kısımda, atlandı: {o}")
                continue
            o["e"] = e
            if o["tip"] == "dondur":
                donma.append((e, float(o.get("sure", 1.0))))
            self.olaylar.append(o)
        self.zaman = Zaman(parcalar, donma)
        for o in self.olaylar:
            o["T"] = self.zaman.kurgu2cikis(o["e"])
        self.gruplar = altyazi_gruplari(plan, parcalar, self.zaman)
        self._kutu()
        self._cache = {}

    def _kurgu(self, t, k):
        z = Zaman(self.parcalar, [])
        return z.kaynak2kurgu(t, k)

    # --- yerleşim
    def _kutu(self):
        s = self.s
        if self.duzen == "kirp":
            self.kutu = (0, 0, self.W, self.H)
        else:
            oran = float(self.plan.get("pencere", self.sw / self.sh))
            bw = self.W
            bh = round(bw / oran / 2) * 2
            # videoyu güvenli alanın biraz üstüne, ortaya yakın koy
            y = round(max(GUVENLI_UST * s + 330 * s, (self.H - bh) / 2 - 60 * s))
            self.kutu = (0, y, bw, y + bh)
        bx0, by0, bx1, by1 = self.kutu
        self.kanca_alt = by0 - 34 * s
        self.altyazi_y = by1 + 40 * s if self.duzen != "kirp" else self.H * 0.64

    # --- kamera hareketi
    def _kamera(self, T, donuk, donma_t):
        k, merkez, olcek = 0.0, (0.5, 0.5), 1.0
        for o in self.olaylar:
            if o["tip"] != "zoom":
                continue
            d = float(o.get("sure", 1.5))
            x = T - o["T"]
            if not (0 <= x <= d):
                continue
            hedef = float(o.get("olcek", 1.3))
            if o.get("gecis", "ani") == "ani":
                kk = 1.0
                hedef *= 1 + 0.05 * math.exp(-x / 0.06)  # vuruşta minik taşma
            else:
                kk = ease(x / 0.3) * ease((d - x) / 0.3)
            if kk >= k:
                k, merkez, olcek = kk, tuple(o.get("merkez", (0.5, 0.45))), hedef
        z = 1 + (olcek - 1) * k
        if donuk:  # donma karesinde yavaş içe kayış
            z *= 1 + 0.06 * ease(donma_t / 1.2)
        dx = dy = 0.0
        for o in self.olaylar:
            if o["tip"] != "sarsinti":
                continue
            x = T - o["T"]
            d = float(o.get("sure", 0.4))
            if 0 <= x <= d:
                g = float(o.get("guc", 22)) * (1 - x / d)
                dx += g * math.sin(x * 83.0)
                dy += g * math.cos(x * 61.0)
        return z, merkez, k, dx, dy

    def _kare(self, src, T, donuk, donma_t):
        bx0, by0, bx1, by1 = self.kutu
        bw, bh = bx1 - bx0, by1 - by0
        oran = bw / bh
        # temel kırpma (pencere oranı)
        if self.sw / self.sh > oran:
            cw, ch = self.sh * oran, self.sh
        else:
            cw, ch = self.sw, self.sw / oran
        cx0 = float(self.plan.get("kirp_x", 0.5)) * self.sw
        cy0 = self.sh / 2
        z, merkez, k, dx, dy = self._kamera(T, donuk, donma_t)
        cx = cx0 + (merkez[0] * self.sw - cx0) * min(k, 1)
        cy = cy0 + (merkez[1] * self.sh - cy0) * min(k, 1)
        w, h = cw / z, ch / z
        piks = cw / bw  # çıkış pikseli başına kaynak pikseli
        cx = min(max(cx + dx * piks, w / 2), self.sw - w / 2)
        cy = min(max(cy + dy * piks, h / 2), self.sh - h / 2)
        return src.resize((bw, bh), Image.BILINEAR, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))

    def _arka(self, src):
        if self.duzen == "bulanik":
            small = src.resize((max(2, self.W // 20), max(2, self.H // 20)), Image.BILINEAR,
                               box=self._fill_box(src.size, self.W / self.H))
            small = small.filter(ImageFilter.GaussianBlur(2.2))
            arr = np.asarray(small, np.float32) * 0.42
            return Image.fromarray(arr.astype(np.uint8)).resize((self.W, self.H), Image.BILINEAR).convert("RGBA")
        renk = tuple(self.plan.get("arka_renk", (12, 12, 14)))
        return Image.new("RGBA", (self.W, self.H), renk + (255,))

    @staticmethod
    def _fill_box(size, oran):
        sw, sh = size
        if sw / sh > oran:
            w = sh * oran
            return ((sw - w) / 2, 0, (sw + w) / 2, sh)
        h = sw / oran
        return (0, (sh - h) / 2, sw, (sh + h) / 2)

    # --- yazılar
    def _img(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def _yapistir(self, canvas, im, cx, y, olcek=1.0, alpha=1.0, anchor="top"):
        if olcek != 1.0:
            im = im.resize((max(1, round(im.width * olcek)), max(1, round(im.height * olcek))), Image.BILINEAR)
        if alpha < 1.0:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
        yy = y if anchor == "top" else y - im.height if anchor == "bottom" else y - im.height / 2
        canvas.alpha_composite(im, (int(cx - im.width / 2), int(yy)))

    def _kanca(self, canvas, T):
        metin = self.plan.get("kanca")
        if not metin:
            return
        sure = self.plan.get("kanca_sure")
        if sure and T > sure:
            return
        s = self.s
        stil = self.plan.get("kanca_stil", "koyu")
        if stil == "beyaz":
            im = self._img(("kanca", stil), lambda: render_text(
                metin, round(64 * s), self.W - 120 * s, color=(0, 0, 0), hl=(214, 40, 40),
                stroke=0, shadow=False, weight="ExtraBold"))
            if self.duzen != "kirp":
                y0 = GUVENLI_UST * s
                y1 = self.kutu[1]
                canvas.paste((255, 255, 255, 255), (0, int(y0 - 40 * s), self.W, int(y1)))
                self._yapistir(canvas, im, self.W / 2, (y0 - 40 * s + y1) / 2, anchor="center")
                return
        im = self._img(("kanca", stil), lambda: render_text(
            metin, round(70 * s), self.W - 110 * s, weight="Black", stroke=round(7 * s)))
        if self.duzen == "kirp":
            self._yapistir(canvas, im, self.W / 2, GUVENLI_UST * s + 20 * s)
        else:
            self._yapistir(canvas, im, self.W / 2, self.kanca_alt, anchor="bottom")

    def _altyazi(self, canvas, T):
        s = self.s
        for gi, g in enumerate(self.gruplar):
            if not (g["a"] <= T < g["b"]):
                continue
            aktif = max([i for i, w in enumerate(g["kelimeler"]) if w["a"] <= T] or [0])
            boyut = round(float(self.plan.get("altyazi_boyut", 80)) * s)

            def make():
                words = [(w["w"], SARI if i == aktif else BEYAZ) for i, w in enumerate(g["kelimeler"])]
                return render_words(words, boyut, self.W - 140 * s, upper=self.plan.get("buyuk_harf", True),
                                    scales=[1.08 if i == aktif else 1 for i in range(len(words))])
            im = self._img(("alt", gi, aktif), make)
            x = T - g["a"]
            pop = 0.86 + 0.14 * ease(x / 0.09)
            self._yapistir(canvas, im, self.W / 2, self.altyazi_y + im.height / 2, olcek=pop, anchor="center")
            return

    def _yazilar(self, canvas, T):
        s = self.s
        bx0, by0, bx1, by1 = self.kutu
        for i, o in enumerate(self.olaylar):
            if o["tip"] not in ("yazi", "emoji"):
                continue
            d = float(o.get("sure", 1.5))
            x = T - o["T"]
            if not (0 <= x <= d):
                continue
            boyut = round(float(o.get("boyut", 96 if o["tip"] == "yazi" else 150)) * s)
            im = self._img(("yazi", i), lambda: render_text(
                o["metin"], boyut, self.W - 120 * s, stroke=round(boyut * 0.1),
                upper=o.get("buyuk_harf", o["tip"] == "yazi")))
            konum = o.get("konum", "orta")
            y = {"ust": by0 + (by1 - by0) * 0.2, "orta": (by0 + by1) / 2, "alt": by1 - (by1 - by0) * 0.18}[konum]
            if self.duzen == "kirp":
                y = {"ust": self.H * 0.3, "orta": self.H * 0.45, "alt": self.H * 0.56}[konum]
            pop = 0.5 + 0.5 * ease(x / 0.12) + 0.08 * math.sin(min(x / 0.12, 1) * math.pi)
            alpha = ease((d - x) / 0.15)
            self._yapistir(canvas, im, self.W / 2, y, olcek=pop, alpha=alpha, anchor="center")

    def _flas(self, canvas, T, donuk, donma_t):
        a = 0.0
        if donuk:
            a = max(a, 0.85 * (1 - donma_t / 0.18)) if donma_t < 0.18 else a
        for o in self.olaylar:
            if o["tip"] == "flas":
                x = T - o["T"]
                if 0 <= x < 0.2:
                    a = max(a, 0.9 * (1 - x / 0.2))
        if a > 0:
            bx0, by0, bx1, by1 = self.kutu
            beyaz = Image.new("RGBA", (bx1 - bx0, by1 - by0), (255, 255, 255, int(255 * a)))
            canvas.alpha_composite(beyaz, (bx0, by0))

    def _imza(self, canvas, T):
        imza = self.plan.get("imza", "@tvarsiv_")
        if not imza:
            return
        s = self.s
        im = self._img("imza", lambda: render_text(imza, round(30 * s), 600, weight="ExtraBold",
                                                    stroke=round(3 * s), shadow=False))
        bx0, by0, bx1, by1 = self.kutu
        if self.duzen == "kirp":
            y = GUVENLI_ALT * s - 60 * s
        else:
            y = by1 - im.height - 14 * s
        self._yapistir(canvas, im, self.W - im.width / 2 - 28 * s, y, alpha=0.72)
        if self.plan.get("ilerleme"):
            p = T / self.zaman.sure
            bar = Image.new("RGBA", (max(1, int(self.W * p)), max(2, int(8 * s))), SARI + (255,))
            canvas.alpha_composite(bar, (0, int(by1 - bar.height if self.duzen != "kirp" else GUVENLI_ALT * s)))

    def kare(self, src, T):
        e, donuk, donma_t = self.zaman.cikis2kurgu(T)
        canvas = self._arka(src)
        bx0, by0, _, _ = self.kutu
        canvas.paste(self._kare(src, T, donuk, donma_t), (bx0, by0))
        self._flas(canvas, T, donuk, donma_t)
        self._imza(canvas, T)
        self._kanca(canvas, T)
        self._altyazi(canvas, T)
        self._yazilar(canvas, T)
        return canvas.convert("RGB")

    # --- ses
    def ses(self, wav_out):
        ins, fg = kurgu_filtresi(self.parcalar, self.sw, self.sh, ses=True)
        raw = subprocess.run(["ffmpeg", "-v", "error", *ins, "-filter_complex", fg, "-map", "[o]",
                              "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                             check=True, capture_output=True).stdout
        kurgu = np.frombuffer(raw, np.float32).reshape(-1, 2) * float(self.plan.get("ses_seviyesi", 1.0))
        n = int(math.ceil(self.zaman.sure * SR))
        out = np.zeros((n, 2), np.float32)
        # kurgu sesini dondurmalarla aralıklı yerleştir
        e_prev, T = 0.0, 0.0
        for ef, d in self.zaman.donma + [(self.zaman.kurgu_sure, 0.0)]:
            a, b = int(e_prev * SR), int(ef * SR)
            seg = kurgu[a:b]
            o = int(T * SR)
            m = min(len(seg), n - o)
            out[o:o + m] += seg[:m]
            T += (ef - e_prev) + d
            e_prev = ef
        # sansür bip'leri: orijinal sesi sustur, yerine 1 kHz
        for o in self.olaylar:
            if o["tip"] == "bip":
                a, b = int(o["T"] * SR), int((o["T"] + float(o.get("sure", 0.5))) * SR)
                b = min(b, n)
                out[a:b] = 0
                t = np.arange(b - a) / SR
                ton = 0.35 * np.sin(2 * np.pi * 1000 * t)
                r = min(240, len(ton) // 2)
                if r:
                    ton[:r] *= np.linspace(0, 1, r)
                    ton[-r:] *= np.linspace(1, 0, r)
                out[a:b] += ton[:, None]
        # efektler
        for o in self.olaylar:
            if o["tip"] != "ses":
                continue
            if "dosya" in o:  # kendi sesiniz / seslendirme (her formatta)
                raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ROOT / o["dosya"]), "-f", "f32le",
                                      "-ac", "2", "-ar", str(SR), "-"], check=True, capture_output=True).stdout
                x = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
            else:
                sr, x = wavfile.read(ROOT / "sfx" / f"{o['ad']}.wav")
                x = (x.astype(np.float32) / 32768.0)
                if x.ndim == 1:
                    x = np.repeat(x[:, None], 2, 1)
            x *= float(o.get("seviye", 0.7))
            a = int((o["T"] + float(o.get("kaydir", 0))) * SR)
            if a < 0:
                x, a = x[-a:], 0
            m = min(len(x), n - a)
            if m > 0:
                if o.get("kis", True):  # efekt boyunca orijinali hafif kıs
                    out[a:a + m] *= float(o.get("kis_oran", 0.25 if "dosya" in o else 0.6))
                out[a:a + m] += x[:m]
        peak = np.max(np.abs(out)) or 1.0
        if peak > 0.98:
            out *= 0.98 / peak
        wavfile.write(wav_out, SR, out)


def render(plan_path, onizleme=False):
    plan, parcalar = yukle_plan(plan_path)
    r = Render(plan, parcalar, olcek=0.5 if onizleme else 1.0)
    cikti = ROOT / "cikti"
    cikti.mkdir(exist_ok=True)
    ad = Path(plan_path).stem + ("_onizleme" if onizleme else "")
    mp4, wav = cikti / f"{ad}.mp4", cikti / f"{ad}.tmp.wav"
    print(f"{ad}: {r.zaman.sure:.1f} sn, {len(r.gruplar)} altyazı grubu, {len(r.olaylar)} olay, düzen={r.duzen}")
    r.ses(wav)

    ins, fg = kurgu_filtresi(parcalar, r.sw, r.sh, ses=False)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", *ins, "-filter_complex", fg, "-map", "[o]",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{r.W}x{r.H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
                            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR),
                            "-c:v", "libx264", "-preset", "veryfast" if onizleme else "medium",
                            "-crf", "28" if onizleme else "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
                            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(mp4)],
                           stdin=subprocess.PIPE)
    fsize = r.sw * r.sh * 3
    idx, src = -1, None
    toplam = int(round(r.zaman.sure * FPS))
    kapak_t = float(plan.get("kapak_t", 0.0))
    kapak_T = r.zaman.kaynak2cikis(kapak_t, None) if "kapak_t" in plan else None
    kapak = None
    for i in range(toplam):
        T = i / FPS
        e, _, _ = r.zaman.cikis2kurgu(T)
        hedef = min(int(e * FPS + 1e-6), int(r.zaman.kurgu_sure * FPS) - 1)
        while idx < hedef:
            buf = dec.stdout.read(fsize)
            if len(buf) < fsize:
                break
            src, idx = Image.frombuffer("RGB", (r.sw, r.sh), buf), idx + 1
        frame = r.kare(src, T)
        if kapak is None and (kapak_T is None and i == int(1.0 * FPS) or kapak_T is not None and T >= kapak_T):
            kapak = frame
        enc.stdin.write(frame.tobytes())
        if i % (FPS * 5) == 0:
            print(f"  {T:5.1f}/{r.zaman.sure:.1f} sn", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()
    wav.unlink()
    if kapak is not None and not onizleme:
        kapak.save(cikti / f"{ad}_kapak.jpg", quality=92)
    print(f"  -> {mp4}")
    return mp4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planlar", nargs="+")
    ap.add_argument("--onizleme", action="store_true")
    a = ap.parse_args()
    for p in a.planlar:
        render(p, a.onizleme)


if __name__ == "__main__":
    main()
