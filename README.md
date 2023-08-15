[![Paper DOI](https://img.shields.io/badge/DOI-10.1145%2F3539618.3591890-blue?style=flat-square)](https://doi.org/10.1145/3539618.3591890)
[![arXiv preprint](https://img.shields.io/badge/arXiv-2304.00413-blue?style=flat-square)](https://arxiv.org/abs/2304.00413)
[![Papers with Code](https://img.shields.io/badge/papers%20with%20code-AQL--22-blue?style=flat-square)](https://paperswithcode.com/paper/the-archive-query-log-mining-millions-of)  
[![CI status](https://img.shields.io/github/actions/workflow/status/webis-de/archive-query-log/ci.yml?branch=main&style=flat-square)](https://github.com/webis-de/archive-query-log/actions/workflows/ci.yml)
[![Code coverage](https://img.shields.io/codecov/c/github/webis-de/archive-query-log?style=flat-square)](https://codecov.io/github/webis-de/archive-query-log/)
[![Maintenance](https://img.shields.io/maintenance/yes/2023?style=flat-square)](https://github.com/webis-de/archive-query-log/graphs/contributors)  
[![Issues](https://img.shields.io/github/issues/webis-de/archive-query-log?style=flat-square)](https://github.com/webis-de/archive-query-log/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/webis-de/archive-query-log?style=flat-square)](https://github.com/webis-de/archive-query-log/pulls)
[![Commit activity](https://img.shields.io/github/commit-activity/m/webis-de/archive-query-log?style=flat-square)](https://github.com/webis-de/archive-query-log/commits)
[![License](https://img.shields.io/github/license/webis-de/archive-query-log?style=flat-square)](LICENSE)

# 📜 The Archive Query Log

Mining Millions of Search Result Pages of Hundreds of Search Engines from 25&nbsp;Years of Web Archives.

[![Queries TSNE](docs/queries-tsne-teaser.png)](docs/queries-tsne.png)

Start now by running [your custom analysis/experiment](#integrations), scraping [your own query log](#tldr), or just look at [our example files](data/examples).

## Contents

- [Integrations](#integrations)
- [Installation](#installation)
- [Usage](#tldr)
- [Development](#development)
- [Contribute](#contribute)
- [Abstract](#abstract)

## Integrations

### Running Experiments on the AQL

The data in the Archive Query Log is highly sensitive (still, you can [re-crawl everything from the Wayback Machine](#usage)). For that reason, we ensure that custom experiments or analyises can not leak sensitive data (please [get in touch](#contribute) if you have questions) by using [TIRA](https://tira.io) as a platform for custom analyses/experiments. In TIRA, you submit a Docker image that implements your experiment. Your software is then executed in sandboxed mode (without internet connection) to ensure that your software does not leak sensitive information. After your software execution finished, administrators will review your submission and unblind it so that you can access the outputs.  
Please refer to our [dedicated TIRA tutorial](integrations/tira/) as starting point for your experiments.

## Installation

1. Install [Python 3.10](https://python.org/downloads/)
2. Create and activate virtual environment:
    ```shell
    python3.10 -m venv venv/
    source venv/bin/activate
    ```
4. Install dependencies:
    ```shell
    pip install -e .
    ```

## Usage

### Docker

1. Build the Docker image:
    ```shell
    docker build -t aql .
    ```
2. Run the Docker image:
    ```shell
    docker run -it --rm -v "$(pwd)"/config.override.yml:/workspace/config.override.yml aql
    ```


## Citation

If you use the Archive Query Log dataset or the code to generate it in your research, please cite the following paper describing the AQL and its use-cases:

> Heinrich Reimer, Sebastian Schmidt, Maik Fröbe, Lukas Gienapp, Harrisen Scells, Benno Stein, Matthias Hagen, and Martin Potthast. [The Archive Query Log: Mining Millions of Search Result Pages of Hundreds of Search Engines from 25 Years of Web Archives.](https://webis.de/publications.html?q=archive#reimer_2023) In Hsin-Hsi Chen et al., editors, _46th International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR 2023)_, pages 2848–2860, July 2023. ACM.

You can use the following BibTeX entry for citation:

```bibtex
@InProceedings{reimer:2023,
   author =                   {{Jan Heinrich} Reimer and Sebastian Schmidt and Maik Fr{\"o}be and Lukas Gienapp and Harrisen Scells and Benno Stein and Matthias Hagen and Martin Potthast},
   booktitle =                {46th International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR 2023)},
   doi =                      {10.1145/3539618.3591890},
   editor =                   {Hsin{-}Hsi Chen and Wei{-}Jou (Edward) Duh and Hen{-}Hsen Huang and Makoto P. Kato and Josiane Mothe and Barbara Poblete},
   ids =                      {potthast:2023u},
   isbn =                     {9781450394086},
   month =                    jul,
   numpages =                 13,
   pages =                    {2848--2860},
   publisher =                {ACM},
   site =                     {Taipei, Taiwan},
   title =                    {{The Archive Query Log: Mining Millions of Search Result Pages of Hundreds of Search Engines from 25 Years of Web Archives}},
   url =                      {https://dl.acm.org/doi/10.1145/3539618.3591890},
   year =                     2023
}
```

## Development

Run tests:
```shell
flake8 archive_query_log
pylint -E archive_query_log
pytest archive_query_log
```

Add new tests for parsers:

1. Select the number of tests to run per service and the number of services.
2. Auto-generate unit tests and download WARCs with [generate_tests.py](archive_query_log/results/test/generate_tests.py)
3. Run the tests.
4. Failing tests will open a diff editor with the approval and a web browser tab with the Wayback URL.
5. Use the web browser dev tools to find the query input field and search result CSS paths.
6. Close diffs and tabs and re-run tests.

## Contribute

If you've found an important search provider to be missing from this query log, please suggest it by creating an [issue][repo-issues]. We also very gratefully accept [pull requests][repo-prs] for adding [search providers](#1-search-providers) or new parser configurations!

If you're unsure about anything, post an [issue][repo-issues], or contact us:
- [heinrich.reimer@uni-jena.de](mailto:heinrich.reimer@uni-jena.de)
- [s.schmidt@uni-leipzig.de](mailto:s.schmidt@uni-leipzig.de)
- [maik.froebe@uni-jena.de](mailto:maik.froebe@uni-jena.de)
- [lukas.gienapp@uni-leipzig.de](mailto:lukas.gienapp@uni-leipzig.de)
- [harry.scells@uni-leipzig.de](mailto:harry.scells@uni-leipzig.de)
- [benno.stein@uni-weimar.de](mailto:benno.stein@uni-weimar.de)
- [matthias.hagen@uni-jena.de](mailto:matthias.hagen@uni-jena.de)
- [martin.potthast@uni-leipzig.de](mailto:martin.potthast@uni-leipzig.de)

We're happy to help!

## License

This repository is released under the [MIT license](LICENSE). Files in the `data/` directory are exempt from this license.
If you use the AQL in your research, we'd be glad if you'd [cite us](#citation).

## Abstract

The Archive Query Log (AQL) is a previously unused, comprehensive query log collected at the Internet Archive over the last 25 years. Its first version includes 356 million queries, 166 million search result pages, and 1.7 billion search results across 550 search providers. Although many query logs have been studied in the literature, the search providers that own them generally do not publish their logs to protect user privacy and vital business data. Of the few query logs publicly available, none combines size, scope, and diversity. The AQL is the first to do so, enabling research on new retrieval models and (diachronic) search engine analyses. Provided in a privacy-preserving manner, it promotes open research as well as more transparency and accountability in the search industry.

[repo-issues]: https://git.webis.de/code-research/web-search/web-archive-query-log/-/issues

[repo-prs]: https://git.webis.de/code-research/web-search/web-archive-query-log/-/merge_requests

[cdx-pagination]: https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api

[warc-spec]: https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/

[jsonl-spec]: https://jsonlines.org/

[yaml-spec]: https://yaml.org/
