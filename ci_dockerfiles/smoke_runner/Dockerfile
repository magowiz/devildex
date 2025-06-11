FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    xvfb \
    libgl1-mesa-glx \
    libgtk-3-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libice6 \
    libdbus-glib-1-2 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app