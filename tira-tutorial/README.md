# TIRA Tutorial for custom Experiments on the Archive Query Log

# Step 1: Implement baseline retrieval approaches

We will create a docker image that covers a simple baseline analysis.

```
docker build -t archive-query-log-experiment-baseline .
```

# Step 2: Test your retrieval approach locally

To execute the script that we included in our docker image on your system as TIRA would execute it, the command is:

```
tira-run \
    --input-directory ${PWD}/validation-data \
    --image archive-query-log-experiment-baseline \
    --command '/aql-experiment-baseline.py --input $inputDataset --output $outputDir'
```

In this `tira-run` example, we set the arguments as follows:

- `--command` specified the command that is to be executed in the container. Our command here is `/aql-experiment-baseline.py --input $inputDataset --output $outputDir` which specifies that we execute the mentioned `aql-experiment-baseline.py` script that itself gets an input and output. The passed arguments `$inputDataset` and `$outputDir` are the input respectively output directories that are injected by TIRA.
- `--image` specifies the docker image in which `--command` is executed
- `--input-directory` specifies the directory with the input data.
- `--output-directory` specifies the directory to which the output data is written.

This should yield a run like (top 3 lines with `head -3 tira-output/run.txt`):
