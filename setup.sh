#!/bin/bash
cd `dirname $0`

# Create a virtual environment to run our code
VIRTUAL_ENV=$VIAM_MODULE_DATA/.venv
SUDO=sudo

export PATH=$PATH:$HOME/.local/bin

if ! command -v $SUDO; then
  echo "no sudo on this system, proceeding as current user"
  SUDO=""
fi

if command -v apt-get; then
  $SUDO apt-get install python3-pip git python3-pyaudio portaudio19-dev alsa-tools alsa-utils flac python3-dev build-essential -y
else
  echo "Skipping tool installation because your platform is missing apt-get"
  echo "If you see failures below, install the equivalent of python3-venv for your system"
fi

if [ ! "$(command -v uv)" ]; then
  if [ ! "$(command -v curl)" ]; then
    echo "curl is required to install UV. please install curl on this system to continue."
    exit 1
  fi
  echo "Installing uv command"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if ! uv venv --allow-existing $VIRTUAL_ENV; then
  echo "unable to create required virtual environment"
  exit 1
fi

source $VIRTUAL_ENV/bin/activate

echo "Virtualenv found/created. Installing/upgrading Python packages..."
uv pip install -r requirements.txt -q
