
FROM ubuntu:25.04


ARG PYTHON_VERSION=3.13.1
ARG POETRY_VERSION=2.1.0


ENV PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYENV_ROOT="/root/.pyenv" \
    POETRY_HOME="/opt/poetry" \
    PATH="/root/.pyenv/shims:/root/.pyenv/bin:/opt/poetry/bin:${PATH}"





RUN apt-get update && \
    apt-get install -y --no-install-recommends --reinstall ca-certificates && \
    rm -rf /var/lib/apt/lists/*




RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    git \
    libcairo2-dev \
    libffi-dev \
    libgdbm-dev \
    libglib2.0-0 \
    libncurses5-dev \
    libnss3-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    libbz2-dev \
    patchelf \
    pkg-config \
    python3 \
    python3-wxgtk4.0 \
    python3-wxgtk-webview4.0 \
    zlib1g-dev \
    && \
    rm -rf /var/lib/apt/lists/*




SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN git clone https://github.com/pyenv/pyenv.git "${PYENV_ROOT}" && \
    pyenv install "${PYTHON_VERSION}" && \
    pyenv global "${PYTHON_VERSION}" && \
    curl -sSL https://install.python-poetry.org | python - --version ${POETRY_VERSION} && \
    poetry self add poetry-plugin-export


WORKDIR /app