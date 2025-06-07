#!/bin/bash

# URL del repository "extras" di wxPython per una versione di Ubuntu compatibile (es. 24.04)
# Assicurati che questa sia la più adatta per il tuo sistema o per l'ambiente di destinazione.
WXPYTHON_EXTRAS_URL="https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/"
export PIP_FIND_LINKS="${WXPYTHON_EXTRAS_URL}"
# Percorso del tuo file wheel di devildex
DEVILDEX_WHEEL="./dist/devildex-0.1.0-py3-none-any.whl"

# Verifica che il file wheel di devildex esista
if [ ! -f "$DEVILDEX_WHEEL" ]; then
    echo "Errore: File wheel di devildex non trovato: $DEVILDEX_WHEEL"
    exit 1
fi

echo "Installazione di devildex, con wxPython preinstallato dall'URL extras..."
pipx install \
    --preinstall "wxPython" \
    --pip-args="--find-links ${WXPYTHON_EXTRAS_URL}" \
    "$DEVILDEX_WHEEL"

echo "Installazione completata."