FROM python:3.12-slim
RUN apt-get update && apt-get install --no-install-recommends -y lftp curl xvfb xdg-utils jq gcc git libsdl2-dev \
     ffmpeg libavcodec-dev libavfilter-dev libavdevice-dev libmtdev-dev xclip xauth  libxcb-xinerama0 \
    && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip