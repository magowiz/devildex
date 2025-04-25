FROM python:3.13-slim

ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_HOME="/opt/poetry" \
    PATH="$PATH:/opt/poetry/bin"

RUN pip install poetry
WORKDIR /app

COPY . /app

RUN poetry install --no-root --sync

RUN poetry run pip install cx_Freeze nuitka pyoxidizer

RUN apt-get update && \
    apt-get install -y --no-install-recommends mingw-w64 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/lib/mingw-w64/bin:${PATH}"