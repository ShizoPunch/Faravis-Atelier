"""Ses efektlerini sıfırdan sentezler. Hepsi bize ait, telif sorunu yok.

    python tvarsiv/sfx_uret.py        # tvarsiv/sfx/*.wav dosyalarını yeniden üretir
"""
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
OUT = Path(__file__).parent / "sfx"
rng = np.random.default_rng(7)


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def env(n, attack=0.005, release=None, curve=4.0):
    """Hızlı yükselen, üstel sönen zarf."""
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    rel = release or (n / SR)
    return a * np.exp(-curve * t / rel)


def bp(x, lo, hi, order=4):
    return sosfilt(butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)


def lp(x, f, order=4):
    return sosfilt(butter(order, f, "lowpass", fs=SR, output="sos"), x)


def hp(x, f, order=4):
    return sosfilt(butter(order, f, "highpass", fs=SR, output="sos"), x)


def sweep(f0, f1, dur, shape="exp"):
    t = t_(dur)
    if shape == "exp":
        f = f0 * (f1 / f0) ** (t / dur)
    else:
        f = f0 + (f1 - f0) * t / dur
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def norm(x, peak=0.89):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def soft(x, drive=2.0):
    return np.tanh(drive * x) / np.tanh(drive)


# ---------------------------------------------------------------- efektler
def boom():
    """Derin bas vuruşu: şaşkınlık / 'patladı' anı."""
    d = 1.6
    body = sweep(120, 38, d) * env(int(d * SR), 0.002, d, 3.2)
    click = hp(rng.standard_normal(int(0.03 * SR)), 1500) * env(int(0.03 * SR), 0.0005, 0.03, 5)
    sub = np.sin(2 * np.pi * 45 * t_(d)) * env(int(d * SR), 0.01, d, 2.5) * 0.6
    x = body + sub
    x[: len(click)] += click * 0.5
    return soft(norm(x), 2.5)


def whoosh():
    """Geçiş / zoom anı için hava sesi."""
    d = 0.55
    n = int(d * SR)
    noise = rng.standard_normal(n)
    t = t_(d)
    shape = np.sin(np.pi * t / d) ** 2
    lo = lp(noise, 2500) * shape
    hi = bp(noise, 1800, 7000) * shape ** 3 * 0.5
    return norm(lo + hi)


def ding():
    """Doğru cevap / 'bingo' zili."""
    d = 1.4
    t = t_(d)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * k)
            for f, a, k in [(1318.5, 1.0, 3.0), (2637, 0.35, 5.0), (3950, 0.15, 8.0)])
    return norm(x * env(len(t), 0.002, d, 0.1))


def pop():
    """Yazı / emoji belirince küçük 'pıt'."""
    d = 0.12
    x = sweep(900, 250, d) * env(int(d * SR), 0.001, d, 6)
    return norm(x)


def tik():
    d = 0.04
    x = hp(rng.standard_normal(int(d * SR)), 2000) * env(int(d * SR), 0.0003, d, 9)
    return norm(x, 0.7)


def riser():
    """Gerilim yükselen ses (punchline öncesi)."""
    d = 2.0
    t = t_(d)
    tone = sweep(180, 1400, d) * 0.6 + sweep(181.5, 1410, d) * 0.6
    noise = hp(rng.standard_normal(len(t)), 800) * 0.25
    shape = (t / d) ** 2
    return norm((tone + noise) * shape)


def scratch():
    """Plak cızırtısı: 'dur bir dakika' anı."""
    d = 0.42
    t = t_(d)
    # ileri-geri sürtme: frekansı hızla değişen gürültü bantları
    wob = 0.5 + 0.5 * np.sin(2 * np.pi * 7.5 * t)
    noise = rng.standard_normal(len(t))
    x = np.zeros_like(t)
    for c in (600, 1200, 2400):
        x += bp(noise, c * 0.6, c * 1.4, 2) * wob
    tone = np.sin(2 * np.pi * np.cumsum(300 + 900 * wob) / SR) * 0.4
    return soft(norm((x + tone) * env(len(t), 0.003, d, 1.2)), 1.8)


