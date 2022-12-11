# 📜 Web Archive Query and Search Logs

Scrape real-life query logs from archived query URLs and search engine result pages (SERPs) on the Internet Archive.

[Start now](#tldr) by scraping your own query log [here](#tldr).

## Contents

- [Installation](#installation)
- [Usage](#tldr)
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

To quickly scrape a sample query log, jump to the [TL;DR](#tldr).

If you want to learn more about each step here are some more detailed guides:

1. [Select services](#1-selected-services)
2. [Fetch archived URLs](#2-archived-urls)
3. [Parse archived query URLs](#3-archived-query-urls)
4. [Download archived raw SERPs](#4-archived-raw-serps)
5. [Parse archived SERPs](#5-archived-parsed-serps)
6. [Download archived raw search results](#6-archived-raw-search-results)
7. [Parse archived search results](#7-archived-parsed-search-results)
8. [Construct IR corpus](#8-ir-corpus)

### TL;DR

Let's start with a small example and construct a query log for the [ChatNoir](https://chatnoir.eu) search engine:

1. `python -m web_archive_query_log make archived-urls chatnoir`
2. `python -m web_archive_query_log make archived-query-urls chatnoir`
3. `python -m web_archive_query_log make archived-raw-serps chatnoir`
4. `python -m web_archive_query_log make archived-parsed-serps chatnoir`
5. `python -m web_archive_query_log make archived-raw-search-results chatnoir`
6. `python -m web_archive_query_log make archived-parsed-search-results chatnoir`
7. `python -m web_archive_query_log make ir-corpus chatnoir`

Got the idea? Now you're ready to scrape your own query logs!
To scale things up and understand the data, just keep on reading.
For more details on how to add more services, see [below](#contribute).

### 1. Selected Services

Manually or semi-automatically collect a list of services that you would like to scrape query logs from.

The list of services should be stored in a single [YAML][yaml-spec] file
at [`data/selected-services.yaml`](data/selected-services.yaml) and contains one entry per service, like shown below:

```yaml
- name: string               # service name (alexa_domain - alexa_public_suffix)
  public_suffix: string      # public suffix (https://publicsuffix.org/) of alexa_domain
  alexa_domain: string       # domain as it appears in Alexa top-1M ranks
  alexa_rank: int            # rank from fused Alexa top-1M rankings
  category: string           # manual annotation
  notes: string              # manual annotation
  input_field: bool          # manual annotation
  search_form: bool          # manual annotation
  search_div: bool           # manual annotation
  domains: # known domains of service (including the main domain)
    - string
    - string
    - ...
  query_parsers: # query parsers in order of precedence
    - pattern: regex
      type: query_parameter    # for URLs like https://example.com/search?q=foo
      parameter: string
    - pattern: regex
      type: fragment_parameter # for URLs like https://example.com/search#q=foo
      parameter: string
    - pattern: regex
      type: query_parameter    # for URLs like https://example.com/search/foo
      path_prefix: string
    - ...
  page_parsers: # page number parsers in order of precedence
    - pattern: regex
      type: query_parameter    # for URLs like https://example.com/search?page=2
      parameter: string
    - ...
  offset_parsers: # page offset parsers in order of precedence
    - pattern: regex
      type: query_parameter    # for URLs like https://example.com/search?start=11
      parameter: string
    - ...
  interpreted_query_parsers: # interpreted query parsers in order of precedence
    - ...
  results_parsers: # search result and snippet parsers in order of precedence
    - ...
- ...
```

In the source code, a selected service corresponds
to the Python class [`SelectedService`](web_archive_query_log/model/__init__.py).

### 2. Archived URLs

Fetch all archived URLs for a service from the Internet Archive's Wayback Machine.

You can run this step with the following command line, where `<SERVICENAME>` is the name of the service
you want to fetch archived URLs from:

```shell:
python -m web_archive_query_log make archived-urls <SERVICENAME>
```

This will create multiple files in the `archived-urls` subdirectory
under the [data directory](#pro-tip--specify-a-custom-data-directory),
based on the service name (`<SERVICENAME>`), domain (`<DOMAIN>`),
and the Wayback Machine's CDX [page number][cdx-pagination] (`<CDXPAGE>`)
from which the URLs were originally fetched:

```
<DATADIR>/archived-urls/<SERVICENAME>/<DOMAIN>/<CDXPAGE>.jsonl.gz
```

Here, the `<CDXPAGE>` is a 10-digit number with leading zeros, e.g., `0000000001`.

Each individual file is a GZIP-compressed [JSONL][jsonl-spec] file
with one archived URL per line, in arbitrary order.
Each line contains the following fields:

```json
{
  "url": "string",
  // archived URL
  "timestamp": "int"
  // archive timestamp as POSIX integer
}
```

In the source code, an archived URL corresponds
to the Python class [`ArchivedUrl`](web_archive_query_log/model/__init__.py).

### 3. Archived Query URLs

Parse and filter archived URLs that contain a query and may point to a search engine result page (SERP).

You can run this step with the following command line, where `<SERVICENAME>` is the name of the service
you want to parse query URLs from:

```shell:
python -m web_archive_query_log make archived-query-urls <SERVICENAME>
```

This will create multiple files in the `archived-query-urls` subdirectory
under the [data directory](#pro-tip--specify-a-custom-data-directory),
based on the service name (`<SERVICENAME>`), domain (`<DOMAIN>`),
and the Wayback Machine's CDX [page number][cdx-pagination] (`<CDXPAGE>`)
from which the URLs were originally fetched:

```
<DATADIR>/archived-query-urls/<SERVICENAME>/<DOMAIN>/<CDXPAGE>.jsonl.gz
```

Here, the `<CDXPAGE>` is a 10-digit number with leading zeros, e.g., `0000000001`.

Each individual file is a GZIP-compressed [JSONL][jsonl-spec] file
with one archived query URL per line, in arbitrary order.
Each line contains the following fields:

```json
{
  "url": "string",
  // archived URL
  "timestamp": "int",
  // archive timestamp as POSIX integer
  "query": "string",
  // parsed query
  "page": "int",
  // result page number (optional)
  "offset": "int"
  // result page offset (optional)
}
```

In the source code, an archived query URL corresponds
to the Python class [`ArchivedQueryUrl`](web_archive_query_log/model/__init__.py).

### 4. Archived Raw SERPs

Download the raw HTML content of archived search engine result pages (SERPs).

You can run this step with the following command line, where `<SERVICENAME>` is the name of the service
you want to download raw SERP HTML contents from:

```shell:
python -m web_archive_query_log make archived-raw-serps <SERVICENAME>
```

This will create multiple files in the `archived-urls` subdirectory
under the [data directory](#pro-tip--specify-a-custom-data-directory),
based on the service name (`<SERVICENAME>`), domain (`<DOMAIN>`),
and the Wayback Machine's CDX [page number][cdx-pagination] (`<CDXPAGE>`)
from which the URLs were originally fetched.
Archived raw SERPs are stored as 1GB-sized WARC chunk files, that is, WARC chunks are "filled" sequentially
up to a size of 1GB each. If a chunk is full, a new chunk is created.

```
<DATADIR>/archived-raw-serps/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/<WARCCHUNK>.jsonl.gz
```

Here, the `<CDXPAGE>` and `<WARCCHUNK>` are both 10-digit numbers with leading zeros, e.g., `0000000001`.

Each individual file is a GZIP-compressed [WARC][warc-spec] file
with one WARC request and one WARC response per archived raw SERP.
WARC records are arbitrarily ordered within or across chunks, but the WARC request and response
for the same archived query URL are kept together.
The archived query URL is stored in the WARC request's and response's `Archived-URL` field
in [JSONL][jsonl-spec] format (the same format as in the previous step):

```json
{
  "url": "string",
  // archived URL
  "timestamp": "int",
  // archive timestamp as POSIX integer
  "query": "string",
  // parsed query
  "page": "int",
  // result page number (optional)
  "offset": "int"
  // result page offset (optional)
}
```

In the source code, an archived raw SERP corresponds
to the Python class [`ArchivedRawSerp`](web_archive_query_log/model/__init__.py).

### 5. Archived Parsed SERPs

Parse and filter archived SERPs from raw contents.

You can run this step with the following command line, where `<SERVICENAME>` is the name of the service
you want to parse SERPs from:

```shell:
python -m web_archive_query_log make archived-parsed-serps <SERVICENAME>
```

This will create multiple files in the `archived-serps` subdirectory
under the [data directory](#pro-tip--specify-a-custom-data-directory),
based on the service name (`<SERVICENAME>`), domain (`<DOMAIN>`),
and the Wayback Machine's CDX [page number][cdx-pagination] (`<CDXPAGE>`)
from which the URLs were originally fetched:

```
<DATADIR>/archived-serps/<SERVICENAME>/<DOMAIN>/<CDXPAGE>.jsonl.gz
```

Here, the `<CDXPAGE>` is a 10-digit number with leading zeros, e.g., `0000000001`.

Each individual file is a GZIP-compressed [JSONL][jsonl-spec] file
with one archived parsed SERP per line, in arbitrary order.
Each line contains the following fields:

```json
{
  "url": "string",
  // archived URL
  "timestamp": "int",
  // archive timestamp as POSIX integer
  "query": "string",
  // parsed query
  "page": "int",
  // result page number (optional)
  "offset": "int",
  // result page offset (optional)
  "interpreted_query": "string",
  // query displayed on the SERP (e.g. with spelling correction; optional)
  "results": [
    {
      "url": "string",
      // URL of the result
      "title": "string",
      // title of the result
      "snippet": "string"
      // snippet of the result (highlighting normalized to <em>)
    },
    ...
  ]
}
```

In the source code, an archived parsed SERP corresponds
to the Python class [`ArchivedParsedSerp`](web_archive_query_log/model/__init__.py).

### 6. Archived Raw Search Results

Download the raw HTML content of archived search engine results.

You can run this step with the following command line, where `<SERVICENAME>` is the name of the service
you want to download search results from:

```shell:
python -m web_archive_query_log make archived-raw-search-results <SERVICENAME>
```

**TODO**

In the source code, an archived raw search result corresponds
to the Python class [`ArchivedRawSearchResult`](web_archive_query_log/model/__init__.py).

### 7. Archived Parsed Search Results

Parse the main content from archived raw search engine results.

You can run this step with the following command line, where `<SERVICENAME>` is the name of the service
you want to parse search results from:

```shell:
python -m web_archive_query_log make archived-parsed-search-results <SERVICENAME>
```

**TODO**

In the source code, an archived parsed search result corresponds
to the Python class [`ArchivedParsedSearchResult`](web_archive_query_log/model/__init__.py).

### 8. IR Corpus

Construct an information retrieval corpus of the query log, qrels derived from the SERP ranking,
and downloaded search result documents, in standard TREC formats.

**TODO**

### Pro Tip: Specify a Custom Data Directory

By default, the data directory is set to [`data/`](data).
You can change this with the `--data-directory` option, e.g.:

```bash

```shell
python -m web_archive_query_log make archived-urls --data-directory /mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/
```

### Pro Tip: Limit Scraping for Testing

If the service you're scraping queries for is very large and has many domains,
testing your settings on a smaller sample from that service can be helpful.
You can specify a single domain to scrape from like this:

```shell
python -m web_archive_query_log make archived-urls SERVICENAME DOMAIN
```

If a domain is very popular and therefore has many archived URLs,
you can further limit the number of archived URLs to scrape by selecting
a [page](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api)
from the Wayback Machine's
[CDX API](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api):

```shell
python -m web_archive_query_log make archived-urls SERVICENAME DOMAIN CDX_PAGE
```

## Contribute

If you've found an important service to be missing from this query log,
please suggest it by creating an [issue][repo-issues].
We also very gratefully accept [pull requests][repo-prs]
for adding [service definitions](#1-selected-services) or new parsers!

If you're unsure about anything, post an [issue][repo-issues], or [contact us](mailto:jan.reimer@student.uni-halle.de).


[repo-issues]: https://git.webis.de/code-research/web-search/web-archive-query-log/-/issues

[repo-prs]: https://git.webis.de/code-research/web-search/web-archive-query-log/-/merge_requests

[cdx-pagination]: https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api

[warc-spec]: https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/

[jsonl-spec]: https://jsonlines.org/

[yaml-spec]: https://yaml.org/