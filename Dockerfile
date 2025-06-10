# Usa ubuntu:25.04 (Plucky) come base per la dipendenza da glibc 2.39 su arm64.
FROM ubuntu:25.04

# Argomenti per configurare le versioni degli strumenti.
ARG PYTHON_VERSION=3.13.1
ARG POETRY_VERSION=2.1.0

# Impostazione delle variabili d'ambiente per pyenv, poetry e Python.
ENV PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYENV_ROOT="/root/.pyenv" \
    POETRY_HOME="/opt/poetry" \
    PATH="/root/.pyenv/shims:/root/.pyenv/bin:/opt/poetry/bin:${PATH}"

# --- FASE 1: Tentativo di Ripristino Certificati tramite HTTP ---
# Come da te suggerito, usiamo i repository HTTP di default per reinstallare
# il pacchetto ca-certificates. Se questo passo ha successo, il trust store
# del container sarà aggiornato e pronto per le connessioni HTTPS successive.
RUN apt-get update && \
    apt-get install -y --no-install-recommends --reinstall ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# --- FASE 2: Installazione delle altre dipendenze ---
# Ora che (si spera) i certificati sono a posto, rieseguiamo l'update e installiamo
# tutto il resto. Apt ora dovrebbe poter parlare in HTTPS se necessario.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # 1. Dipendenze per pyenv
    build-essential git curl \
    libssl-dev zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev \
    libsqlite3-dev libreadline-dev libffi-dev libbz2-dev pkg-config \
    # 2. Le tue dipendenze di applicazione (WxWidgets e basi)
    patchelf \
    libglib2.0-0 \
    cmake \
    libcairo2-dev \
    python3-wxgtk4.0 \
    python3-wxgtk-webview4.0 \
    python3 \
    && \
    rm -rf /var/lib/apt/lists/*

# --- FASE 3: Installazione di Python "Vanilla" ---
# Questo comando ora dovrebbe funzionare, perché il git clone HTTPS
# può usare il trust store che abbiamo appena ripristinato.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN git clone https://github.com/pyenv/pyenv.git "${PYENV_ROOT}" && \
    pyenv install "${PYTHON_VERSION}" && \
    pyenv global "${PYTHON_VERSION}"

# --- FASE 4: Installazione di Poetry ---
RUN curl -sSL https://install.python-poetry.org | python - --version ${POETRY_VERSION} && \
    poetry self add poetry-plugin-export

# --- FASE 5: Finalizzazione ---
WORKDIR /app