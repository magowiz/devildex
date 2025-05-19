# Usiamo una versione specifica e recente di Fedora.
# Fedora 42 (rilasciata Primavera 2025) è un'ottima scelta. È multi-arch.
FROM fedora:42

ARG PYTHON_VERSION_TARGET=3.13
ARG POETRY_VERSION=1.8.2 # O la versione di Poetry che usi

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Aggiorna il sistema e installa le dipendenze con dnf
# NOTA: Dovrai tradurre i nomi dei pacchetti da apt a dnf.
RUN dnf update -y && \
    dnf install -y \
    # Python 3.13 e i suoi tool (su Fedora 42, python3 dovrebbe essere 3.13)
    python${PYTHON_VERSION_TARGET} \
    python${PYTHON_VERSION_TARGET}-devel \
    python${PYTHON_VERSION_TARGET}-pip \
    python${PYTHON_VERSION_TARGET}-venv \
    # Strumenti di build generici
    gcc \
    gcc-c++ \
    git \
    curl \
    # Esempio di dipendenze che avevi (DA VERIFICARE I NOMI ESATTI PER FEDORA):
    lftp \
    xorg-x11-server-Xvfb \
    xdg-utils \
    jq \
    SDL2-devel \        # per libsdl2-dev
    # Per ffmpeg completo, Fedora usa spesso RPM Fusion (repository esterno).
    # Se ti servono solo le librerie per compilare un wrapper Python:
    # ffmpeg-devel ffmpeg-libs 
    # Per ora, concentriamoci sulle dipendenze più semplici da trovare.
    libmtdev-devel \    # per libmtdev-dev
    xclip \
    xorg-x11-xauth \
    xcb-util-xinerama-devel \ # o libXinerama-devel (per libxcb-xinerama0)
    patchelf \
    glib2-devel \       # per libglib2.0-0
    # mingw-w64 per cross-compilazione Windows
    mingw64-gcc-c++ \   # (o mingw64-gcc, mingw64-cpp, ecc. a seconda di cosa ti serve)
    # pipx
    python3-pipx \      # (o semplicemente 'pipx' se è un pacchetto standalone)
    && dnf clean all

# Aggiorna pip per Python 3.13
RUN python${PYTHON_VERSION_TARGET} -m pip install --no-cache-dir --upgrade pip

# Installa Poetry usando pipx
RUN pipx install poetry==${POETRY_VERSION}
# Assicura che il PATH per gli eseguibili di pipx sia attivo
ENV PATH="/root/.local/bin:${PATH}"

# Se devi aggiungere il plugin a Poetry già nell'immagine Docker:
# Questo comando va eseguito DOPO che PATH è stato aggiornato per includere /root/.local/bin
RUN poetry self add poetry-plugin-export

WORKDIR /app

# Il resto: COPY pyproject.toml poetry.lock* ./ ecc.
# Poi il Jenkinsfile si occuperà di creare il venv specifico per il progetto,
# installare le dipendenze lì, e lanciare Nuitka.