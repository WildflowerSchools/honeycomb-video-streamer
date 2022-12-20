FROM python:3.10.9-slim

# Disabled RAV1E for now, uncomment all "# RAV1E: " to enable
ARG FFMPEG_VERSION=5.1.2
# RAV1E: ARG RAV1E_VERSION=0.6.1

#ARG RAV1E_PREFIX=/opt/rav1e
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

# Compile GCC 11.3 to speed up ffmpeg on Arm architecture
# TODO: Add an ARG called ENABLE_GRAVITON that should be enabled before GCC 11.3 is compiled
RUN if [ "$(uname -m)" = "aarch64" ] ; then \
      echo "Compiling GCC 11.3"; \
      export ARCHITECTURE="aarch64-linux-gnu"; \
    else \
      printf "Using system default GCC:\n\n`gcc --version`\n\n"; \
      exit; \
    fi && \
    wget https://github.com/gcc-mirror/gcc/archive/refs/tags/releases/gcc-11.3.0.tar.gz && \
    tar zxf gcc-11.3.0.tar.gz && \
    rm gcc-11.3.0.tar.gz && \
    cd gcc-releases-gcc-11.3.0 && \
    contrib/download_prerequisites && \
    mkdir -p build && cd build && \
    ../configure -v \
      --build=${ARCHITECTURE} \
      --host=${ARCHITECTURE} \
      --target=${ARCHITECTURE} \
      --prefix=/usr/local/gcc-11.3.0 \
      --enable-checking=release \
      --enable-languages=c,c++ \
      --disable-multilib \
      --program-suffix=-11.3 && \
    make ${MAKEFLAGS} && \
    make install-strip && \
    export PATH=/usr/local/gcc-11.3.0/bin:$PATH && \
    export LD_LIBRARY_PATH=/usr/local/gcc-11.3.0/lib64:$LD_LIBRARY_PATH && \
    export CC=/usr/local/gcc-11.3.0/bin/gcc-11.3 && \
    export CXX=/usr/local/gcc-11.3.0/bin/g++-11.3 && \
    rm /usr/bin/gcc && \
    ln -s /usr/local/gcc-11.3.0/bin/gcc-11.3 /usr/bin/gcc

# RAV1E: # Install Rust and Cargo w/ Cargo-C
# RAV1E: # Added "--config "net.git-fetch-with-cli=true" to avoid an OOM error: https://github.com/near/near-enhanced-api-server/pull/7
# RAV1E: RUN curl https://sh.rustup.rs -sSf | sh -s -- -y && \
# RAV1E:     export PATH=$HOME/.cargo/bin:$PATH && \
# RAV1E:     cargo --config "net.git-fetch-with-cli=true" install cargo-quickinstall && \
# RAV1E:     cargo quickinstall cargo-c

# RAV1E: # Get rav1e source and install library
# RAV1E: RUN wget https://github.com/xiph/rav1e/archive/refs/tags/v${RAV1E_VERSION}.tar.gz && \
# RAV1E:    tar zxf v${RAV1E_VERSION}.tar.gz && \
# RAV1E:    rm v${RAV1E_VERSION}.tar.gz && \
# RAV1E:    cd /tmp/rav1e-${RAV1E_VERSION} && \
# RAV1E:    mkdir -p /usr/local/lib && \
# RAV1E:    export PATH=$HOME/.cargo/bin:$PATH && \
# RAV1E:    cargo cinstall \
# RAV1E:      --library-type=cdylib \
# RAV1E:      --release \
# RAV1E:      --prefix=${RAV1E_PREFIX} \
# RAV1E:      --libdir=${RAV1E_PREFIX}/lib \
# RAV1E:      --includedir=${RAV1E_PREFIX}/include

# RAV1E:       PKG_CONFIG_PATH=${RAV1E_PREFIX}/lib/pkgconfig \
# RAV1E:       C_INCLUDE_PATH=${RAV1E_PREFIX}/include/rav1e \

# RAV1E:       --enable-librav1e \

# RAV1E:       PKG_CONFIG_PATH=${RAV1E_PREFIX}/lib/pkgconfig \
# RAV1E:       C_INCLUDE_PATH=${RAV1E_PREFIX}/include/rav1e:${RAV1E_PREFIX}/lib \
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
