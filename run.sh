#!/bin/bash
cd `dirname $0`

SUDO=sudo

if ! command -v $SUDO; then
  echo "no sudo on this system, proceeding as current user"
  SUDO=""
fi

if command -v apt-get; then
  if dpkg -l python3-venv; then
    echo "python3-venv is installed, skipping setup"
  else
    if ! apt info python3-venv; then
      echo "package info not found, trying apt update"
      $SUDO apt-get -qq update
    fi
    $SUDO apt-get install -qqy python3-venv
  fi

  $SUDO apt-get -qq update
  $SUDO apt install -qqy python3-pyaudio portaudio19-dev alsa-tools alsa-utils flac python3-dev
else
  echo "Skipping tool installation because your platform is missing apt-get"
  echo "If you see failures below, install the equivalent of python3-venv for your system"
fi

if [ -f .installed ]
  then
    source viam-env/bin/activate
  else
    python3 -m venv viam-env
    source viam-env/bin/activate
    pip3 install --upgrade -r requirements.txt
    if [ $? -eq 0 ]
      then
        touch .installed
    fi
fi

# Be sure to use `exec` so that termination signals reach the python process,
# or handle forwarding termination signals manually
exec python3 -m src $@
