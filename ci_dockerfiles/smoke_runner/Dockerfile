FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libdbus-glib-1-2 \
    libfontconfig1 \
    libglx-mesa0 \
    libgtk-3-0 \
    libice6 \
    libnotify4 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    xvfb \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app