#!/bin/sh

rewrite_append=""
if [ ! -z "${REWRITE}"  ] && [ "${REWRITE}" = "true" ]; then
    rewrite_append="--rewrite"
fi

if [ ! -z "${APPEND}"  ] && [ "${APPEND}" = "true" ]; then
    rewrite_append+=" --append"
fi

python -m honeycomb_tools prepare-videos-for-environment-for-time-range \
    --environment_name ${ENVIRONMENT_NAME} \
    --output_path /data/videos \
    --output_name ${OUTPUT_NAME:="trash"} \
    --start $START_TIME \
    --end $END_TIME \
    ${rewrite_append}
