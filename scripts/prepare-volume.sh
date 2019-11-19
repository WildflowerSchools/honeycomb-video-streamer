#!/bin/sh

python -m honeycomb_tools prepare-videos-for-environment-for-time-range \
    --environment_name ${ENVIRONMENT_NAME:="capucine"} \
    --output_path /data/videos \
    --output_name ${OUTPUT_NAME:="trash"} \
    --manifest_path /data/videos \
    --start $START_TIME \
    --end $END_TIME
