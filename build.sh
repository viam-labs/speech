#!/usr/bin/env bash
if ! command -v uv 2>&1 >/dev/null; then
    pip install uv
fi
apt install -qqy python3-pyaudio portaudio19-dev alsa-tools alsa-utils flac python3-dev clang
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
.venv/bin/python3 -m PyInstaller --onefile --paths src --hidden-import="googleapiclient" main.py
tar -czvf dist/archive.tar.gz dist/main
