FROM --platform=linux/amd64 python:3.12.0rc2-slim

RUN apt update -y && \
    apt install build-essential libpq-dev -y && \
    pip install poetry wheel --upgrade

WORKDIR /app

COPY poetry.lock pyproject.toml setup.py /app/

#RUN poetry lock && \
#    poetry export -f requirements.txt --without dev | pip install -r /dev/stdin
RUN poetry config virtualenvs.create false && poetry install --without dev --no-interaction --no-ansi  --no-root

COPY video_streaming_service/ /app/video_streaming_service/

CMD python -m video_streaming_service
