# 📜 internet-archive-query-log

Scrape real-life query logs from archived search engine result pages (SERPs) on the Internet Archive.

## Installation

1. Install [Python 3.10](https://python.org/downloads/)
2. Install [pipx](https://pipxproject.github.io/pipx/installation/#install-pipx)
3. Install [Pipenv](https://pipenv.pypa.io/en/latest/install/#isolated-installation-of-pipenv-with-pipx).
4. Install dependencies:
    ```shell
    pipenv install
    ```
   
## Usage

### Queries

To fetch all search queries that were archived from a search engine, use:

```shell
pipenv run python -m internet_archive_query_log queries fetch bing
```

You can first check how many pages of URLs the Internet Archive finds for the configured URL prefix.
(Omit the search engine parameter to get a summary of the number of pages for all configured search engines.)

```shell
pipenv run python -m internet_archive_query_log queries num-pages bing
```

### Search engine result pages (SERPs)

To fetch all search engine result pages (SERPs) that were archived from a search engine, use:

```shell
pipenv run python -m internet_archive_query_log serps fetch bing
```

It is recommended to fetch the corresponding [queries](#queries) first.

You can also check how many chunk files would be created before aggregating all SERPs to a single file.
(Omit the search engine parameter to get a summary of the number of chunks for all configured search engines.)

```shell
pipenv run python -m internet_archive_query_log serps num-chunks bing
```
