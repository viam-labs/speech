#!/bin/bash
cd `dirname $0`

VIRTUAL_ENV=$VIAM_MODULE_DATA/.venv

export PATH=$PATH:$HOME/.local/bin

./setup.sh

source $VIRTUAL_ENV/bin/activate

# Use `plughw:` prefixed PCM devices for auto sample rate conversion
export PA_ALSA_PLUGHW=1

# Be sure to use `exec` so that termination signals reach the python process,
# or handle forwarding termination signals manually
echo "Starting module..."
exec uv run python -m main $@
