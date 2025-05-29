FROM ubuntu:plucky AS builder

ARG PYTHON_VERSION=3.13
ARG POETRY_VERSION=2.1.0

ENV PYTHONDONTWRITEBYTECODE=1

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_HOME="/opt/poetry" \
    PATH="/root/.local/bin:/opt/poetry/bin:${PATH}"

RUN sed -i -E 's|^(URIs:[[:space:]]*)http://|\1https://|g' /etc/apt/sources.list.d/ubuntu.sources

RUN echo 'Acquire::https::Verify-Peer "false";' > /etc/apt/apt.conf.d/99temporarily-unsafe-ssl && \
    echo 'Acquire::https::Verify-Host "false";' >> /etc/apt/apt.conf.d/99temporarily-unsafe-ssl && \
    echo "Updating package lists with SSL verification disabled (unsafe)..." && \
    apt-get update -o Debug::Acquire::https=true && \
    echo "Reinstalling ca-certificates..." && \
    apt-get install -y --reinstall ca-certificates apt-transport-https && \
    update-ca-certificates --fresh && \
    echo "CRITICAL: Removing temporary unsafe SSL setting for APT..." && \
    rm /etc/apt/apt.conf.d/99temporarily-unsafe-ssl


RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    curl \
    git \
    python-is-python3 \
    python3-dev \
    patchelf \
    libglib2.0-0 \
    pkg-config cmake build-essential libcairo2-dev \
    pipx python3-gi python3-gi-cairo gir1.2-gtk-4.0 libgirepository1.0-dev libglib2.0-dev gir1.2-glib-2.0-dev && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}
RUN poetry self add poetry-plugin-export

WORKDIR /app