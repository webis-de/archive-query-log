# Running experiments on the Archive Query Log with TIRA

The [Archive Query Log](..) (AQL) is a comprehensive query log collected at the Internet Archive over the last 25 years. This version includes 357 million queries, 306 million search result pages, and 2.6 billion search results across 550 search providers. [TIRA](https://tira.io) allows to run arbitrary software on this dataset in a privacy preserving way: the results of executed software is blinded until they reviewed (both the output, and the software) to ensure that no sensitive data is leaked. In this tutorial, you'll learn how to develop a Docker image that can be executed in TIRA to run your experiment or evaluation.

## Installation

1. Install [Docker](https://docs.docker.com/get-docker/), [git](https://git-scm.com/downloads), [Python 3](https://python.org/downloads/)
2. Install the [TIRA client](https://pypi.org/project/tira/):
    ```shell
    pip install tira
    ```

Note: On Windows, we recommend to run Docker from the standard Windows command line ([PowerShell](https://microsoft.com/powershell) or CMD) or the [Windows Subsystem for Linux](https://learn.microsoft.com/en-us/windows/wsl/), but _not_ from the [Git Bash](https://gitforwindows.org/#bash).

## Step 1: Implement your experiment

In this tutorial, we use a simple baseline experiment (see the [Python script: `aql-experiment-baseline.py`](aql-experiment-baseline.py)) that counts how many SERPs each search provider has in the AQL.

Now, create a Docker image (see the [Dockerfile](Dockerfile)) that wraps the script.

```shell
docker build -t archive-query-log-experiment-baseline .
```

## Step 2: Test your experiment locally

Use the [TIRA client](https://pypi.org/project/tira/) to execute the experiment locally.
This way, you can test how TIRA would execute it.

```shell
tira-run \
    --command '/aql-experiment-baseline.py --input $inputDataset --output $outputDir' \
    --image archive-query-log-experiment-baseline \
    --input-directory ./validation-data \
    --output-directory ./tira-output
```

Let's break down this `tira-run` command:
- The `--command` option specifies the command to be executed by TIRA, in our example:
    ```shell
    /aql-experiment-baseline.py --input $inputDataset --output $outputDir
    ```
  The example command executes the `aql-experiment-baseline.py` script and specifies the TIRA input and output directories. The arguments `$inputDataset` and `$outputDir` are special arguments that are injected by TIRA.
- The `--image` option specifies which Docker image is used to execute the command (`--command`).
- The `--input-directory` option specifies the directory where the input data is found, in our example: `./validation-data`.
- The `--output-directory` option specifies the directory where the output data should be written.

Inspect the output of the experiment:

```shell
cat tira-output/results.json
```

This should yield a result like this:

```json
{"google": 18, "youtube": 10, "stackoverflow": 10, "twitter": 7, "weibo": 1, "facebook": 1, "sogou": 1, "baidu": 1, "bing": 1}
```

## Step 3: Upload your experiment to TIRA

1. [Login](https://tira.io/login) or [register](https://tira.io/signup) at the TIRA website.
2. Open the [AQL task overview](https://tira.io/task/archive-query-log).
3. Click <kbd>Submit</kbd>, <kbd>Docker Submission</kbd>, then <kbd>Upload Images</kbd>.
4. Tag your Docker image with the prefix assigned by TIRA (replace `<PREFIX>` with the assigned prefix from the TIRA website):
    ```shell
    docker tag archive-query-log-experiment-baseline <PREFIX>/archive-query-log-experiment-baseline:0.0.1
    ```
5. Follow the instructions on the TIRA website to login to the dedicated Docker registry.
6. Push your Docker image to the registry (replace `<PREFIX>` with the assigned prefix from the TIRA website):
    ```shell
    docker push <PREFIX>/archive-query-log-experiment-baseline:0.0.1
    ```
7. The Docker image should be listed on the TIRA website after a short while. If not, click <kbd>Refresh Images</kbd>.

## Step 4: Run your experiment on TIRA

1. Open the [AQL task overview](https://tira.io/task/archive-query-log).
2. Click <kbd>Submit</kbd>, <kbd>Docker Submission</kbd>, then <kbd>Add Container</kbd>.
3. Specify the command from above as the command to be executed by TIRA:
    ```shell
    /aql-experiment-baseline.py --input $inputDataset --output $outputDir
    ```
4. Select the previously uploaded Docker image from the dropdown menu.
5. Click <kbd>Add Container</kbd>.
6. A new tab will appear with a "random" name. Click on the tab to open the container.
7. Select the "Validation" dataset from the dropdown menu.
8. Click <kbd>Run Container</kbd> to start the experiment. 
 
Congrats! You've successfully executed your experiment on the AQL with TIRA. 
Our team will now review the outputs of your experiment and unblind it if it doesn't leak private data. You can check the status of your experiment on the TIRA website.