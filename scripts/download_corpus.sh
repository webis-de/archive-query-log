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
  echo "Usage: ./download_corpus.sh [--small|--medium|--full]"
  exit 1
fi

hdfs dfs -mkdir -p archive-query-log/$variant/serps/
hdfs dfs -mkdir -p archive-query-log/$variant/results/

download_dir=/mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/focused/corpus/$variant/$(date '+%Y-%m-%d')
echo "Preparing download to: $download_dir"
mkdir -p "$download_dir"
rm -r -f "$download_dir"
mkdir -p "$download_dir"
echo "Cleaned up $download_dir"

echo "Downloading SERPs to: $download_dir/serps"
hdfs dfs -get archive-query-log/$variant/serps/ "$download_dir"/serps
echo "Finished downloading SERPs."

echo "Downloading results to: $download_dir/results"
hdfs dfs -get archive-query-log/$variant/results/ "$download_dir"/results
echo "Finished downloading results."