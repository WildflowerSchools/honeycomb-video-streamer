# honeycomb-video-streamer

Provides a postgres storage API for storing and serving video

Also includes a prepare service for building streamable video from raw classroom video

## Development

### Setup poetry

If using pyenv, select/set your pyenv environment and run: 

      poetry env use $(pyenv which python)

Then install packages:

      poetry install

### Run the python streaming service:

* Copy `.env.template` to `.env`

      cp .env.template .env

* Update ENV vars as needed
* Run the streaming service with docker-compose (build happens automatically)

      just docker-run-streaming-service

* The streaming API should be exposed via port 8000


### Prepare video:

* Copy `./video_prepare/.env.template` to `./video_prepare/.env`

      cp ./video_prepare/.env.template ./video_prepare/.env

* Update ENV vars as needed

#### Run via Docker:

* Build all video-streamer services and stand up the streaming DB + API service

      just build
      just docker-run-streaming-service


* Run the video prepare job (this example fetches video for greenbrier on 5/27/2021):

      docker run -ti \
        --rm \
        --volume $(pwd)/public/videos:/data/videos \
        --network honeycomb-video-streamer_default \
        --env-file ./video_prepare/.env \
        --env ENVIRONMENT_NAME=greenbrier \
        --env VIDEO_NAME=2021-05-27 \
        --env START_TIME=2021-05-27T09:00-0600 \
        --env END_TIME=2021-05-27T09:10-0600 \
        --env REWRITE=true \
        --env VIDEO_STREAM_SERVICE_URI=http://streamer:8000 \
        honeycomb-video-streamer-prepare:latest


#### Run locally:

* Run: `just install-dev`
* Run (this example fetches video for greenbrier on 5/27/2021):

      python -m video_prepare prepare-videos-for-environment-for-time-range \
      --environment_name greenbrier \
      --video_directory ./public/videos \
      --video_name 2021-05-27 \
      --start 2021-05-27T09:00-0600 \
      --end 2021-05-27T09:10-0600 \
      --rewrite
