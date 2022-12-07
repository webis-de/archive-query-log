# 📜 internet-archive-query-log

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

1. Collect services.
2. Collect service domains.
3. Collect archived service URLs.  
   `python -m web_archive_query_log service archived-urls SERVICENAME`
4. Filter archived service URLs and identify URLs with query data.
5. Parse queries and SERP URLs from service URLs.  
   `python -m web_archive_query_log service archived-serp-urls SERVICENAME`
6. Download archived SERP contents.  
   `python -m web_archive_query_log service archived-serp-contents SERVICENAME`
7. Parse downloaded SERPs.  
   `python -m web_archive_query_log service archived-serps SERVICENAME` (not yet implemented)
8. Download archived documents linked from SERPs, if available.
9. Build IR test collection.

## Architecture and Formats

The intermediate results from each step are stored in different formats.

### Services

- all services are stored in a single YAML file:
  `<DATADIR>/services.yaml`
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

### Archived URLs

- archived URLs are stored in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-urls.jsonl` (`<CDXPAGE>` is a 10-digit number with leading zeros)
- one line per archived URL
- JSONL format:
   ```json
   {
     "url": "string",   // archived URL
     "timestamp": "int" // archive timestamp as POSIX integer
   }
   ```
- Python data class: `ArchivedUrl`

### Archived SERP URLs

- archived SERP URLs are stored in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-serp-urls.jsonl` (`<CDXPAGE>` is a 10-digit number with leading zeros)
- one line per archived URL
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

### Archived SERP contents

- archived SERP contents are stored in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-serp-contents/` (`<CDXPAGE>` is a 10-digit number with leading zeros)
- contents are stored in 1GB-sized WARC file chunks
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-serp-contents/<CHUNK>.warc.gz` (`<CHUNK>` is a 10-digit number with leading zeros)
- one WARC request and one WARC response per archived URL
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

### Archived SERPs

- archived SERPs are stored in subdirectories based on the service name, domain, and CDX page:
  `<DATADIR>/<SERVICENAME>/<DOMAIN>/<CDXPAGE>/archived-serp.jsonl` (`<CDXPAGE>` is a 10-digit number with leading zeros)
- one line per search engine result page (SERP)
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

### Search result downloads

TODO

### Test Collection

TODO

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
An example can be seen [here](https://git.webis.de/code-research/web-search/web-archive-query-log/-/blob/d6d927248e0c215cffe68d064097a7290ee47de0/internet_archive_query_log/config.py#L193-L200).

## Adding SERP parsers

TBD
