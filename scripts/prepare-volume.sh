#!/bin/sh

cmd_extras=""
if [ ! -z "${REWRITE}"  ] && [ "${REWRITE}" = "true" ]; then
    cmd_extras="--rewrite"
fi

if [ ! -z "${APPEND}"  ] && [ "${APPEND}" = "true" ]; then
    cmd_extras="${cmd_extras} --append"
fi

if [ ! -z "${CLEANUP}"  ] && [ "${CLEANUP}" = "true" ]; then
    cmd_extras="${cmd_extras} --cleanup"
fi

python -m video_prepare prepare-videos-for-environment-for-time-range \
    --environment_name ${ENVIRONMENT_NAME} \
    --video_directory /data/videos \
    --raw_video_storage_directory /data \
    --video_name ${VIDEO_NAME} \
    --start ${START_TIME} \
    --end ${END_TIME} \
    ${cmd_extras}
