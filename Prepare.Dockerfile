FROM python:3.13.0a2-slim as build

ARG FFMPEG_VERSION=6.0

ARG FFMPEG_PREFIX=/opt/ffmpeg
ARG MAKEFLAGS="-j8"

RUN apt update -y && apt install -y \
    autoconf \
    automake \
    build-essential \
    cmake \
    curl \
    flex \
    git-core \
    libass-dev \
    libfreetype6-dev \
    libgnutls28-dev \
    libmp3lame-dev \
    libopus-dev \
    librtmp-dev \
    libsdl2-dev \
    libssl-dev \
    libtheora-dev \
    libtool \
    libva-dev \
    libvdpau-dev \
    libvorbis-dev \
    libvpx-dev \
    libwebp-dev \
    libxcb1-dev \
    libxcb-shm0-dev \
    libxcb-xfixes0-dev \
    libx264-dev \
    libx265-dev \
    meson \
    nasm \
    ninja-build \
    pkg-config \
    texinfo \
    wget \
    yasm \
    zlib1g-dev

WORKDIR /tmp

COPY ./scripts/add-testing-channel-to-debian.sh .

# Install GCC 11.3 from Debian testing channel to speed up ffmpeg on Arm architecture
# TODO: Add an ARG called ENABLE_GRAVITON that should be enabled before GCC 11.3 is compiled
RUN chmod +x add-testing-channel-to-debian.sh && \
    ./add-testing-channel-to-debian.sh && \
    apt -y update && \
    apt-get -y -t testing install gcc-11 librav1e-dev rav1e && \
    rm /usr/bin/gcc && \
    ln -s /usr/bin/gcc-11 /usr/bin/gcc

# Get ffmpeg source and install library
RUN wget http://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.gz && \
    tar zxf ffmpeg-${FFMPEG_VERSION}.tar.gz && \
    rm ffmpeg-${FFMPEG_VERSION}.tar.gz && \
    cd /tmp/ffmpeg-${FFMPEG_VERSION} && \
      if [ "$(uname -m)" = "aarch64" ]; then \
        export GRAVITON_CFLAG="-mcpu=neoverse-512tvb"; \
      fi && \
      ./configure \
      --enable-version3 \
      --enable-gpl \
      --enable-nonfree \
      --enable-small \
      --enable-libmp3lame \
      --enable-libx264 \
      --enable-libx265 \
      --enable-libvpx \
      --enable-libtheora \
      --enable-libvorbis \
      --enable-libopus \
      --enable-libass \
      --enable-libwebp \
      --enable-librav1e \
      --enable-librtmp \
      --enable-postproc \
      --enable-libfreetype \
      --enable-openssl \
      --disable-debug \
      --disable-doc \
      --disable-ffplay \
      --extra-cflags="-I${FFMPEG_PREFIX}/include ${GRAVITON_CFLAG}" \
      --extra-ldflags="-L${FFMPEG_PREFIX}/lib" \
      --extra-libs="-lpthread -lm" \
      --prefix="${FFMPEG_PREFIX}" && \
      make ${MAKEFLAGS} && make install && make distclean


FROM python:3.13.0a2-slim

RUN apt update -y && \
    apt-get install -y \
    build-essential \
    libasound2 \
    libgl1 \
    libglib2.0-0 \
    libass9 \
    libmp3lame0 \
    libpq-dev \
    librtmp1 \
    libsdl2-2.0-0 \
    libsndio7.0 \
    libtheora0 \
    libva-drm2 \
    libva-x11-2 \
    libva2 \
    libvdpau1 \
    libvpx6 \
    libwebpmux3 \
    libxcb-shape0 \
    libx264-160 \
    libx265-192 \
    libxv1

COPY ./scripts/add-testing-channel-to-debian.sh .

RUN chmod +x add-testing-channel-to-debian.sh && \
    ./add-testing-channel-to-debian.sh && \
    apt -y update && \
    apt-get -y -t testing install librav1e-dev

COPY --from=build /opt/ffmpeg /opt/ffmpeg

ENV PATH=${PATH}:/opt/ffmpeg/bin

WORKDIR /app

RUN pip install --upgrade pip poetry wheel
RUN pip install opencv-python

COPY setup.py pyproject.toml /app/
RUN poetry lock && \
    poetry export -f requirements.txt --without dev | pip install -r /dev/stdin

RUN mkdir -p /app/video_prepare
COPY video_prepare/ /app/video_prepare/
COPY scripts/ /app

CMD sh /app/prepare-volume.sh
