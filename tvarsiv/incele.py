"""Gelen videoları kurgu öncesi inceler: yazıya döker + zaman damgalı kare panosu çıkarır.

    python tvarsiv/incele.py                      # gelen/ içindeki tüm yeni videolar
    python tvarsiv/incele.py gelen/klip.mp4 --aralik 1.5

Çıktı: yazilar/<ad>.json, .srt ve <ad>_kareler.jpg (her N saniyeden bir kare, üstünde saniye yazılı).
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
VIDEO = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}


def kareler(video, aralik, out):
    vf = (f"fps=1/{aralik},scale=480:-2,"
          "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
          f"text='%{{eif\\:n*{aralik}\\:d}} sn':x=8:y=8:fontsize=26:fontcolor=yellow:box=1:boxcolor=black@0.6,"
          "tile=5x200:padding=4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", vf, "-frames:v", "1",
                    "-q:v", "4", str(out)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videolar", nargs="*")
    ap.add_argument("--aralik", type=float, default=2.0)
    a = ap.parse_args()
    vids = [Path(v) for v in a.videolar] or sorted(p for p in (ROOT / "gelen").iterdir() if p.suffix.lower() in VIDEO)
    (ROOT / "yazilar").mkdir(exist_ok=True)
    yeni = [v for v in vids if a.videolar or not (ROOT / "yazilar" / f"{v.stem}.json").exists()]
    if yeni:
        subprocess.run([sys.executable, str(ROOT / "yaziya_dok.py"), *map(str, yeni)], check=True)
    for v in vids:
        out = ROOT / "yazilar" / f"{v.stem}_kareler.jpg"
        if a.videolar or not out.exists():
            kareler(v, a.aralik, out)
            print(f"  -> {out}")


if __name__ == "__main__":
    main()
