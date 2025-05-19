FROM fedora:42

ARG PYTHON_VERSION_TARGET=3.13

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN dnf update -y && \
    dnf install -y \
    python${PYTHON_VERSION_TARGET} \
    python${PYTHON_VERSION_TARGET}-devel \
    python${PYTHON_VERSION_TARGET}-pip \
    python${PYTHON_VERSION_TARGET}-venv \
    gcc \
    gcc-c++ \
    git \
    curl \
    lftp \
    xorg-x11-server-Xvfb \
    xdg-utils \
    jq \
    SDL2-devel \
    libmtdev-devel \
    xclip \
    xorg-x11-xauth \
    xcb-util-xinerama-devel \
    patchelf \
    glib2-devel \
    mingw64-gcc-c++ \
    python3-pipx \
    && dnf clean all


RUN python -m pip install --no-cache-dir --upgrade pip

RUN pipx install poetry

ENV PATH="/root/.local/bin:${PATH}"

RUN poetry self add poetry-plugin-export
