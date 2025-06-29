FROM python:3.13-slim

RUN apt-get update && apt-get install --no-install-recommends -y avahi-daemon \
    avahi-utils libnss-mdns make && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir poetry && poetry self add poetry-plugin-export
WORKDIR /app