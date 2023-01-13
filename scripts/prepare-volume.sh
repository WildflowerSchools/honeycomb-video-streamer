#!/bin/sh

rewrite_append=""
if [ ! -z "${REWRITE}"  ] && [ "${REWRITE}" = "true" ]; then
    rewrite_append="--rewrite"
fi

if [ ! -z "${APPEND}"  ] && [ "${APPEND}" = "true" ]; then
    rewrite_append="${rewrite_append} --append"
fi

python -m video_prepare prepare-videos-for-environment-for-time-range \
    --environment_name ${ENVIRONMENT_NAME} \
    --video_directory /data/videos \
    --video_name ${VIDEO_NAME:="trash"} \
    --start $START_TIME \
    --end $END_TIME \
    ${rewrite_append}
