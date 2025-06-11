
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

    build-essential git curl \
    libssl-dev zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev \
    libsqlite3-dev libreadline-dev libffi-dev libbz2-dev pkg-config \

    patchelf \
    libglib2.0-0 \
    cmake \
    libcairo2-dev \
    python3-wxgtk4.0 \
    python3-wxgtk-webview4.0 \
    python3 \
    && \
    rm -rf /var/lib/apt/lists/*




SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN git clone https://github.com/pyenv/pyenv.git "${PYENV_ROOT}" && \
    pyenv install "${PYTHON_VERSION}" && \
    pyenv global "${PYTHON_VERSION}"


RUN curl -sSL https://install.python-poetry.org | python - --version ${POETRY_VERSION} && \
    poetry self add poetry-plugin-export


WORKDIR /app