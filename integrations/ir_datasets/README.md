# `ir_datasets` Integration


```shell
docker run --rm -ti \
    -v ${PWD}/../../tira/validation-data/:/data:ro \
    -v ${PWD}/aql-corpus-for-tira:/output \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --ir_datasets_id archive-query-log --output_dataset_path /output --output_dataset_truth_path /output/truth
```

```shell
tira-run \
    --input-directory ${PWD}/aql-corpus-for-tira \
    --image webis/tira-ir-starter-pyterrier:0.0.2-base \
    --command '/workspace/run-pyterrier-notebook.py --input $inputDataset --output $outputDir --notebook /workspace/full-rank-pipeline.ipynb'
```

```shell
tira-run \
    --input-directory ${PWD}/tira-output \
    --image mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --allow-network true \
    --command 'diffir --dataset archive-query-log --web $outputDir/run.txt > $outputDir/run.html'
```

```shell
tira-run \
    --input-directory ${PWD}/tira-output \
    --image mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --command 'ir_measures archive-query-log $outputDir/run.txt nDCG@10'
```


```shell
docker run --rm -ti \
    -v ${PWD}/../../tira/random-10000-2023-05-14/:/data:ro \
    -v ${PWD}/aql-corpus-for-tira:/output \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --ir_datasets_id archive-query-log --output_dataset_path /output --output_dataset_truth_path /output/truth
```

```shell
docker run --rm -ti \
    -v ${PWD}/../../tira/random-10000-2023-05-14/:/data:rw \
    -v ${PWD}/aql-corpus-for-tira:/output \
    --entrypoint python3 \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    /usr/lib/python3.8/site-packages/ir_datasets/datasets_in_progress/archive_query_log_ir_datasets_integration.py
```

```shell
docker run --rm -ti \
    -v ${PWD}/../../tira/random-10000-2023-05-14/:/data:rw \
    -v ${PWD}/aql-corpus-for-tira:/output \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --ir_datasets_id archive-query-log --rerank /data --output_dataset_path /outputs
```


```shell
docker run --rm -ti \
    -v ${PWD}/../../tira/random-10000-2023-05-14/:/data:ro \
    -v ${PWD}/tira-output:/tira-runs \
    --entrypoint sh \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    -c 'ir_measures archive-query-log /tira-runs/run.txt nDCG@10'
```
