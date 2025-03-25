#!/usr/bin/env bash
export PATH=$PATH:$HOME/.local/bin

if [ ! "$(command -v uv)" ]; then
  if [ ! "$(command -v curl)" ]; then
    echo "curl is required to install UV. please install curl on this system to continue."
    exit 1
  fi
  echo "Installing uv command"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if command -v apt >/dev/null 2>&1; then
  sudo apt install -qqy python3-pyaudio portaudio19-dev alsa-tools alsa-utils flac python3-dev clang
fi

if command -v brew >/dev/null 2>&1; then
  brew install portaudio
fi

uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
.venv/bin/python3 -m PyInstaller --onefile --paths src --hidden-import="googleapiclient" main.py
tar -czvf dist/archive.tar.gz dist/main meta.json
