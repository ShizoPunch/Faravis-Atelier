"""Videonun üstüne basılan yazılar: kalın, konturlu, emojili, vurgulu kelimeli."""
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).parent / "fonts"
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
SARI = (255, 214, 10)
BEYAZ = (255, 255, 255)
SIYAH = (0, 0, 0)


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


@lru_cache(maxsize=32)
def font(size, weight="Black"):
    return ImageFont.truetype(str(FONTS / f"Montserrat-{weight}.ttf"), size)


@lru_cache(maxsize=1)
def emoji_font():
    try:
        return ImageFont.truetype(EMOJI_FONT, 109)
    except OSError:
        return None


def _is_emoji(ch):
    o = ord(ch)
    return o >= 0x2190 or o in (0x200D, 0xFE0F) or 0x2000 <= o < 0x2070 and o != 0x2026


def _runs(word):
    """Kelimeyi metin ve emoji parçalarına böler."""
    out = []
    for ch in word:
        e = _is_emoji(ch) and ch not in "–—’‘“”"
        if out and out[-1][1] == e:
            out[-1][0] += ch
        else:
            out.append([ch, e])
    return out


@lru_cache(maxsize=512)
def _emoji_img(seq, height):
    ef = emoji_font()
    if ef is None:
        return None
    bb = ef.getbbox(seq)
    im = Image.new("RGBA", (max(bb[2], 1), max(bb[3], 1)))
    ImageDraw.Draw(im).text((0, 0), seq, font=ef, embedded_color=True)
    w = max(1, round(im.width * height / im.height))
    return im.resize((w, height), Image.LANCZOS)


def _word_img(word, f, color, stroke, stroke_color):
    """Tek kelime; taban çizgisi sabit olsun diye yükseklik font metriğinden gelir."""
    asc, desc = f.getmetrics()
    h = asc + desc + 2 * stroke
    pieces = []
    for txt, is_emo in _runs(word):
        if is_emo:
            em = _emoji_img(txt, int(asc * 1.05))
            if em is None:
                continue
            canvas = Image.new("RGBA", (em.width + 2 * stroke, h))
            canvas.alpha_composite(em, (stroke, max(0, stroke + asc - em.height + int(desc * 0.25))))
            pieces.append(canvas)
        else:
            w = int(f.getlength(txt)) + 2 * stroke + 2
            canvas = Image.new("RGBA", (w, h))
            ImageDraw.Draw(canvas).text((stroke, stroke + asc), txt, font=f, fill=color, anchor="ls",
                                        stroke_width=stroke, stroke_fill=stroke_color)
            pieces.append(canvas)
    w = sum(p.width for p in pieces) - 2 * stroke * max(0, len(pieces) - 1)
    out = Image.new("RGBA", (max(w, 1), h))
    x = 0
    for p in pieces:
        out.alpha_composite(p, (x, 0))
        x += p.width - 2 * stroke
    return out


def parse_markup(text, color=BEYAZ, hl=SARI):
    """'Yarışmacı *annesini* aradı' -> [(kelime, renk), ...]; *...* vurgulanır."""
    out, on = [], False
    for tok in re.split(r"(\*)", text):
        if tok == "*":
            on = not on
            continue
        for w in tok.split():
            out.append((w, hl if on else color))
    return out


def render_words(words, size, max_w, weight="Black", stroke=None, stroke_color=SIYAH,
                 shadow=True, line_gap=1.12, align="center", upper=False, scales=None):
    """[(kelime, renk)] listesini satırlara sarıp tek RGBA görüntü yapar.

    scales: kelime başına büyütme (aktif kelimeyi hafif büyütmek için).
    """
    f = font(size, weight)
    stroke = round(size * 0.11) if stroke is None else stroke
    imgs = []
    for i, (w, c) in enumerate(words):
        im = _word_img(tr_upper(w) if upper else w, f, c, stroke, stroke_color)
        s = scales[i] if scales else 1.0
        if s != 1.0:
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        imgs.append(im)
    space = f.getlength(" ") * 0.45
    lines, cur, cur_w = [], [], 0
    for im in imgs:
        add = im.width + (space if cur else 0)
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [], 0
            add = im.width
        cur.append(im)
        cur_w += add
    if cur:
        lines.append(cur)
    lh = int(size * line_gap)
    base_h = max(im.height for im in imgs) if imgs else 1
    widths = [sum(i.width for i in ln) + space * (len(ln) - 1) for ln in lines]
    W = int(max(widths)) + 4 if widths else 1
    H = lh * (len(lines) - 1) + base_h + 4
    out = Image.new("RGBA", (W, H))
    y = 2
    for ln, lw in zip(lines, widths):
        x = 2 + (W - 4 - lw) / 2 if align == "center" else 2
        for im in ln:
            out.alpha_composite(im, (int(x), int(y + (base_h - im.height) / 2)))
            x += im.width + space
        y += lh
    if shadow:
        pad = 24
        sh = Image.new("RGBA", (W + 2 * pad, H + 2 * pad))
        a = out.getchannel("A").point(lambda v: v * 0.55)
        black = Image.new("RGBA", out.size, (0, 0, 0, 255))
        black.putalpha(a)
        sh.alpha_composite(black, (pad, pad + max(3, size // 14)))
        sh = sh.filter(ImageFilter.GaussianBlur(size / 10))
        sh.alpha_composite(out, (pad, pad))
        out = sh
    return out


def render_text(text, size, max_w, **kw):
    hl = kw.pop("hl", SARI)
    color = kw.pop("color", BEYAZ)
    return render_words(parse_markup(text, color, hl), size, max_w, **kw)
