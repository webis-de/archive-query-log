#!/usr/bin/env bash

hdfs dfs -rm -r -f archive-query-log-urls/

spark-submit \
  --conf spark.yarn.submit.waitAppCompletion=false \
  --name archive-query-log-urls \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 4 \
  --executor-cores 8 \
  --executor-memory 4g \
  --driver-memory 32g \
  --conf spark.executor.memoryOverhead=8000 \
  --conf spark.driver.memoryOverhead=10000 \
  --conf spark.network.timeout=600 \
  create_url_list.py
