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

* Copy `./honeycomb_tools/.env.template` to `./honeycomb_tools/.env`

      cp ./honeycomb_tools/.env.template ./honeycomb_tools/.env

* Update ENV vars as needed
* Run: `just install-dev`
* Run (this example fetches video for greenbrier on 5/27/2021):

      python -m honeycomb_tools prepare-videos-for-environment-for-time-range \
      --environment_name greenbrier \
      --video_directory ./public/videos \
      --video_name 2021-05-27 \
      --start 2021-05-27T09:00-0600 \
      --end 2021-05-27T09:10-0600 \
      --rewrite
