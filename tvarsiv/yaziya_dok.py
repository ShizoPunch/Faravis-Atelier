"""Videodaki konuşmayı kelime zamanlı yazıya döker (Whisper turbo, yerel, internetsiz).

    python tvarsiv/yaziya_dok.py tvarsiv/gelen/klip.mp4          # -> tvarsiv/yazilar/klip.json + .srt

Videonun yanında YouTube altyazısı varsa (klip.tr.vtt) model yerine o kullanılır:
    yt-dlp --write-auto-subs --sub-langs tr ... ile birlikte iner.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
MODELS = Path.home() / "models"
SR = 16000


def load_audio(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


# ------------------------------------------------------------------ Whisper
def _recognizer():
    import sherpa_onnx
    d = MODELS / "sherpa-onnx-whisper-turbo"
    if not d.exists() or not (MODELS / "silero_vad.onnx").exists():
        print("Model yok, indiriliyor...")
        subprocess.run(["bash", str(ROOT / "kurulum.sh")], check=True)
    return sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(d / "turbo-encoder.int8.onnx"), decoder=str(d / "turbo-decoder.int8.onnx"),
        tokens=str(d / "turbo-tokens.txt"), language="tr", task="transcribe", num_threads=4)


def _vad_chunks(audio, max_len=9.0):
    """Konuşma parçalarını sessizliklere göre böler (Silero VAD)."""
    import sherpa_onnx
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(MODELS / "silero_vad.onnx")
    cfg.silero_vad.min_silence_duration = 0.25
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = max_len
    cfg.silero_vad.threshold = 0.45
    cfg.sample_rate = SR
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=600)
    win = cfg.silero_vad.window_size
    chunks = []
    for i in range(0, len(audio), win):
        vad.accept_waveform(audio[i:i + win])
        while not vad.empty():
            chunks.append((vad.front.start, np.array(vad.front.samples)))
            vad.pop()
    vad.flush()
    while not vad.empty():
        chunks.append((vad.front.start, np.array(vad.front.samples)))
        vad.pop()
    return chunks


def _spread_words(text, start, end):
    """Parça içindeki kelimelere süreyi hece uzunluğuna göre paylaştırır."""
    words = text.split()
    if not words:
        return []
    weights = np.array([len(re.sub(r"\W", "", w)) + 2 for w in words], float)
    edges = start + (end - start) * np.concatenate([[0], np.cumsum(weights) / weights.sum()])
    return [{"w": w, "start": round(edges[i], 3), "end": round(edges[i + 1], 3)} for i, w in enumerate(words)]


def transcribe_whisper(path):
    audio = load_audio(path)
    rec = _recognizer()
    segments = []
    for start_i, samples in _vad_chunks(audio):
        st = rec.create_stream()
        st.accept_waveform(SR, samples)
        rec.decode_stream(st)
        text = st.result.text.strip()
        if not text or _is_hallucination(text):
            continue
        s, e = start_i / SR, (start_i + len(samples)) / SR
        segments.append({"start": round(s, 3), "end": round(e, 3), "text": text,
                         "words": _spread_words(text, s, e)})
        print(f"  [{s:6.2f}-{e:6.2f}] {text}")
    return segments


def _is_hallucination(text):
    t = text.lower()
    return any(k in t for k in ("altyazı m.k", "abone ol", "izlediğiniz için teşekkür")) and len(t) < 60


# ------------------------------------------------------------------ YouTube VTT
def _ts(s):
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def transcribe_vtt(vtt):
    """YouTube otomatik altyazısını (kelime zamanlı) okur."""
    words = []
    cue = re.compile(r"(\d+:\d+:\d+\.\d+) --> (\d+:\d+:\d+\.\d+)")
    lines = Path(vtt).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = cue.match(line)
        if not m:
            continue
        body = lines[i + 1] if i + 1 < len(lines) else ""
        if "<c>" not in body and not re.search(r"<\d", body):
            continue  # YouTube her satırı iki kez yazar; yalnız zamanlı olanı al
        start, end = _ts(m.group(1)), _ts(m.group(2))
        parts = re.split(r"<(\d+:\d+:\d+\.\d+)>", body)
        t = start
        for j, p in enumerate(parts):
            if j % 2 == 1:
                t = _ts(p)
                continue
            w = re.sub(r"</?c[^>]*>", "", p).strip()
            if w:
                words.append({"w": w, "start": t, "end": end})
    for a, b in zip(words, words[1:]):
        a["end"] = min(a["end"], b["start"])
    # kelimeleri cümle benzeri parçalara topla (0.6 sn sessizlik = yeni parça)
    segments, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > 0.6 or len(cur) >= 14):
            segments.append(cur)
            cur = []
        cur.append(w)
    if cur:
        segments.append(cur)
    return [{"start": s[0]["start"], "end": s[-1]["end"], "text": " ".join(w["w"] for w in s), "words": s}
            for s in segments]


def to_srt(segments):
    def f(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{f(s['start'])} --> {f(s['end'])}\n{s['text']}\n" for i, s in enumerate(segments, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--whisper", action="store_true", help="VTT olsa bile Whisper kullan")
    a = ap.parse_args()
    out = ROOT / "yazilar"
    out.mkdir(exist_ok=True)
    for v in map(Path, a.videos):
        vtts = sorted(v.parent.glob(v.stem + "*.vtt"))
        print(f"{v.name}: " + (f"YouTube altyazısı ({vtts[0].name})" if vtts and not a.whisper else "Whisper"))
        segs = transcribe_vtt(vtts[0]) if vtts and not a.whisper else transcribe_whisper(v)
        (out / f"{v.stem}.json").write_text(json.dumps({"video": v.name, "segments": segs},
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
        (out / f"{v.stem}.srt").write_text(to_srt(segs), encoding="utf-8")
        print(f"  -> {out / v.stem}.json ({len(segs)} parça)")


if __name__ == "__main__":
    main()
