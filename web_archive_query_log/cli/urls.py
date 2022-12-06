from asyncio import run
from pathlib import Path
from typing import Iterable

from click import option, Path as PathParam, argument, STRING, Choice, INT

from web_archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL
from web_archive_query_log.cli.main import main
from web_archive_query_log.cli.util import URL, ServiceChoice
from web_archive_query_log.urls.fetch import UrlMatchScope


@main.group("urls")
def urls_group():
    pass


# noinspection PyTypeChecker
@urls_group.command("fetch")
@option(
    "-m", "--match-scope",
    type=Choice(
        [scope.value for scope in UrlMatchScope],
        case_sensitive=False,
    ),
    default=UrlMatchScope.EXACT.value,
)
@option(
    "--include-status-codes",
    type=INT,
    multiple=True,
    default={200},
)
@option(
    "--exclude-status-codes",
    type=INT,
    multiple=True,
    default={},
)
@option(
    "--include-mime-types",
    type=STRING,
    multiple=True,
    default={"text/html"},
)
@option(
    "--exclude-mime-types",
    type=STRING,
    multiple=True,
    default={},
)
@option(
    "-u", "--api-url", "--cdx-api-url",
    type=URL,
    default=CDX_API_URL,
)
@option(
    "-o", "--output-path",
    type=PathParam(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH / f"urls"
)
@argument(
    "urls",
    type=STRING,
    nargs=-1,
    required=True,
)
def fetch(
        api_url: str,
        match_scope: str,
        include_status_codes: Iterable[int],
        exclude_status_codes: Iterable[int],
        include_mime_types: Iterable[str],
        exclude_mime_types: Iterable[str],
        output_path: Path,
        urls: Iterable[str],
) -> None:
    from web_archive_query_log.urls.fetch import ArchivedUrlsFetcher
    fetcher = ArchivedUrlsFetcher(
        match_scope=UrlMatchScope(match_scope),
        include_status_codes=set(include_status_codes),
        exclude_status_codes=set(exclude_status_codes),
        include_mime_types=set(include_mime_types),
        exclude_mime_types=set(exclude_mime_types),
        cdx_api_url=api_url
    )
    run(fetcher.fetch_many(
        output_path=output_path,
        urls=set(urls),
    ))


@urls_group.command("fetch-service")
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
@argument(
    "service_name",
    type=ServiceChoice(),
    required=True,
)
def fetch_service(
        data_directory: Path,
        service_name: str,
) -> None:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.urls.fetch import ArchivedUrlsFetcher
    service = SERVICES[service_name]
    fetcher = ArchivedUrlsFetcher(
        match_scope=UrlMatchScope.DOMAIN,
        include_status_codes={200},
        exclude_status_codes=set(),
        include_mime_types={"text/html"},
        exclude_mime_types=set(),
        cdx_api_url=CDX_API_URL
    )
    run(fetcher.fetch_many(
        output_path=data_directory / service_name,
        urls=set(service.domains),
    ))
