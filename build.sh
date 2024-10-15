#!/usr/bin/env bash
if ! command -v uv 2>&1 >/dev/null; then
    pip install uv
fi
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
.venv/bin/python3 -m PyInstaller --onefile --paths src --hidden-import="googleapiclient" main.py
tar -czvf dist/archive.tar.gz dist/main
