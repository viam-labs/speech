#!/bin/sh
cd `dirname $0`
# Be sure to use `exec` so that termination signals reach the python process,
# or handle forwarding termination signals manually
exec python -m src.main $@