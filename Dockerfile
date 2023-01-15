FROM --platform=linux/amd64 python:3.10.9-slim

RUN apt update -y && \
    apt install build-essential libpq-dev -y && \
    pip install poetry wheel --upgrade

WORKDIR /app

COPY pyproject.toml setup.py /app/

RUN poetry lock && \
    poetry export -f requirements.txt --without dev | pip install -r /dev/stdin

COPY video_streaming_service/ /app/video_streaming_service/

CMD python -m video_streaming_service
