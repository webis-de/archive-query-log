[![Paper DOI](https://img.shields.io/badge/DOI-10.1145%2F3539618.3591890-blue?style=flat-square)](https://doi.org/10.1145/3539618.3591890)
[![arXiv preprint](https://img.shields.io/badge/arXiv-2304.00413-blue?style=flat-square)](https://arxiv.org/abs/2304.00413)
[![Papers with Code](https://img.shields.io/badge/papers%20with%20code-AQL--22-blue?style=flat-square)](https://paperswithcode.com/paper/the-archive-query-log-mining-millions-of) \
[![PyPi](https://img.shields.io/pypi/v/archive-query-log?style=flat-square)](https://pypi.org/project/archive-query-log/)
[![Python](https://img.shields.io/pypi/pyversions/archive-query-log?style=flat-square)](https://pypi.org/project/archive-query-log/)
[![Downloads](https://img.shields.io/pypi/dm/archive-query-log?style=flat-square)](https://pypi.org/project/archive-query-log/) \
[![CI status](https://img.shields.io/github/actions/workflow/status/webis-de/archive-query-log/ci.yml?branch=main&style=flat-square)](https://github.com/webis-de/archive-query-log/actions/workflows/ci.yml)
[![Code coverage](https://img.shields.io/codecov/c/github/webis-de/archive-query-log?style=flat-square)](https://codecov.io/github/webis-de/archive-query-log/)
[![Maintenance](https://img.shields.io/maintenance/yes/2025?style=flat-square)](https://github.com/webis-de/archive-query-log/graphs/contributors) \
[![Issues](https://img.shields.io/github/issues/webis-de/archive-query-log?style=flat-square)](https://github.com/webis-de/archive-query-log/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/webis-de/archive-query-log?style=flat-square)](https://github.com/webis-de/archive-query-log/pulls)
[![Commit activity](https://img.shields.io/github/commit-activity/m/webis-de/archive-query-log?style=flat-square)](https://github.com/webis-de/archive-query-log/commits)
[![License](https://img.shields.io/github/license/webis-de/archive-query-log?style=flat-square)](LICENSE)
<!-- TODO: Add GitHub Docker badges when <https://github.com/badges/shields/issues/5594> is resolved. -->

# 📜 The Archive Query Log

Mining Millions of Search Result Pages of Hundreds of Search Engines from 25&nbsp;Years of Web Archives.

[![Queries t-SNE](docs/queries-tsne-teaser.png)](docs/queries-tsne.png)

Start now by running [your custom analysis/experiment](#integrations), scraping [your query log](#crawling), or looking at [our example files](data/examples).

## Contents

- [Integrations](#integrations)
- [Crawling](#crawling)
- [Development](#development)
- [Third-party Resources](#third-party-resources)
- [Contribute](#contribute)
- [Abstract](#abstract)

## Integrations

### Running experiments on the AQL

The data in the Archive Query Log is highly sensitive (still, you can [re-crawl everything from the Wayback Machine](#crawling)). For that reason, we ensure that custom experiments or analyses can not leak sensitive data (please [get in touch](#contribute) if you have questions) by using [TIRA](https://tira.io) as a platform for custom analyses/experiments. In TIRA, you submit a Docker image that implements your experiment. Your software is then executed in sandboxed mode (without an internet connection) to ensure that your software does not leak sensitive information. After your software execution is finished, administrators will review your submission and unblind it so that you can access the outputs.  
Please refer to our [dedicated TIRA tutorial](integrations/tira/README.md) as the starting point for your experiments.

## Crawling

For running the CLI and crawl a query log on your own machine, please refer to the [instructions for single-machine deployments](#single-machine-pypidocker).
If instead you want to scale up and run the crawling pipelines on a cluster, please refer to the [instructions for cluster deployments](#cluster-helmkubernetes).

### Single-machine (PyPi/Docker)

To run the Archive Query Log CLI on your machine, you can either use our [PyPi package](#installation-pypi) or the [Docker image](#installation-docker).
(If you absolutely need to, you can also install the [Python CLI](#installation-python-from-source) or the Docker image from source.)

#### Installation (PyPi)

First you need to install [Python 3.13](https://python.org/downloads/) and [pipx](https://pypa.github.io/pipx/installation/) (this allows you to install the AQL CLI in a virtual environment). Then, you can install the Archive Query Log CLI by running:

```shell
pipx install archive-query-log
```

Now you can run the Archive Query Log CLI by running:

```shell
aql --help
```

#### Installation (Python from source)

<details>

First, install [Python 3.13](https://python.org/downloads/) and then clone this repository. From inside the repository directory, create a virtual environment and activate it:

```shell
python3.13 -m venv venv/
source venv/bin/activate
```

Install the Archive Query Log by running:

```shell
pip install -e .
```

Now you can run the Archive Query Log CLI by running:

```shell
aql --help
```

</details>

#### Installation (Docker)

You only need to install [Docker](https://docs.docker.com/get-docker/).

**Note:** The commands below use the syntax of the [PyPi installation](#installation-pypi). To run the same commands with the Docker installation, replace `aql` with `docker run -it -v "$(pwd)"/config.override.yml:/workspace/config.override.yml ghcr.io/webis-de/archive-query-log`, for example:

```shell
docker run -it -v "$(pwd)"/config.override.yml:/workspace/config.override.yml ghcr.io/webis-de/archive-query-log --help
```

#### Installation (Docker from source)

<details>

First, install [Docker](https://docs.docker.com/get-docker/) and clone this repository. From inside the repository directory, build the Docker image like this:

```shell
docker build -t aql .
```

**Note:** The commands below use the syntax of the [PyPi installation](#installation-pypi). To run the same commands with the Docker installation, replace `aql` with `docker run -it -v "$(pwd)"/config.override.yml:/workspace/config.override.yml aql`, for example:

```shell
docker run -it -v "$(pwd)"/config.override.yml:/workspace/config.override.yml aql --help
```

</details>

#### Configuration

Crawling the Archive Query Log requires access to an Elasticsearch cluster and some S3 block storage. To configure access to the Elasticsearch cluster and S3, add a `config.override.yml` file in the current directory with the following contents. Replace the placeholders with your actual credentials:

```yaml
es:
  host: "<HOST>"
  port: 9200
  username: "<USERNAME>"
  password: "<PASSWORD>"
s3:
   endpoint_url: "<URL>"
   bucket_name: archive-query-log
   access_key: "<KEY>"
   secret_key: "<KEY>"
```

#### Toy example: Crawl ChatNoir SERPs from the Wayback Machine

The crawling pipeline of the Archive Query Log can best be understood by looking at a small toy example. Here, we want to crawl and parse SERPs of the [ChatNoir search engine](https://chatnoir.eu) from the [Wayback Machine](https://web.archive.org).

> TODO: Add example instructions.

#### Add an archive service

Add new web archive services (e.g., the [Wayback Machine](https://web.archive.org)) to the AQL by running:

```shell
aql archives add
```

We maintain a list of compatible web archives [below](#compatible-archives).

##### Compatible archives

Below, we provide a curated list of web archives.
In this list, archives that have both a CDX API and a Memento API are compatible with the Archive Query Log crawler and can be used to mine SERPs.

| Name | CDX API | Memento API | Size | Funding | Notes | AQL |
|:--|:--|:--|:-:|:--|:--|:--|
| [Wayback Machine](https://web.archive.org/) | [🟩](https://web.archive.org/cdx/search/cdx) | [🟩](https://web.archive.org/web) | [928B](https://web.archive.org/) | [non-profit](https://archive.org/donate) | - | 🟩 |
| [Arquivo.pt](https://arquivo.pt/) | [🟩](https://arquivo.pt/wayback/cdx) | [🟩](https://arquivo.pt/wayback) | [47M](https://sobre.arquivo.pt/en/about/press/the-portuguese-web-archive-in-numbers/) | government | [Focus on Portugese websites](https://arquivo.pt/numeros/#5-top-domains-available-in-arquivo-pt) | 🟩 |
| [Estonian Web Archives](https://veebiarhiiv.digar.ee/a/20191008165439mp_/http://veebiarhiiv.digar.ee/) | [🟩](https://veebiarhiiv.digar.ee/a/cdx) | [🟩](https://veebiarhiiv.digar.ee/a) | [75k](https://veebiarhiiv.digar.ee/a/20191008165439/http://www.nlib.ee/veebisaidid) | government | Only `.ee`-domains and hand-picked Estonian websites of other TLDs | 🟩 |
| [Estonian Web Archives](https://veebiarhiiv.digar.ee/a/20191008165439mp_/http://veebiarhiiv.digar.ee/) | [🟩](https://veebiarhiiv.digar.ee/a/cdx) | [🟩](https://veebiarhiiv.digar.ee/a) | [75k](https://veebiarhiiv.digar.ee/a/20191008165439/http://www.nlib.ee/veebisaidid) | government | Only `.ee`-domains and hand-picked Estonian websites of other TLDs | 🟩 |
| [Icelandic Web Archive](https://vefsafn.is/) | [🟩](https://vefsafn.is/is/cdx) | [🟩](https://vefsafn.is/is) | - | government | Only `.is`-domains and hand-picked Icelandic websites of other TLDs | 🟩 |
| [Stanford Web Archive](https://swap.stanford.edu/) | [🟩](https://swap.stanford.edu/was/cdx) | [🟩](https://swap.stanford.edu/was) | - | university | Websites selected by subject specialists | 🟩 |
| [Australian Web Archive](https://webarchive.nla.gov.au/) | [🟩](https://web.archive.org.au/awa/cdx) | [🟩](https://web.archive.org.au/awa) | [8B](https://trove.nla.gov.au/help/categories/websites-category) | government | Mostly `.au`-domains and other Australia-related websites | 🔜 |
| [New Zealand Web Archive](https://natlib.govt.nz/collections/a-z/new-zealand-web-archive) | [🟩](https://ndhadeliver.natlib.govt.nz/webarchive/cdx) | [🟩](https://ndhadeliver.natlib.govt.nz/webarchive) | [47k](https://natlib.govt.nz/collections/a-z/new-zealand-web-archive) | government | Websites about New Zealand and the Pacific | 🔜 |
| [MNMKK OSZK Webarchívum](https://webarchivum.oszk.hu/) | [🟩](http://webadmin.oszk.hu/pywb/cdx) | [🟩](http://webadmin.oszk.hu/pywb) | - | government | Focus on Hungarian websites | 🔜 |
| [UK Web Archive](https://www.webarchive.org.uk/) | [🟨](https://www.webarchive.org.uk/wayback/archive/cdx) | [🟨](https://www.webarchive.org.uk/wayback/archive) | - | government | UK websites | 🟨¹ |
| [archive.today](https://archive.is/) | 🟥 | [🟩](https://archive.is/) | - | private | Also known as archive.is and archive.ph | 🟥 |
| [Perma.cc](https://perma.cc/) | 🟥 | 🟥 | - | university | Maintained by the Harvard Law School Library | 🟥 |

¹ The UK Web Archive is currently unavailable due to a [cyber-attack](https://www.bl.uk/cyber-incident/).

<p><details><summary>Selected archives available as <a href="https://archive-it.org/">Archive-it</a> collections</summary>

- [PRONI Collections](https://archive-it.org/collections/11112/)
- [Harvard Library](https://preservation.library.harvard.edu/web-archives-collections)
- [National Library of Ireland](https://archive-it.org/home/nli)
- [National Central Library of Florence](https://archive-it.org/home/BNCF)
- [Stanford University Archives](https://archive-it.org/organizations/933)
- [Stanford University, Social Sciences Resource Group](https://archive-it.org/organizations/159)
- [California State Library](https://archive-it.org/organizations/898)
- [Ivy Plus Libraries Confederation](https://archive-it.org/home/IvyPlus)
- [University of Texas at San Antonio Libraries Special Collections](https://archive-it.org/organizations/318)
- [Kentucky Department for Libraries and Archives](https://archive-it.org/organizations/386)
- [University of California, San Francisco](https://archive-it.org/organizations/986)
- [Montana State Library](https://archive-it.org/organizations/139)
- [Columbia University Libraries](https://archive-it.org/home/Columbia)
- [North Carolina State Archives and State Library of North Carolina](https://archive-it.org/organizations/67)
- [International Internet Preservation Consortium](https://archive-it.org/home/IIPC)
- [EU Web Archive](https://archive-it.org/home/euwebarchive)

See below on how to [import all public Archive-it archives](#import) automatically.

</details></p>

<p><details><summary>Further archives with unclear status (not yet examined)</summary>

- [Pagefreezer](https://pagefreezer.com/)
- [archive.st](https://archive.st/)
- [FreezePage](https://freezepage.com/)
- [WebCite](https://webcitation.org/)
- [ウェブ魚拓](https://megalodon.jp/)
- [Ina](https://ina.fr/)
- [Web-Archiv des Deutschen Bundestages](https://webarchiv.bundestag.de/cgi/kurz.php)
- [WARP Web Archiving Project](https://warp.da.ndl.go.jp/)
- [Kulturarw3](https://www.kb.se/hitta-och-bestall/hitta-i-samlingarna/kulturarw3.html)
- [Langzeitarchivierung im Bibliotheksverbund Bayern](https://langzeitarchivierung.bib-bvb.de/wayback/)
- [Ghostarchive](https://ghostarchive.org/)
- [Webarchiv Österreich](https://webarchiv.onb.ac.at/)
- [EuropArchive](https://europarchive.org/)
- [Luxembourg Web Archive](https://www.webarchive.lu/)
- [Web Archive Singapore](https://eresources.nlb.gov.sg/webarchives/landing-page)
- [DIR Slovak Internet Archive](https://www.webdepozit.sk/)
- [Spletni Arhiv Narodne](https://arhiv.nuk.uni-lj.si/)
- [The Web Archive of Catalonia](https://padicat.cat/)
- [Web Archive Switzerland](https://www.e-helvetica.nb.admin.ch/)
- [臺灣網站典藏庫](https://webarchive.lib.ntu.edu.tw/)
- [UK Government Web Archive](https://www.nationalarchives.gov.uk/webarchive/)
- [UK Parliament Web Archive](https://webarchive.parliament.uk/)
- [EU Exit Web Archive](https://webarchive.nationalarchives.gov.uk/eu-exit/)
- [End of Term Web Archive](https://eotarchive.org/)
- [Web Archiving Project of the Pacific Islands](https://guides.library.manoa.hawaii.edu/pacificwebarchive)
- [Library of Congress Web Archives](https://www.loc.gov/web-archives/)
- [Национальный цифровой архив России](https://ruarxive.org/)
- [CyberCemetery](https://govinfo.library.unt.edu/)
- [Πύλη Αρχείου Ελληνικού Ιστού](https://webarchive.nlg.gr/)
- [York University Libraries Wayback Machine](https://wayback.library.yorku.ca/)
- [NYARC Web Archive](https://nyarc.org/initiatives/web-archiving)
- [NLM Web Collecting and Archiving](https://www.nlm.nih.gov/webcollecting/index.html)
- [Common Crawl](https://commoncrawl.org/)
- [Webarchiv der Deutschen Nationalbibliothek](https://webarchiv.dnb.de/)
- [Hrvatski Arhiv Weba](https://haw.nsk.hr/)
- [Webarchiv](https://webarchiv.cz/)
- [Netarkivet](https://www.kb.dk/find-materiale/samlinger/netarkivet)
- [Suomalainen Verkkoarkisto](https://verkkoarkisto.kansalliskirjasto.fi/va/)
- [ארכיון האינטרנט הישראלי](https://wayback.nli.org.il/)
- [Scotland Web Archives](https://webarchive.nrscotland.gov.uk/search)

</details></p>

We have last checked Wikipedia's [list of web archiving initiatives](https://en.wikipedia.org/wiki/List_of_Web_archiving_initiatives) and the [Memento Depot](https://mementoweb.org/depot/) on April 3, 2025. If an archive from there is not listed above, it is considered unavailable/broken.

If you know any other web archive service, we would appreciate a [pull request](https://github.com/webis-de/archive-query-log/fork) adding the details to this list.

#### Add a search provider

Add new search providers (e.g., [Google](https://google.com)) to the AQL by running:

```shell
aql providers add
```

A search provider can be any website that offers some search functionality. Ideally, you should also look at common prefixes of the URLs of the search results pages (e.g., `/search` for Google). Narrowing down URL prefixes helps to avoid crawling too many captures that do not contain search results.

Refer to the [import instructions below](#import) to import providers from the AQL-22 YAML file format.

#### Build source pairs

Once you have added at least one [archive](#add-an-archive-service) and one [search provider](#add-a-search-provider), we want to crawl archived captures of SERPs for each search provider and for each archive service. That is, we compute the cross-product of archives and the search providers' domains and URL prefixes (roughly: archive×provider). Start building source pairs (i.e., archive–provider pairs) by running:

```shell
aql sources build
```

Running the command again after adding more archives or providers will automatically create the missing source pairs.

#### Fetch captures

For each [source pair](#build-source-pairs), we now fetch captures from the archive service that corresponds to the provider's domain and URL prefix given in the source pair. Again, rerunning the command after adding more source pairs fetches just the missing captures.

```shell
aql captures fetch
```

#### Parse SERP URLs

Not every capture necessarily points to a search engine result page (SERP). But usually, SERPs contain the user query in the URL, so we can filter out non-SERP captures by parsing the URLs.

```shell
aql serps parse url-query
```

Parsing the query from the capture URL will add SERPs to a new, more focused index that only contains SERPs. From the SERPs, we can also parse the page number and offset of the SERP, if available.

```shell
aql serps parse url-page
aql serps parse url-offset
```

All the above commands can be run in parallel, and they can be run multiple times to update the SERP index. Already parsed SERPs will be skipped.

#### Download SERP WARCs

Up to this point, we have only fetched the metadata of the captures, most prominently the URL. However, the snippets of the SERPs are not contained in the metadata but only on the web page. So, we need to download the actual web pages from the archive service.

```shell
aql serps download warc
```

This command will download the contents of each SERP to a WARC file that is for now stored in the configured cache directory on disk, along with a reference of the SERP. In real-life scenarios, you would probably want to parallelize this step and write to a cache directory that is accessible from any of the workers, because downloads from the Internet Archive and other archives tend to be slow (but the archives can usually handle parallel requests fine).

#### Upload SERP WARCs

The local WARC cache consists of many but small WARC files which is nice for parallel download stability, but not so nice for efficient storage. Hence, in this next step, we pick up WARC records from multiple smaller cache files and upload them to larger but fewer bundles on an S3-compatible block storage:

```shell
aql serps upload warc
```

A pointer to the WARC block in S3 is stored in the SERP index so that we can efficiently access a specific SERP's contents later.

#### Parsing SERP WARCs

From the WARC contents, we can now parse the query as it appears on the SERP (which can sometimes differ from the query encoded in the URL).

```shell
aql serps parse warc-query
```

More importantly, we can parse the snippets of the SERP.

```shell
aql serps parse warc-snippets
```

Parsing the snippets from the SERP's WARC contents will also add the SERP's results to a new index.

<!-- #### Download SERP snippet WARCs

To get the full text of each referenced result from the SERP, we need to download a capture of the result from the web archive. Intuitively, we would like to download a capture of the result at the exact same time as the SERP was captured. But often, web archives crawl the results later or not at all. Therefore, our implementation searches for the nearest captures before and after the SERP's timestamp and downloads these two captures individually for each result, if any capture can be found.

```shell
aql results download warc
```

This command will again download the result's contents to a WARC file that is stored in the configured S3 bucket. A pointer to the WARC file is stored in the result index for random access to the contents of a specific result. -->

### Import

We support automatically importing providers and parsers from the AQL-22 YAML-file format (see [`data/selected-services.yaml`](data/selected-services.yaml)). To import the services and parsers from the AQL-22 YAML file, run the following commands:

```shell
aql providers import
aql parsers url-query import
aql parsers url-page import
aql parsers url-offset import
aql parsers warc-query import
aql parsers warc-snippets import
```

We also support importing a previous crawl of captures from the AQL-22 file system backend:

```shell
aql captures import aql-22
```

Last, we support importing all archives from the [Archive-It](https://archive-it.org/) web archive service:

```shell
aql archives import archive-it
```

### Cluster (Helm/Kubernetes)

Running the Archive Query Log on a cluster is recommended for large-scale crawls. We provide a Helm chart that automatically starts crawling and parsing jobs for you and stores the results in an Elasticsearch cluster.

#### Installation

Just install [Helm](https://helm.sh/docs/intro/quickstart/) and configure `kubectl` for your cluster.

#### Cluster configuration

Crawling the Archive Query Log requires access to an Elasticsearch cluster and some S3 block storage. Configure the Elasticsearch and S3 credentials in a `values.override.yaml` file like this:

```yaml
elasticsearch:
  host: "<HOST>"
  port: 9200
  username: "<USERNAME>"
  password: "<PASSWORD>"
s3:
  endpoint_url: "<URL>"
  bucket_name: archive-query-log
  access_key: "<KEY>"
  secret_key: "<KEY>"
```

#### Deployment

Let us deploy the Helm chart on the cluster (we are testing first with `--dry-run` to see if everything works):

```shell
helm upgrade --install --values ./helm/values.override.yaml --dry-run archive-query-log ./helm
```

If everything works and the output looks good, you can remove the `--dry-run` flag to actually deploy the chart.

#### Uninstall

If you no longer need the chart, you can uninstall it:

```shell
helm uninstall archive-query-log
```

## Citation

If you use the Archive Query Log dataset or the crawling code in your research, please cite the following paper describing the AQL and its use cases:

> Jan Heinrich Reimer, Sebastian Schmidt, Maik Fröbe, Lukas Gienapp, Harrisen Scells, Benno Stein, Matthias Hagen, and Martin Potthast. [The Archive Query Log: Mining Millions of Search Result Pages of Hundreds of Search Engines from 25 Years of Web Archives.](https://webis.de/publications.html?q=archive#reimer_2023) In Hsin-Hsi Chen et al., editors, _46th International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR 2023)_, pages 2848–2860, July 2023. ACM.

You can use the following BibTeX entry for citation:

```bibtex
@InProceedings{reimer:2023,
    author = {Jan Heinrich Reimer and Sebastian Schmidt and Maik Fr{\"o}be and Lukas Gienapp and Harrisen Scells and Benno Stein and Matthias Hagen and Martin Potthast},
    booktitle = {46th International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR 2023)},
    doi = {10.1145/3539618.3591890},
    editor = {Hsin{-}Hsi Chen and Wei{-}Jou (Edward) Duh and Hen{-}Hsen Huang and Makoto P. Kato and Josiane Mothe and Barbara Poblete},
    isbn = {9781450394086},
    month = jul,
    numpages = 13,
    pages = {2848--2860},
    publisher = {ACM},
    site = {Taipei, Taiwan},
    title = {{The Archive Query Log: Mining Millions of Search Result Pages of Hundreds of Search Engines from 25 Years of Web Archives}},
    url = {https://dl.acm.org/doi/10.1145/3539618.3591890},
    year = 2023
}
```

## Development

Refer to the local [Python installation](#installation-python-from-source) instructions to set up the development environment and install the dependencies.

Then, also install the test dependencies:

```shell
pip install -e .[tests]
```

After having implemented a new feature, please check the code format, inspect common LINT errors, and run all unit tests with the following commands:

```shell
ruff check .                         # Code format and LINT
mypy .                         # Static typing
bandit -c pyproject.toml -r .  # Security
pytest .                       # Unit tests
```

### Add new tests for parsers

At the moment, our workflow for adding new tests for parsers goes like this:

1. Select the number of tests to run per service and the number of services.
2. Auto-generate unit tests and download WARCs with [generate_tests.py](archive_query_log/legacy/results/test/generate_tests.py)
3. Run the tests.
4. Failing tests will open a diff editor with the approval and a web browser tab with the Wayback URL.
5. Use the web browser dev tools to find the query input field and the search result CSS paths.
6. Close diffs and tabs and re-run tests.

## Third-party resources

- [Kaggle dataset of the manual test SERPs](https://www.kaggle.com/datasets/federicominutoli/awesome-archive-query-log), thanks to @DiTo97

## Contribute

If you have found an important search provider missing from this query log, please suggest it by creating an [issue](https://github.com/webis-de/archive-query-log/issues). We also gratefully accept [pull requests](https://github.com/webis-de/archive-query-log/pulls) for adding search providers or new parser configurations!

If you are unsure about anything, post an [issue](https://github.com/webis-de/archive-query-log/issues/new) or contact us:

- [heinrich.merker@uni-jena.de](mailto:heinrich.merker@uni-jena.de)
- [sebastian.heineking@uni-leipzig.de](mailto:sebastian.heineking@uni-leipzig.de)
- [maik.froebe@uni-jena.de](mailto:maik.froebe@uni-jena.de)
- [lukas.gienapp@uni-leipzig.de](mailto:lukas.gienapp@uni-leipzig.de)
- [harry.scells@uni-leipzig.de](mailto:harry.scells@uni-leipzig.de)
- [benno.stein@uni-weimar.de](mailto:benno.stein@uni-weimar.de)
- [matthias.hagen@uni-jena.de](mailto:matthias.hagen@uni-jena.de)
- [martin.potthast@uni-kassel.de](mailto:martin.potthast@uni-kassel.de)
- [simon.ruth@uni-kassel.de](mailto:simon.ruth@uni-kassel.de)

We are happy to help!

## License

This repository is released under the [MIT license](LICENSE). Files in the `data/` directory are exempt from this license. If you use the AQL in your research, we would be glad if you could [cite us](#citation).

## Abstract

The Archive Query Log (AQL) is a previously unused, comprehensive query log collected at the Internet Archive over the last 25 years. Its first version includes 356 million queries, 166 million search result pages, and 1.7 billion search results across 550 search providers. Although many query logs have been studied in the literature, the search providers that own them generally do not publish their logs to protect user privacy and vital business data. Of the few query logs publicly available, none combines size, scope, and diversity. The AQL is the first to do so, enabling research on new retrieval models and (diachronic) search engine analyses. Provided in a privacy-preserving manner, it promotes open research as well as more transparency and accountability in the search industry.
