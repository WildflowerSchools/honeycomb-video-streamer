ARG TAG=latest
FROM --platform=linux/amd64 wildflowerschools/honeycomb-video-streamer:prepare-stage-0-${TAG} as build

FROM --platform=linux/amd64 python:3.10.9-slim

RUN apt update -y && \
    apt-get install -y \
    libasound2 \
    libgl1 \
    libglib2.0-0 \
    libass9 \
    libmp3lame0 \
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

COPY --from=build /opt/ffmpeg /opt/ffmpeg
COPY --from=build /opt/rav1e/lib/librav1e.so* /usr/lib/

ENV PATH=${PATH}:/opt/ffmpeg/bin

WORKDIR /app

RUN pip install --upgrade pip poetry wheel
RUN pip install opencv-python

COPY setup.py pyproject.toml /app/
RUN poetry lock && \
    poetry export -f requirements.txt --without dev | pip install -r /dev/stdin

RUN mkdir -p /app/honeycomb_tools
COPY honeycomb_tools/README.md /app/honeycomb_tools
COPY honeycomb_tools/*.py /app/honeycomb_tools/
COPY honeycomb_tools/assets/ /app/honeycomb_tools/assets
COPY scripts/ /app

CMD sh /app/prepare-volume.sh
