from asyncio import run
from math import inf
from pathlib import Path

from click import option, argument, BOOL, IntRange
from pandas import DataFrame

from web_archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL, LOGGER
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam, ServiceChoice
from web_archive_query_log.config import SERVICES

# See:
# https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api
_URLS_PER_BLOCK = 3000
_BLOCKS_PER_PAGE = 50


@main.group("stats")
def stats_group():
    pass


def _data_directory_option():
    return option(
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


def _focused_option():
    return option(
        "-f", "--focused",
        type=BOOL,
        default=False,
        is_flag=True,
    )


def _service_name_argument():
    return argument(
        "service",
        type=ServiceChoice(),
        required=True,
    )


def _all_archived_urls(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.urls.fetch import ArchivedUrlsFetcher, \
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


@stats_group.command(
    "all-archived-urls",
    help="Get upper bound for the number of all archived URLs from "
         "the Wayback Machine's CDX API.",
)
@_data_directory_option()
@_focused_option()
@_service_name_argument()
def all_archived_urls_command(
        data_directory: Path,
        focused: bool,
        service: str,
) -> None:
    print(_all_archived_urls(
        data_directory=data_directory,
        focused=focused,
        service=service,
    ))


def _archived_urls(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    from web_archive_query_log.index import ArchivedUrlIndex
    index = ArchivedUrlIndex(
        data_directory=data_directory,
        focused=focused,
        service=service,
    )
    index.index()
    return len(index)


@stats_group.command(
    "archived-urls",
    help="Get number of fetched archived URLs from "
         "the Wayback Machine's CDX API.",
)
@_data_directory_option()
@_focused_option()
@_service_name_argument()
def archived_urls_command(
        data_directory: Path,
        focused: bool,
        service: str,
) -> None:
    print(_archived_urls(
        data_directory=data_directory,
        focused=focused,
        service=service,
    ))


def _archived_query_urls(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    from web_archive_query_log.index import ArchivedQueryUrlIndex
    index = ArchivedQueryUrlIndex(
        data_directory=data_directory,
        focused=focused,
        service=service,
    )
    index.index()
    return len(index)


@stats_group.command(
    "archived-query-urls",
    help="Get number of queries from fetched archived URLs.",
)
@_data_directory_option()
@_focused_option()
@_service_name_argument()
def archived_query_urls_command(
        data_directory: Path,
        focused: bool,
        service: str,
) -> None:
    print(_archived_query_urls(
        data_directory=data_directory,
        focused=focused,
        service=service,
    ))


def _archived_raw_serps(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    from web_archive_query_log.index import ArchivedRawSerpIndex
    index = ArchivedRawSerpIndex(
        data_directory=data_directory,
        focused=focused,
        service=service,
    )
    index.index()
    return len(index)


@stats_group.command(
    "archived-raw-serps",
    help="Get number of raw SERP contents (in WARC files) for parsed queries.",
)
@_data_directory_option()
@_focused_option()
@_service_name_argument()
def archived_raw_serps_command(
        data_directory: Path,
        focused: bool,
        service: str,
) -> None:
    print(_archived_raw_serps(
        data_directory=data_directory,
        focused=focused,
        service=service,
    ))


def _archived_parsed_serps(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    from web_archive_query_log.index import ArchivedParsedSerpIndex
    index = ArchivedParsedSerpIndex(
        data_directory=data_directory,
        focused=focused,
        service=service,
    )
    index.index()
    return len(index)


@stats_group.command(
    "archived-parsed-serps",
    help="Get number of parsed SERPs.",
)
@_data_directory_option()
@_focused_option()
@_service_name_argument()
def archived_parsed_serps_command(
        data_directory: Path,
        focused: bool,
        service: str,
) -> None:
    print(_archived_parsed_serps(
        data_directory=data_directory,
        focused=focused,
        service=service,
    ))


def _archived_raw_search_results(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    from web_archive_query_log.index import ArchivedRawSearchResultIndex
    index = ArchivedRawSearchResultIndex(
        data_directory=data_directory,
        focused=focused,
        service=service,
    )
    index.index()
    return len(index)


@stats_group.command(
    "archived-raw-search-results",
    help="Get number of downloaded raw search result contents (as WARC files) "
         "for parsed SERPs.",
)
@_data_directory_option()
@_focused_option()
@_service_name_argument()
def archived_raw_search_results_command(
        data_directory: Path,
        focused: bool,
        service: str,
) -> None:
    print(_archived_raw_search_results(
        data_directory=data_directory,
        focused=focused,
        service=service,
    ))


def _archived_parsed_search_results(
        data_directory: Path,
        focused: bool,
        service: str,
) -> int:
    raise NotImplementedError()


@stats_group.command(
    "archived-parsed-search-results",
    help="Get number of parsed search results "
         "from raw search result contents.",
)
@_data_directory_option()
@_focused_option()
@_service_name_argument()
def archived_parsed_search_results_command(
        data_directory: Path,
        focused: bool,
        service: str,
) -> None:
    print(_archived_parsed_search_results(
        data_directory=data_directory,
        focused=focused,
        service=service,
    ))


@stats_group.command(
    "all",
    help="Get all stats for all services.",
)
@_data_directory_option()
@_focused_option()
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
def all_stats_command(
        data_directory: Path,
        focused: bool,
        output: Path | None,
        min_rank: int | None,
        max_rank: int | None,
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
    results: dict[str, dict[str, int]] = {}
    for service in services:
        service_results: dict[str, int] = {}
        print(f"\033[1mService: {service.name}\033[0m")
        print(f"✔ Alexa rank: {service.alexa_rank}")
        service_results["all-archived-urls"] = _all_archived_urls(
            data_directory,
            focused,
            service.name,
        )
        print(f"✔ Available Archived URLs: "
              f"{service_results['all-archived-urls']}")
        service_results["archived-urls"] = _archived_urls(
            data_directory,
            focused,
            service.name,
        )
        print(f"✔ Archived URLs: "
              f"{service_results['archived-urls']}")
        service_results["archived-query-urls"] = _archived_query_urls(
            data_directory,
            focused,
            service.name,
        )
        print(f"✔ Archived query URLs: "
              f"{service_results['archived-query-urls']}")
        service_results["archived-raw-serps"] = _archived_raw_serps(
            data_directory,
            focused,
            service.name,
        )
        print(f"✔ Archived raw SERPs: "
              f"{service_results['archived-raw-serps']}")
        service_results["archived-parsed-serps"] = _archived_parsed_serps(
            data_directory,
            focused,
            service.name,
        )
        print(f"✔ Archived parsed SERPs: "
              f"{service_results['archived-parsed-serps']}")
        service_results["archived-raw-search-results"] = \
            _archived_raw_search_results(
                data_directory,
                focused,
                service.name,
            )
        print(f"✔ Archived raw search results: "
              f"{service_results['archived-raw-search-results']}")
        # service_results["archived-parsed-search-results"] = \
        #     _archived_parsed_search_results(
        #         data_directory,
        #         focused,
        #         service.name,
        #     )
        # print(f"✔ Archived parsed search results: "
        #         f"{service_results['archived-parsed-search-results']}")
        print()
        results[service.name] = service_results

    if output is not None:
        df = DataFrame([
            {
                "service": service_name,
                **service_results,
            }
            for service_name, service_results in results.items()
        ])
        df.to_csv(output, index=False)
        print(f"Statistics saved to {output}.")
