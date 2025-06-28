#!/bin/bash

WXPYTHON_EXTRAS_URL="https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/"
export PIP_FIND_LINKS="${WXPYTHON_EXTRAS_URL}"
DEVILDEX_WHEEL="./dist/devildex-0.1.0-py3-none-any.whl"

if [ ! -f "$DEVILDEX_WHEEL" ]; then
    echo "Error: devildex wheel file not found: $DEVILDEX_WHEEL"
    exit 1
fi

echo "Installing devildex, with wxPython preinstalled from URL extras..."
pipx install \
    --preinstall "wxPython" \
    --pip-args="--find-links ${WXPYTHON_EXTRAS_URL}" \
    "$DEVILDEX_WHEEL"

echo "Installation completed."