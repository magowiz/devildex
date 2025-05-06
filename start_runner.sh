#!/bin/bash
docker rm -f runner_devildex 2>/dev/null || true
docker build -f runner/Dockerfile . -t runner_devildex
docker run -d -it \
	--env="DISPLAY" \
	--env="XAUTHORITY=/root/.Xauthority" \
	--volume="$HOME/.Xauthority:/root/.Xauthority:rw" \
	--volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
	--name runner_devildex runner_devildex
