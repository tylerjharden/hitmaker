#!/usr/bin/env bash
# hitmaker setup: creates a Python 3.11 venv with the audio/ML stack (CPU only).
# usage: bash scripts/setup.sh [venv_path]      (default: ~/.hitmaker-venv)
set -euo pipefail
VENV="${1:-$HOME/.hitmaker-venv}"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
if command -v uv >/dev/null; then
  uv venv --python 3.11 "$VENV"
  PIP="uv pip install --python $VENV/bin/python"
else
  python3.11 -m venv "$VENV" 2>/dev/null || python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install -q --upgrade pip
  PIP="$VENV/bin/python -m pip install -q"
fi
$PIP --index-url https://download.pytorch.org/whl/cpu torch torchaudio
$PIP demucs "basic-pitch[onnx]" librosa pretty_midi soundfile scipy numba faster-whisper yt-dlp "setuptools<81"
# basic-pitch must use ONNX: a stray tensorflow breaks it
"$VENV/bin/python" -m pip uninstall -y tensorflow tensorflow-cpu >/dev/null 2>&1 || true
"$VENV/bin/python" - <<'EOF'
import demucs, librosa, pretty_midi, faster_whisper, yt_dlp
from basic_pitch import ICASSP_2022_MODEL_PATH
print("hitmaker env OK")
EOF
echo "PY=$VENV/bin/python"
