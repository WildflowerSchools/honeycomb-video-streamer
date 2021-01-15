FROM python:3.8.2-slim

#RUN apk add --update ffmpeg g++
RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app
RUN mkdir -p /app/honeycomb_tools

COPY setup.py /app
COPY package.json /app
COPY honeycomb_tools/README.md /app/honeycomb_tools

WORKDIR /app
RUN pip install -e .

COPY honeycomb_tools/*.py /app/honeycomb_tools/
COPY scripts/ /app

CMD sh /app/prepare-volume.sh
