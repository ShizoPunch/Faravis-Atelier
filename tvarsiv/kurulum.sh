#!/usr/bin/env bash
# Ses-yazı modelini (Whisper large-v3-turbo, int8, ~560 MB) ve Silero VAD'ı ~/models'a indirir.
# Modeller GitHub'dan iner (HuggingFace gerekmez). Bir kez yeterli; bulut oturumunda her yeni oturumda bir kez.
set -euo pipefail
pip install -q sherpa-onnx scipy numpy pillow
M="${HOME}/models"
mkdir -p "$M"
REL=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models
if [ ! -f "$M/sherpa-onnx-whisper-turbo/turbo-encoder.int8.onnx" ]; then
  echo "Whisper turbo indiriliyor (~560 MB)..."
  curl -fSL "$REL/sherpa-onnx-whisper-turbo.tar.bz2" | tar xj -C "$M"
fi
[ -f "$M/silero_vad.onnx" ] || curl -fsSL -o "$M/silero_vad.onnx" "$REL/silero_vad.onnx"
echo "Hazır: $M"
