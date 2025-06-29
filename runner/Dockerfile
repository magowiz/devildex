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
    libegl1 \
    python-is-python3 \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages poetry && poetry self add poetry-plugin-export


WORKDIR /app
COPY pyproject.toml /app/
COPY poetry.lock /app/

ENV PIP_DEFAULT_TIMEOUT=1000
RUN poetry export -f requirements.txt --without-hashes > requirements.txt.tmp && \
    mv requirements.txt.tmp requirements.txt && \
    pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY __init__.py /app/
COPY main.py /app/
COPY local_data_parse /app/local_data_parse/
COPY scan_project_env.py /app/

RUN apt-get update && apt-get install -y --no-install-recommends  \
libfontconfig1 \
libgl1 \
libglib2.0 \
libx11-6 \
libxcb-cursor0 \
libxcb-icccm4 \
libxcb-image0 \
libxcb-keysyms1 \
libxcb-render-util0 \
libxcb-shape0 \
libxcb-xinerama0 \
libxkbcommon-x11-0 \
libxkbcommon-x11-0 \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*


ENV PYTHONPATH="/app:${PYTHONPATH}"

CMD  ["python3", "main.py"]
