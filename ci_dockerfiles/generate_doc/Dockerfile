FROM python:3.13-slim

RUN apt-get update && apt-get install --no-install-recommends -y avahi-daemon \
    avahi-utils make libnss-mdns && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app