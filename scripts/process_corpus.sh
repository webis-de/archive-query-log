#!/usr/bin/env bash

PYSPARK_PYTHON=/mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/venv/bin/python \
spark-submit \
    --conf spark.yarn.submit.waitAppCompletion=false \
    --name web-archive-query-log-corpus \
    --master yarn \
    --deploy-mode cluster \
    --num-executors 4 \
    --executor-cores 8 \
    --executor-memory 4g \
    --driver-memory 32g \
    --conf spark.executor.memoryOverhead=8000 \
    --conf spark.driver.memoryOverhead=10000 \
    --conf spark.network.timeout=600 \
    process_corpus.py
