#!/usr/bin/env bash

if [ "$1" = "--small" ]; then
  variant="small"
elif [ "$1" = "--medium" ]; then
  variant="medium"
elif [ "$1" = "--full" ]; then
  variant="full"
elif [ "$#" -eq 0 ]; then
  variant="full"
else
  echo "Usage: ./create_corpus.sh [--small|--medium|--full]"
  exit 1
fi

hdfs dfs -mkdir -p archive-query-log/$variant/
hdfs dfs -rm -r -f archive-query-log/$variant/serps/
hdfs dfs -rm -r -f archive-query-log/$variant/results/

PYSPARK_PYTHON=/mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/venv/bin/python \
  spark-submit \
  --conf spark.yarn.submit.waitAppCompletion=false \
  --name archive-query-log-corpus \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 4 \
  --executor-cores 8 \
  --executor-memory 4g \
  --driver-memory 32g \
  --conf spark.executor.memoryOverhead=8000 \
  --conf spark.driver.memoryOverhead=10000 \
  --conf spark.network.timeout=600 \
  create_corpus.py --$variant
