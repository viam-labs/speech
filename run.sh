#!/bin/sh
cd `dirname $0`

# Create a virtual environment to run our code
# VENV_NAME="venv"
VENV_NAME=$VIAM_MODULE_DATA/.venv
PYTHON="$VENV_NAME/bin/python"

# uncomment for hot reloading
# sh ./setup.sh

# Be sure to use `exec` so that termination signals reach the python process,
# or handle forwarding termination signals manually
echo "Starting module..."
exec $PYTHON -m main $@
