version := "v36"

environment_name := "greenbrier"
output_path := "public/videos"
output_name := "2021-05-28"
start := "2021-05-28T13:00"
end := "2021-05-28T17:00"

system-info:
    @echo "system info: {{ os() }} ({{ os_family() }}) on {{arch()}}".

fmt-python:
    autopep8 --aggressive --recursive --in-place ./honeycomb_tools/
    autopep8 --aggressive --recursive --in-place ./multiview_stream_service/

install-dev:
    npm install
    pip install -e .[development]

_build-docker-service:
    @docker build -t wildflowerschools/honeycomb-video-streamer:{{version}} -f Dockerfile .

_build-docker-prepare:
    @docker build -t wildflowerschools/honeycomb-video-streamer:prepare-{{version}} -f Prepare.Dockerfile .

build-docker: _build-docker-service _build-docker-prepare

docker-push: build-docker
    @docker push wildflowerschools/honeycomb-video-streamer:{{version}}
    @docker push wildflowerschools/honeycomb-video-streamer:prepare-{{version}}


prepare-videos:
    @python -m honeycomb_tools prepare-videos-for-environment-for-time-range  --environment_name {{environment_name}} --output_path {{output_path}} --output_name {{output_name}} --start {{start}} --end {{end}}


list-datapoints:
    @python -m honeycomb_tools list-datapoints-for-environment-for-time-range  --environment_name {{environment_name}} --output_path ./ --output_name datapoints.csv --start {{start}} --end {{end}}

lint-app:
    @pylint multiview_stream_service

start-app: lint-app
    @uvicorn multiview_stream_service:app --reload


start-postgres:
    @docker run -it -p 5432:5432 -e POSTGRES_PASSWORD=mysecretpassword -e POSTGRES_DB=multiview -e POSTGRES_USER=pollu postgres
