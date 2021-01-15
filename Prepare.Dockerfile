FROM python:3.8.2-alpine

RUN apk add ffmpeg g++

RUN mkdir -p /app
RUN mkdir -p /app/honeycomb_tools
COPY scripts/ /app
COPY honeycomb_tools/*.py /app/honeycomb_tools/
COPY setup.py /app
COPY package.json /app
COPY honeycomb_tools/README.md /app/honeycomb_tools

WORKDIR /app

RUN pip install -e .


CMD sh /app/prepare-volume.sh
