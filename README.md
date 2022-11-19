# 📜 internet-archive-query-log

Scrape real-life query logs from archived search engine result pages (SERPs) on the Internet Archive.

## Contents
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
- [Contribute](#contribute)

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
pipenv run python -m web_archive_query_log queries fetch bing
```

You can first check how many pages of URLs the Internet Archive finds for the configured URL prefix.
(Omit the search engine parameter to get a summary of the number of pages for all configured search engines.)

```shell
pipenv run python -m web_archive_query_log queries num-pages bing
```

### Search engine result pages (SERPs)

To fetch all search engine result pages (SERPs) that were archived from a search engine, use:

```shell
pipenv run python -m web_archive_query_log serps fetch bing
```

It is recommended to fetch the corresponding [queries](#queries) first.

You can also check how many chunk files would be created before aggregating all SERPs to a single file.
(Omit the search engine parameter to get a summary of the number of chunks for all configured search engines.)

```shell
pipenv run python -m web_archive_query_log serps num-chunks bing
```

## Architecture

1. Collect services.
2. Collect service domains.
3. Collect archived service URLs.
4. Filter archived service URLs and identify URLs with query data.
5. Parse queries and SERP URLs from service URLs.
6. Download archived SERPs.
7. Parse downloaded SERPs.
8. Download archived documents linked from SERPs, if available.
9. Build IR test collection.

## Contribute

If you've found a search engine to be missing from this query log, please add the corresponding [query source](#adding-query-sources) or add [SERP parser(s)](#adding-serp-parsers) to enhance the query log with ranked results.
We gratefully accept [issues](https://git.webis.de/code-research/web-search/internet-archive-query-log/-/issues) and [pull requests](https://git.webis.de/code-research/web-search/internet-archive-query-log/-/merge_requests)!
If you're unsure about anything, post an [issue](https://git.webis.de/code-research/web-search/internet-archive-query-log/-/issues), or [contact us](mailto:jan.reimer@student.uni-halle.de).

## Adding query sources

Follow these steps to add a `Source` to the [configuration](web_archive_query_log/config.py):
1. Most important is the `url_prefix` that is used to fetch lists of archived snapshots. Keep that as precise as possible but keep in mind that not all URLs are well-formed. (Note that the prefix matches all URLs that start with the )
2. Specify a `query_parser`, that is, where in the URL is the query found. For most sites that is probably `QueryParameter("q")`, i.e., the `q=` parameter in the URLs query string.
3. For now, you can leave `serp_parsers` empty. We can gradually [add parsers](#adding-serp-parsers) later to cover most SERPs.

You can get a rough estimate of how many pages of URLs will be fetched with `pipenv run python -m internet_archive_query_log queries num-pages bing` (see [above](#queries)).
Note that some sites (e.g., Amazon and eBay) operate on multiple TLDs. Instead of adding individual sources for each domain, it is often easier to use Python list comprehension to create the same source for multiple domains.
An example can be seen [here](https://git.webis.de/code-research/web-search/internet-archive-query-log/-/blob/d6d927248e0c215cffe68d064097a7290ee47de0/internet_archive_query_log/config.py#L193-L200).

## Adding SERP parsers

TBD
