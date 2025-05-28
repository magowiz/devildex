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
    pipx && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}
RUN poetry self add poetry-plugin-export

WORKDIR /app