#!/usr/bin/bash

while IFS= read -r p; do
  echo "Parse SERPs for: $p"
  sleep 1s

  srun --cpus-per-task 4 --input /dev/null  --ntasks-per-node 1 --mem 40G --container-writable --container-image python:3.10 --container-name web-archive-query-log-python-3.10 --container-mounts "$PWD":/workspace --chdir "$PWD" sh -c "cd /workspace && python -m pipenv run python -m archive_query_log make archived-parsed-serps -d /mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/ -f ${p}"
  wait
done </mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/service_batches/batch-${1}.txt
