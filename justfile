version := "test"

system-info:
    @echo "system info: {{ os() }} ({{ os_family() }}) on {{arch()}}".

fmt:
    black ./video_prepare/
    black ./video_streaming_service/

install-dev:
    pip install -e .[development]

_build-docker-service:
    @docker-compose -f stack.yml build

_build-docker-prepare:
    @docker buildx build --build-arg TAG={{version}} -t wildflowerschools/honeycomb-video-streamer:prepare-{{version}} --platform linux/arm64 --cache-from=type=local,src=/tmp/buildx-cache --cache-to=type=local,dest=/tmp/buildx-cache -f Prepare.Dockerfile --load .

build: _build-docker-service _build-docker-prepare

docker-run-streamer:
    @docker-compose -f stack.yml up -d --build

lint-streaming-service:
    @pylint video_streaming_service

lint-prepare-service:
    @pylint video_prepare

lint: lint-streaming-service lint-prepare-service

start-streaming-service:
    @uvicorn video_streaming_service:app --reload --port 8000
