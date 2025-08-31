FROM ubuntu:24.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    libnotify-dev \
    libgtk-3-dev \
    libsdl2-dev \
    libwebkit2gtk-4.1-dev \
    libxtst-dev \
    xvfb \
    bzr \
    python3-gi \
    python3-gi-cairo \
    python3-wxgtk4.0 \
    python3-wxgtk-webview4.0 && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry and Export Plugin
RUN apt-get update && \
    apt-get install -y python3-pip pipx && \
    pipx install poetry && \
    poetry self add poetry-plugin-export && \
    rm -rf /var/lib/apt/lists/*

# Set up PATH for poetry
ENV PATH="/root/.local/bin:/usr/local/bin:${PATH}"
