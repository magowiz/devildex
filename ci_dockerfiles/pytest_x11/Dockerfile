FROM fedora:42

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN dnf update -y &&     dnf install -y     python \
    python-devel     python-pip     gcc     gcc-c++ \
    git     curl     lftp     xorg-x11-server-Xvfb \
    xdg-utils     jq     SDL2-devel     xclip     xorg-x11-xauth \
    patchelf     glib2-devel     cmake cairo-devel cairo-gobject-devel \
    gawk gtk3-devel     libjpeg-turbo-devel \
    libjpeg-turbo \
    libjpeg \
    libpng-devel     libtiff-devel     gstreamer1-plugins-base-devel     libnotify-devel \
    freeglut-devel \
    python3-wxpython4 \
    webkit2gtk4.1-devel \
    && dnf clean all

ENV PATH="/root/.local/bin:${PATH}"

RUN python -m pip install --no-cache-dir --upgrade pip pipx && \
    pipx install poetry && \
    poetry self add poetry-plugin-export \



