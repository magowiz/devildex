FROM fedora:42

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN dnf update -y && \
    dnf install -y \
    python \
    python-devel \
    python-pip \
    gcc \
    gcc-c++ \
    git \
    curl \
    lftp \
    xorg-x11-server-Xvfb \
    xdg-utils \
    jq \
    SDL2-devel \
    xclip \
    xorg-x11-xauth \
    patchelf \
    glib2-devel \
    && dnf clean all


RUN python -m pip install --no-cache-dir --upgrade pip pipx

RUN pipx install poetry
ENV PATH="/root/.local/bin:${PATH}"

RUN poetry self add poetry-plugin-export