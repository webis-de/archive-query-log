# 📜 Web Archive Query and Search Logs

Scrape real-life query logs from archived search engine result pages (SERPs) on the Internet Archive.

## Contents

- [Installation](#installation)
- [Usage](#usage)
- [Architecture and Formats](#architecture-and-formats)
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

1. Collect services. (#1-service-collection)
2. Collect service domains. (#2-service-domains)
3. Collect archived service URLs. (#3-service-urls)  
   `python -m web_archive_query_log service archived-urls SERVICENAME [DOMAIN [CDX_PAGE]]`
4. Filter archived service URLs and identify URLs with query data. (#4-service-urls)
5. Parse queries and SERP URLs from service URLs. (#5-url-query-extraction)  
   `python -m web_archive_query_log service archived-serp-urls SERVICENAME [DOMAIN [CDX_PAGE]]`
6. Download archived SERP contents. (#6-serps-download)  
   `python -m web_archive_query_log service archived-serp-contents SERVICENAME [DOMAIN [CDX_PAGE]]`
7. Parse downloaded SERPs. (#7-serps-parsing)  
   `python -m web_archive_query_log service archived-serps SERVICENAME [DOMAIN [CDX_PAGE]]` (not fully implemented)
8. Download archived documents linked from SERPs, if available. (#8-results-download)
   `python -m web_archive_query_log service archived-serp-results-contents SERVICENAME [DOMAIN [CDX_PAGE]]` (not yet implemented)
9. Build IR test collection. (#9-corpus construction)

## Architecture and Formats

The intermediate results from each step are stored in different formats.

### 1 Archived Services

- all services are stored in a single YAML file:
  [`data/services.yaml`](data/services.yaml)
- one object per service, array containing all services
  - YAML format:
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
       domains:                   # known domains of service (including the main domain)
       - string
       - string
       - ...
       query_parsers:             # query parsers in order of precedence
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
       page_parsers:              # page number parsers in order of precedence
       - pattern: regex
         type: query_parameter    # for URLs like https://example.com/search?page=2
         parameter: string
       - ...
       offset_parsers:            # page offset parsers in order of precedence
       - pattern: regex
         type: query_parameter    # for URLs like https://example.com/search?start=11
         parameter: string
       - ...
       interpreted_query_parsers: # interpreted query parsers in order of precedence
       - ...
       results_parsers:           # search result and snippet parsers in order of precedence
       - ...
     - ...
     ```
- Python data class: `Service`

### 2 Archived Serice Domains

### 3 Archived Service URLs

- archived URLs are stored in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-urls.jsonl.gz`
  - `<DATADIR>`: main data directory (e.g., `/mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/`)
  - `<SERVICENAME>`: name of the service
  - `<DOMAIN>`: one of the domains of the service
  - `<CDXPAGE>`: page number of the [CDX API](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api) from which the URLs were originally fetched (10-digit number with leading zeros, e.g., `0000000001`)
- one line per archived URL
- lines are not ordered within one CDX page file path
- JSONL format:
   ```json
   {
     "url": "string",   // archived URL
     "timestamp": "int" // archive timestamp as POSIX integer
   }
   ```
- Python data class: `ArchivedUrl`

### 3 Archived Query URLs

- archived SERP URLs are stored in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-serp-urls.jsonl.gz`
  - `<DATADIR>`: main data directory (e.g., `/mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/`)
  - `<SERVICENAME>`: name of the service
  - `<DOMAIN>`: one of the domains of the service
  - `<CDXPAGE>`: page number of the [CDX API](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api) from which the URLs were originally fetched (10-digit number with leading zeros, e.g., `0000000001`)
- one line per archived URL
- lines are not ordered within one CDX page file path
- JSONL format:
   ```json
   {
     "url": "string",    // archived URL
     "timestamp": "int", // archive timestamp as POSIX integer
     "query": "string",  // parsed query
     "page": "int",      // result page number (optional)
     "offset": "int"     // result page offset (optional)
   }
   ```
- Python data class: `ArchivedSerpUrl`

### 4 Archived Queries

### 5 Archived Raw SERPs

- archived SERP contents are stored as 1GB-sized WARC chunk files in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-serp-contents/<WARCCHUNK>.warc.gz`
  - `<DATADIR>`: main data directory (e.g., `/mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/`)
  - `<SERVICENAME>`: name of the service
  - `<DOMAIN>`: one of the domains of the service
  - `<CDXPAGE>`: page number of the [CDX API](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api) from which the URLs were originally fetched (10-digit number with leading zeros, e.g., `0000000001`)
  - `<WARCCHUNK>`: chunk number of WARC chunk files (10-digit number with leading zeros, e.g., `0000000001`; WARCs are "filled" sequentially, i.e., the first `0000000001`)
- one WARC request and one WARC response per archived URL
- WARC records are not ordered within and across chunks, but WARC request and response are kept together
- additional WARC header `Archived-URL` (for request and response) with the archived URL in JSONL format:
   ```json
   {
     "url": "string",    // archived URL
     "timestamp": "int", // archive timestamp as POSIX integer
     "query": "string",  // parsed query
     "page": "int",      // result page number (optional)
     "offset": "int"     // result page offset (optional)
   }
   ```
  (same format as in previous step)
- Python data class: `ArchivedSerpContent` (roughly)

### 7 Archived Parsed SERPs

- archived SERPs are stored in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-serp.jsonl.gz`
  - `<DATADIR>`: main data directory (e.g., `/mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/`)
  - `<SERVICENAME>`: name of the service
  - `<DOMAIN>`: one of the domains of the service
  - `<CDXPAGE>`: page number of the [CDX API](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api) from which the URLs were originally fetched (10-digit number with leading zeros, e.g., `0000000001`)
- one line per search engine result page (SERP)
- lines are not ordered within one CDX page file path
- JSONL format:
   ```json
   {
     "url": "string",               // archived URL
     "timestamp": "int",            // archive timestamp as POSIX integer
     "query": "string",             // parsed query
     "page": "int",                 // result page number (optional)
     "offset": "int",               // result page offset (optional)
     "interpreted_query": "string", // query displayed on the SERP (e.g. with spelling correction; optional)
     "results": [
       {
         "url": "string",           // URL of the result
         "title": "string",         // title of the result
         "snippet": "string"        // snippet of the result (highlighting normalized to <em>)
       },
       ...
     ]
   }
   ```
- Python data class: `ArchivedSerp` with `SearchResult`

### 8 Archived Raw Search Results

### 9 Archived Parsed Search Results

**TODO**

### 10 Archived Web Search Corpus

**TODO**

## Contribute

If you've found a search engine to be missing from this query log, please **TODO**.
We gratefully accept [issues](https://git.webis.de/code-research/web-search/internet-archive-query-log/-/issues) and [pull requests](https://git.webis.de/code-research/web-search/internet-archive-query-log/-/merge_requests)!
If you're unsure about anything, post an [issue](https://git.webis.de/code-research/web-search/internet-archive-query-log/-/issues), or [contact us](mailto:jan.reimer@student.uni-halle.de).


