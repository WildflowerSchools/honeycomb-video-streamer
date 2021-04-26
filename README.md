# honeycomb-video-streamer

## Development

### Run the node server:

Fill out `.docker.env`, then run:

```
just _build-docker-service
docker run --rm -p 8000:8000 --volume "/$(pwd)/public/videos:/app/public/videos" --env-file ./.docker.env wildflowerschools/honeycomb-video-streamer:v26
```
