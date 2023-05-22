


```
docker run --rm -ti \
    -v ${PWD}/../../tira-tutorial/validation-data/:/data:ro \
    -v ${PWD}/aql-corpus-for-tira:/output \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --ir_datasets_id archive-query-log --output_dataset_path /output --output_dataset_truth_path /output/truth
```

```
tira-run \
    --input-directory ${PWD}/aql-corpus-for-tira \
    --image webis/tira-ir-starter-pyterrier:0.0.2-base \
    --command '/workspace/run-pyterrier-notebook.py --input $inputDataset --output $outputDir --notebook /workspace/full-rank-pipeline.ipynb'
```

```
tira-run \
    --input-directory ${PWD}/tira-output \
    --image mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --allow-network true \
    --command 'diffir --dataset archive-query-log --web $outputDir/run.txt > $outputDir/run.html'
```

```
tira-run \
    --input-directory ${PWD}/tira-output \
    --image mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --command 'ir_measures archive-query-log $outputDir/run.txt nDCG@10'
```


```
docker run --rm -ti \
    -v ${PWD}/../../tira-tutorial/random-10000-2023-05-14/:/data:ro \
    -v ${PWD}/aql-corpus-for-tira:/output \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    --ir_datasets_id archive-query-log --output_dataset_path /output --output_dataset_truth_path /output/truth
```

```
docker run --rm -ti \
    -v ${PWD}/../../tira-tutorial/random-10000-2023-05-14/:/data:ro \
    -v ${PWD}/tira-output:/tira-runs \
    --entrypoint sh \
    mam10eks/archive-query-log-ir-datasets-integration:0.0.1 \
    -c 'ir_measures archive-query-log /tira-runs/run.txt nDCG@10'
```
