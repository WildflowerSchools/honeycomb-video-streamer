FROM --platform=linux/amd64 python:3.10.9-slim as build

ARG FFMPEG_VERSION=5.1.2
ARG RAV1E_VERSION=0.6.1

ARG RAV1E_PREFIX=/opt/rav1e
ARG FFMPEG_PREFIX=/opt/ffmpeg
ARG MAKEFLAGS="-j4"

RUN apt update -y && apt install -y \
    autoconf \
    automake \
    build-essential \
    cmake \
    curl \
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

# Install Rust and Cargo w/ Cargo-C
# Added "--config "net.git-fetch-with-cli=true" to avoid an OOM error: https://github.com/near/near-enhanced-api-server/pull/7
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    export PATH=$HOME/.cargo/bin:$PATH && \
    cargo --config "net.git-fetch-with-cli=true" install cargo-quickinstall && \
    cargo quickinstall cargo-c

# Get rav1e source and install library
RUN wget https://github.com/xiph/rav1e/archive/refs/tags/v${RAV1E_VERSION}.tar.gz && \
    tar zxf v${RAV1E_VERSION}.tar.gz && \
    rm v${RAV1E_VERSION}.tar.gz && \
    cd /tmp/rav1e-${RAV1E_VERSION} && \
    mkdir -p /usr/local/lib && \
    export PATH=$HOME/.cargo/bin:$PATH && \
    cargo cinstall \
      --library-type=cdylib \
      --release \
      --prefix=${RAV1E_PREFIX} \
      --libdir=${RAV1E_PREFIX}/lib \
      --includedir=${RAV1E_PREFIX}/include

# Get ffmpeg source and install library
RUN wget http://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.gz && \
    tar zxf ffmpeg-${FFMPEG_VERSION}.tar.gz && \
    rm ffmpeg-${FFMPEG_VERSION}.tar.gz && \
    cd /tmp/ffmpeg-${FFMPEG_VERSION} && \
      PKG_CONFIG_PATH=${RAV1E_PREFIX}/lib/pkgconfig \
      C_INCLUDE_PATH=${RAV1E_PREFIX}/include/rav1e \
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
      --enable-librtmp \
      --enable-librav1e \
      --enable-postproc \
      --enable-libfreetype \
      --enable-openssl \
      --disable-debug \
      --disable-doc \
      --disable-ffplay \
      --extra-cflags="-I${FFMPEG_PREFIX}/include" \
      --extra-ldflags="-L${FFMPEG_PREFIX}/lib" \
      --extra-libs="-lpthread -lm" \
      --prefix="${FFMPEG_PREFIX}" && \
      PKG_CONFIG_PATH=${RAV1E_PREFIX}/lib/pkgconfig \
      C_INCLUDE_PATH=${RAV1E_PREFIX}/include/rav1e:${RAV1E_PREFIX}/lib \
      make ${MAKEFLAGS} && make install && make distclean


FROM --platform=linux/amd64 python:3.10.9-slim

RUN apt update -y && \
    apt-get install -y \
    libgl1 \
    libglib2.0-0

COPY --from=build /opt/ffmpeg /opt/ffmpeg
COPY --from=build /opt/rav1e/lib/librav1e.so /usr/lib/librav1e.so

ENV PATH=${PATH}:/opt/ffmpeg/bin

WORKDIR /app

RUN pip install --upgrade pip poetry wheel
RUN pip install opencv-python

COPY setup.py pyproject.toml /app/
RUN poetry lock && poetry export -f requirements.txt --without dev | pip install -r /dev/stdin

RUN mkdir -p /app/honeycomb_tools
COPY honeycomb_tools/README.md /app/honeycomb_tools
COPY honeycomb_tools/*.py /app/honeycomb_tools/
COPY honeycomb_tools/assets/ /app/honeycomb_tools/assets
COPY scripts/ /app

CMD sh /app/prepare-volume.sh
