# Usa ubuntu:25.04 (Plucky) come base per la dipendenza da glibc 2.39 su arm64.
FROM ubuntu:25.04

# Argomenti per configurare le versioni degli strumenti.
# Aggiornato a una versione plausibile di Python 3.13
ARG PYTHON_VERSION=3.13.1
ARG POETRY_VERSION=2.1.0 # Mantengo 2.1.0 come da tua ultima richiesta

# Impostazione delle variabili d'ambiente per pyenv, poetry e Python.
ENV PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
        LC_ALL=C.UTF-8 \
            PYENV_ROOT="/root/.pyenv" \
                POETRY_HOME="/opt/poetry" \
                    PATH="/root/.pyenv/shims:/root/.pyenv/bin:/opt/poetry/bin:${PATH}"

                    # Installazione delle dipendenze di sistema.
                    RUN apt-get update && \
                        apt-get install -y --no-install-recommends \
                            # 1. Dipendenze per pyenv (per il fallback a compilazione)
                                build-essential git curl \
                                    libssl-dev zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev \
                                        libsqlite3-dev libreadline-dev libffi-dev libbz2-dev pkg-config \
                                            \
                                                # 2. Le tue dipendenze di applicazione (ora solo WxWidgets e le sue basi)
                                                    patchelf \
                                                        libglib2.0-0 \
                                                            cmake \
                                                                libcairo2-dev \
                                                                    # Abbiamo rimosso le dipendenze specifiche di GTK4 e GObject Introspection
                                                                        python3-wxgtk4.0 \
                                                                            python3-wxgtk-webview4.0 \
                                                                                \
                                                                                    # 3. SPIEGAZIONE SUI PACCHETTI PYTHON DI SISTEMA (leggi sotto)
                                                                                        # È necessario mantenere 'python3' perché 'python3-wxgtk4.0' ne dipende.
                                                                                            # Se lo togliessimo, apt si rifiuterebbe di installare il pacchetto di wxgtk.
                                                                                                # Non preoccuparti: il nostro PATH fa sì che useremo sempre il Python di pyenv.
                                                                                                    python3 \
                                                                                                        && \
                                                                                                            rm -rf /var/lib/apt/lists/*

                                                                                                            # Installazione di pyenv e della versione di Python richiesta.
                                                                                                            SHELL ["/bin/bash", "-o", "pipefail", "-c"]
                                                                                                            RUN git clone https://github.com/pyenv/pyenv.git "${PYENV_ROOT}" && \
                                                                                                                pyenv install "${PYTHON_VERSION}" && \
                                                                                                                    pyenv global "${PYTHON_VERSION}"

                                                                                                                    # Installazione di Poetry alla versione specificata.
                                                                                                                    RUN curl -sSL https://install.python-poetry.org | python - --version ${POETRY_VERSION} && \
                                                                                                                        poetry self add poetry-plugin-export

                                                                                                                        # Imposta la directory di lavoro finale per la pipeline.
                                                                                                                        WORKDIR /app
                                                                                                                        