def _brass(f, d):
    t = t_(d)
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 0.8 for k in range(1, 9))
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t)
    x = sum(np.sin(2 * np.pi * f * k * np.cumsum(vib) / SR) / k ** 0.8 for k in range(1, 9))
    a = np.clip(t / 0.03, 0, 1) * np.clip((d - t) / 0.08, 0, 1)
    return lp(x, 3500) * a


def dramatik():
    """Dun dun duuun: dramatik ifşa anı."""
    notes = [(146.8, 0.28), (146.8, 0.28), (138.6, 1.4)]
    gap = int(0.06 * SR)
    parts = []
    for f, d in notes:
        parts.append(_brass(f, d) + _brass(f * 1.5, d) * 0.4)
        parts.append(np.zeros(gap))
    return soft(norm(np.concatenate(parts)), 1.5)


def huzunlu():
    """Üzgün trombon (wah wah wah waaah): başarısızlık anı."""
    parts = []
    for f0, f1, d in [(392, 370, 0.42), (370, 349, 0.42), (349, 330, 0.42), (330, 300, 1.3)]:
        t = t_(d)
        f = np.linspace(f0, f1, len(t))
        if d > 1:  # son nota titreşir
            f = f * (1 + 0.025 * np.sin(2 * np.pi * 6 * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = sum(np.sin(k * ph) / k for k in range(1, 7))
        wah = 0.55 + 0.45 * np.sin(np.pi * np.clip(t / 0.35, 0, 1))
        a = np.clip(t / 0.03, 0, 1) * np.clip((d - t) / 0.06, 0, 1)
        parts.append(lp(x, 1800) * wah * a)
        parts.append(np.zeros(int(0.04 * SR)))
    return norm(np.concatenate(parts))


def glitch():
    d = 0.35
    n = int(d * SR)
    x = np.zeros(n)
    i = 0
    while i < n:
        L = int(rng.uniform(0.008, 0.04) * SR)
        kind = rng.integers(3)
        seg = (rng.standard_normal(L) if kind == 0
               else np.sign(np.sin(2 * np.pi * rng.uniform(80, 900) * np.arange(L) / SR)) * 0.6
               if kind == 1 else np.zeros(L))
        x[i:i + L] = seg[: n - i]
        i += L
    return norm(x * 0.8)


def kamera():
    """Fotoğraf makinesi deklanşörü: donma karesi."""
    d = 0.18
    n = int(d * SR)
    x = np.zeros(n)
    for off, g in [(0, 1.0), (int(0.07 * SR), 0.7)]:
        L = int(0.035 * SR)
        c = bp(rng.standard_normal(L), 1500, 9000) * env(L, 0.0003, 0.035, 6) * g
        x[off:off + L] += c
    return norm(x)


def bip():
    """Sansür bip'i (1 kHz)."""
    d = 0.6
    t = t_(d)
    a = np.clip(t / 0.005, 0, 1) * np.clip((d - t) / 0.005, 0, 1)
    return np.sin(2 * np.pi * 1000 * t) * a * 0.6


def kalp():
    """Kalp atışı: gerilim anı (2 atış)."""
    one = lambda: lp(sweep(70, 40, 0.18), 200) * env(int(0.18 * SR), 0.004, 0.18, 4)
    gap = lambda s: np.zeros(int(s * SR))
    x = np.concatenate([one(), gap(0.08), one() * 0.7, gap(0.45), one(), gap(0.08), one() * 0.7, gap(0.2)])
    return soft(norm(x), 2)


SFX = {
    "boom": boom, "whoosh": whoosh, "ding": ding, "pop": pop, "tik": tik, "riser": riser,
    "scratch": scratch, "dramatik": dramatik, "huzunlu": huzunlu, "glitch": glitch,
    "kamera": kamera, "bip": bip, "kalp": kalp,
}


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in SFX.items():
        x = np.asarray(fn(), dtype=np.float64)
        fade = min(len(x), int(0.004 * SR))
        x[-fade:] *= np.linspace(1, 0, fade)
        wavfile.write(OUT / f"{name}.wav", SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
        print(f"{name:10s} {len(x) / SR:.2f} sn")


if __name__ == "__main__":
    main()
