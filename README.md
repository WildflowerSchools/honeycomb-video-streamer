# honeycomb-video-streamer

## Development

### Prepare video:

* Copy `./honeycomb_tools/.env.template` to `./honeycomb_tools/.env`
* Run: `just install-dev`
* Run:

    python -m honeycomb_tools prepare-videos-for-environment-for-time-range
        --environment_name greenbrier
        --output_path <<PROJECT_DIR>>/public/videos
        --output_name 2021-05-03
        --start 2021-05-03T20:00
        --end 2021-05-03T21:00
        --append

### Run the python server:

Fill out `.docker.env`, then run:

```
just version=vXX _build-docker-service
docker run --rm -p 8000:8000 --volume "/$(pwd)/public/videos:/app/public/videos" --env-file ./.docker.env wildflowerschools/honeycomb-video-streamer:vXX
```
