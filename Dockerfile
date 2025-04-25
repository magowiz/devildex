# Stage 1: Build Environment Setup
FROM ubuntu:plucky AS builder

# Set build arguments for versions
ARG PYTHON_VERSION=3.13
ARG POETRY_VERSION=2.1.0

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1

# Ensure that the locale is set to UTF-8
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Set environment variables for Poetry configuration
ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_HOME="/opt/poetry" \
    PATH="/root/.local/bin:/opt/poetry/bin:${PATH}"

# Install necessary OS packages:
# - python3, python3-venv, python3-pip: Core Python environment (Ubuntu 24.04 default is 3.12)
# - build-essential: For compiling native extensions
# - curl: To download Poetry installer
# - git: Useful for cloning if needed, or used by some tools
# - mingw-w64: Cross-compilation toolchain for Windows
# - mingw-w64-i686-gcc: Explicitly install 32-bit mingw gcc if needed for some builds (less common now)
# - mingw-w64-x86-64-gcc: Explicitly install 64-bit mingw gcc
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    curl \
    git \
    mingw-w64 \
    python-is-python3 \
    python3-dev \
    patchelf \
    pipx && \
    rm -rf /var/lib/apt/lists/* # Clean up immediately

# Install Poetry using the official script
# Use the specified POETRY_VERSION build argument
# Need to make sure the default 'python3' command points to the desired version if multiple are installed.
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}
RUN poetry self add poetry-plugin-export
# Set PATH for mingw-w64 compilers
# Verify exact path after installation on Ubuntu Noble. Common paths include /usr/bin or /usr/lib/mingw-w64/bin
# Let's check common install path for x86_64-w64-mingw32-gcc
RUN if [ -d "/usr/bin/x86_64-w64-mingw32" ]; then export PATH="/usr/bin/x86_64-w64-mingw32:${PATH}"; fi
RUN if [ -d "/usr/lib/mingw-w64/bin" ]; then export PATH="/usr/lib/mingw-w64/bin:${PATH}"; fi


# Set the working directory inside the container
WORKDIR /app

# Copy the project files into the container
# Copy pyproject.toml and poetry.lock first to leverage Docker cache if only code changes

# Install bundling tools using pip within the Poetry environment
RUN pipx install nuitka pyoxidizer

# No need for CMD or ENTRYPOINT for a build image.
# The Jenkinsfile will run commands like 'poetry run python ...' or 'poetry run cxfreeze ...'