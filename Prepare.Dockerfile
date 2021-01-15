FROM faithlife/ffmpeg:4.3-buster AS ffmpeg

FROM python:3.8.6-slim

# Old Alpine command
# RUN apk add --update ffmpeg g++

# Update & Upgrade, comment out ffmpeg as long as the current python-slim ffmpeg version is old
RUN apt-get update && \
    apt-get -y upgrade && \
    #apt-get -y install --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy latest version of ffmpeg from build stage
RUN echo "deb http://deb.debian.org/debian buster main non-free" >> /etc/apt/sources.list
COPY --from=ffmpeg /opt/ffmpeg/ffmpeg-*.deb /opt/ffmpeg/
RUN apt-get update && \
  apt-get install -y /opt/ffmpeg/ffmpeg-*.deb && \
  rm -rf /var/lib/apt/lists/*
ENV PATH=${PATH}:/opt/ffmpeg/bin

RUN mkdir -p /app
RUN mkdir -p /app/honeycomb_tools

COPY setup.py /app
COPY package.json /app
COPY honeycomb_tools/README.md /app/honeycomb_tools

WORKDIR /app
RUN pip install -e .

COPY honeycomb_tools/*.py /app/honeycomb_tools/
COPY honeycomb_tools/assets/ /app/honeycomb_tools/assets
COPY scripts/ /app

CMD sh /app/prepare-volume.sh
