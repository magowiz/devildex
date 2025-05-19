FROM archlinux:base-2025.05.15

ARG PYTHON_VERSION_REQ=3.13
ARG POETRY_VERSION=1.8.2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm \
    base-devel \
    python \
    python-pip \
    python-virtualenv \
    python-pipx \
    git \
    curl \
    lftp \
    xorg-x11-server-xvfb \
    xdg-utils \
    jq \
    sdl2 \
    libmtdev \
    xclip \
    xorg-xauth \
    patchelf \
    glib2 \
    mingw-w64-gcc \
    && rm -rf /var/cache/pacman/pkg/*


RUN python -m pip install --no-cache-dir --upgrade pip


RUN pipx install poetry==${POETRY_VERSION}
ENV PATH="/root/.local/bin:${PATH}"

RUN poetry self add poetry-plugin-export

WORKDIR /app