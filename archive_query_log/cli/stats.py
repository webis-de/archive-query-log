from asyncio import run
from gzip import open as gzip_open
from json import loads
from math import inf
from pathlib import Path

from click import option, BOOL, IntRange
from pandas import DataFrame
from tqdm.auto import tqdm

from archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL, LOGGER
from archive_query_log.cli import main
from archive_query_log.cli.util import PathParam
from archive_query_log.config import SERVICES

# See:
# https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api
_URLS_PER_BLOCK = 3000
_BLOCKS_PER_PAGE = 50


def _all_archived_urls(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    from archive_query_log.config import SERVICES
    from archive_query_log.urls.fetch import ArchivedUrlsFetcher, \
        UrlMatchScope
    service_config = SERVICES[service]
    match_scope = UrlMatchScope.PREFIX if focused else UrlMatchScope.DOMAIN
    fetcher = ArchivedUrlsFetcher(
        match_scope=match_scope,
        include_status_codes={200},
        exclude_status_codes=set(),
        include_mime_types={"text/html"},
        exclude_mime_types=set(),
        cdx_api_url=CDX_API_URL,
    )
    if focused:
        if len(service_config.focused_url_prefixes) == 0:
            LOGGER.warning(
                f"No focused URL prefixes configured for service {service}."
            )
    num_pages = run(fetcher.num_service_pages(
        data_directory=data_directory,
        focused=focused,
        service=service_config,
    ))
    return num_pages * _BLOCKS_PER_PAGE * _URLS_PER_BLOCK


@main.command(
    "stats",
    help="Get stats for the most recent exported corpus.",
)
@option(
    "-d", "--data-directory", "--data-directory-path",
    type=PathParam(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH
)
@option(
    "-f", "--focused",
    type=BOOL,
    default=False,
    is_flag=True,
)
@option(
    "--min-rank", "--min-alexa-rank",
    type=IntRange(min=1),
    required=False,
)
@option(
    "--max-rank", "--max-alexa-rank",
    type=IntRange(min=1),
    required=False,
)
@option(
    "-c", "--corpus-directory", "--corpus-directory-path",
    type=PathParam(
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
    required=False,
)
@option(
    "-o", "--output", "--output-path",
    type=PathParam(
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    required=False,
)
def stats_command(
        data_directory: Path,
        focused: bool,
        min_rank: int | None,
        max_rank: int | None,
        corpus_directory: Path | None,
        output: Path | None,
) -> None:
    services = SERVICES.values()
    if min_rank is not None:
        services = (
            service
            for service in services
            if (service.alexa_rank is not None and
                service.alexa_rank >= min_rank)
        )
    if max_rank is not None:
        services = (
            service
            for service in services
            if (service.alexa_rank is not None and
                service.alexa_rank <= max_rank)
        )
    services = sorted(services, key=lambda service: service.alexa_rank or inf)

    results: dict[str, dict[str, int]] = {
        service.name: {
            "all-archived-urls": 0,
            "archived-urls": 0,
            "archived-query-urls": 0,
            "archived-raw-serps": 0,
            "archived-parsed-serps": 0,
            "archived-snippets": 0,
            "archived-raw-search-results": 0,
            "archived-parsed-search-results": 0,
        }
        for service in services
    }

    for service in services:
        results[service.name]["all-archived-urls"] = _all_archived_urls(
            data_directory,
            focused,
            service.name,
        )

    corpus_path: Path
    if corpus_directory is not None:
        corpus_path = corpus_directory
    elif focused:
        corpus_path = data_directory / "focused" / "corpus"
    else:
        corpus_path = data_directory / "corpus"

    if corpus_path.exists():
        queries_paths = sorted(
            corpus_path.glob("queries-*.jsonl.gz"),
            reverse=True,
        )
        documents_paths = sorted(
            corpus_path.glob("documents-*.jsonl.gz"),
            reverse=True,
        )
        if len(queries_paths) > 0 and len(documents_paths) > 0:
            queries_path = queries_paths[0]
            documents_path = documents_paths[0]

            with gzip_open(queries_path, "rt") as queries_file:
                lines = tqdm(
                    queries_file,
                    desc="Read queries corpus"
                )
                for line in lines:
                    query = loads(line)
                    service_name = query["service"]
                    if query["archived_url_location"] is not None:
                        results[service_name]["archived-urls"] += 1
                    if query["archived_query_url_location"] is not None:
                        results[service_name]["archived-query-urls"] += 1
                    if query["archived_raw_serp_location"] is not None:
                        results[service_name]["archived-raw-serps"] += 1
                    if query["archived_parsed_serp_location"] is not None:
                        results[service_name]["archived-parsed-serps"] += 1

            with gzip_open(documents_path, "rt") as documents_file:
                lines = tqdm(
                    documents_file,
                    desc="Read documents corpus"
                )
                for line in lines:
                    document = loads(line)
                    service_name = document["service"]
                    if document["archived_snippet_location"] is not None:
                        results[service_name]["archived-snippets"] += 1
                    if document[
                        "archived_raw_search_result_location"
                    ] is not None:
                        results[service_name][
                            "archived-raw-search-results"] += 1
                    if document[
                        "archived_parsed_search_result_location"
                    ] is not None:
                        results[service_name][
                            "archived-parsed-search-results"] += 1

    output_path: Path
    if output is not None:
        output_path = output
    elif focused:
        output_path = data_directory / "focused" / "stats.csv"
    else:
        output_path = data_directory / "stats.csv"

    df = DataFrame([
        {
            "service": service_name,
            **service_results,
        }
        for service_name, service_results in results.items()
    ])
    df.to_csv(output_path, index=False)
