FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1


RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    python3.12-dev \
    git \
    curl \
    lftp \
    xvfb \
    xdg-utils \
    jq \
    gcc \
    libsdl2-dev \
    ffmpeg \
    libavcodec-dev \
    libavfilter-dev \
    libavdevice-dev \
    libmtdev-dev \
    xclip \
    xauth \
    libxcb-xinerama0 \
    python3-launchpadlib bzr \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


RUN python3 -m pip install --no-cache-dir --upgrade pip

RUN python3 -m pip install --no-cache-dir poetry
RUN poetry self add poetry-plugin-export