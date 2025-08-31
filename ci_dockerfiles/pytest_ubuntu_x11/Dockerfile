FROM ubuntu:24.04

HEALTHCHECK CMD exit 0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Define virtual environment path early
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \

    libnotify-dev \
    libgtk-3-dev \
    libsdl2-dev \
    libwebkit2gtk-4.1-dev \
    libxtst-dev \
    xvfb \
    bzr \
    git \
    python3-gi \
    python3-gi-cairo \
    python3-wxgtk4.0 \
    python3-wxgtk-webview4.0 && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry and Export Plugin
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip pipx && \

    pipx install poetry && \
    /root/.local/bin/poetry self add poetry-plugin-export && \
    rm -rf /var/lib/apt/lists/*

# Create appuser
RUN useradd -ms /bin/bash appuser
RUN mkdir -p ${VIRTUAL_ENV} && chown -R appuser:appuser ${VIRTUAL_ENV}
USER appuser

# Set up PATH for poetry
ENV PATH="/root/.local/bin:${PATH}"

# Create a virtual environment and install dependencies into it
RUN python3 -m venv ${VIRTUAL_ENV} && \
    ${VIRTUAL_ENV}/bin/pip install --upgrade pip

