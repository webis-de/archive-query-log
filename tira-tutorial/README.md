# TIRA Tutorial for custom Experiments on the Archive Query Log

The Archive Query Log is a comprehensive query log collected at the Internet Archive over the last 25 years. This version includes 357 million queries, 306 million search result pages, and 2.6 billion search results across 550 search providers. TIRA allows to run arbitrary software on this dataset in a privacy preserving way: the results of executed software is blinded until they reviewed (both the output, and the software) to ensure that no sensitive data is leaked. In this tutorial, we will show how to develop a docker image that can be executed in TIRA to produce experiments / evaluations.

# Requirements

This tutorial assumes that you have `Docker`, `git`, `python3`, and `tira` installed. If not:

- Please use official documentation/tutorials to install docker, git and python3 on your machine.
- Please run `pip3 install tira` to install the TIRA client library on your machine.

Please note: If you use windows, we have the experience that there are problems with docker in git-bash that do not appear in the standard windows shell. I.e., please use the powershell on windows, or the Windows Subsystem for Linux.

# Step 1: Implement Your Experment / Analysis

We will create a docker image that covers a simple baseline analysis.

```
docker build -t archive-query-log-experiment-baseline .
```

This docker image contains a script `aql-experiment-baseline.py` that counts how many SERPs each service has.

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

This should yield a result like this (top 3 lines with `cat tira-output/results.json`):

```
{"google": 18, "youtube": 10, "stackoverflow": 10, "twitter": 7, "weibo": 1, "facebook": 1, "sogou": 1, "baidu": 1, "bing": 1}
```

