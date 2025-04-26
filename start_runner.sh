#!/bin/bash
docker rm -f runner_devildex 2>/dev/null || true
docker build -f runner/Dockerfile . -t runner_devildex
docker run -d --name runner_devildex runner_devildex
