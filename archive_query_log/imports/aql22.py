from datetime import datetime, timezone
from itertools import chain
from os.path import getmtime
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple
from urllib.parse import unquote
from uuid import uuid5

from click import echo
from elasticsearch_dsl.query import Term
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.legacy.model import ArchivedUrl
from archive_query_log.legacy.urls.iterable import ArchivedUrls
from archive_query_log.namespaces import NAMESPACE_CAPTURE
from archive_query_log.orm import Capture, Archive, Provider, \
    InnerProvider, InnerArchive
from archive_query_log.utils.time import CET, UTC


class _ImportablePath(NamedTuple):
    path: Path
    archive: Archive
    provider: Provider
    domain: str
    url_path_prefix: str


def _iter_captures(
        config: Config,
        importable_path: _ImportablePath,
        last_modified: datetime,
        archived_urls: Iterable[ArchivedUrl],
        check_memento: bool = True,
) -> Iterator[Capture]:
    for archived_url in archived_urls:
        url = archived_url.url
        timestamp = datetime.fromtimestamp(
            archived_url.timestamp,
            tz=timezone.utc,
        )
        # Bug fix because the AQL-22 data is in CET, but the timestamps are
        # not marked as such.
        timestamp = timestamp.astimezone(CET)
        timestamp = timestamp.replace(tzinfo=UTC)

        memento_url = (
            f"{importable_path.archive.memento_api_url}/"
            f"{timestamp.astimezone(UTC).strftime('%Y%m%d%H%M%S')}/"
            f"{url}")
        if check_memento:
            response = config.http.session_no_retry.head(
                memento_url,
                allow_redirects=False,
            )
            if response.status_code != 200:
                continue

        capture_id_components = (
            importable_path.archive.cdx_api_url,
            url,
            timestamp.astimezone(UTC).strftime("%Y%m%d%H%M%S"),
        )
        capture_id = str(uuid5(
            NAMESPACE_CAPTURE,
            ":".join(capture_id_components),
        ))
        yield Capture(
            id=capture_id,
            last_modified=last_modified.replace(microsecond=0),
            archive=InnerArchive(
                id=importable_path.archive.id,
                cdx_api_url=importable_path.archive.cdx_api_url,
                memento_api_url=importable_path.archive.memento_api_url,
            ),
            provider=InnerProvider(
                id=importable_path.provider.id,
                domain=importable_path.domain,
                url_path_prefix=importable_path.url_path_prefix,
            ),
            url=url,
            timestamp=timestamp.astimezone(UTC),
            url_query_parser=InnerProvider(
                should_parse=True,
            ),
        )


def _import_captures_path(
        config: Config,
        importable_path: _ImportablePath,
        check_memento: bool = True,
) -> None:
    echo(f"Importing captures from {importable_path.path} to "
         f"archive {importable_path.archive.id} and "
         f"provider {importable_path.provider.id}.")

    json_paths = list(importable_path.path.glob("*.jsonl.gz"))
    oldest_modification_time = min(
        datetime.fromtimestamp(getmtime(path))
        for path in json_paths
    ).astimezone(UTC)
    echo(f"Found {len(json_paths)} JSONL files "
         f"(oldest from {oldest_modification_time.strftime('%c')}).")

    urls_iterators_list = [ArchivedUrls(path) for path in json_paths]
    urls_iterators: Iterable[ArchivedUrls] = urls_iterators_list
    if len(urls_iterators_list) > 50:
        # noinspection PyTypeChecker
        urls_iterators = tqdm(
            urls_iterators,
            desc="Get capture count",
            unit="file",
        )
    total_count = sum(len(urls) for urls in urls_iterators)
    echo(f"Found {total_count} captures.")

    archived_urls: Iterable[ArchivedUrl] = chain.from_iterable(
        urls_iterators_list)
    # noinspection PyTypeChecker
    archived_urls = tqdm(
        archived_urls,
        total=total_count,
        desc="Importing captures",
        unit="capture",
    )
    captures_iter = _iter_captures(
        config=config,
        importable_path=importable_path,
        last_modified=oldest_modification_time,
        archived_urls=archived_urls,
        check_memento=check_memento,
    )
    actions = (
        _create_action(capture, config)
        for capture in captures_iter
    )
    config.es.bulk(actions)


def _create_action(capture: Capture, config: Config) -> dict:
    capture.meta.index = config.es.index_captures
    return {
        **capture.to_dict(include_meta=True),
        "_op_type": "create",
    }


def import_captures(
        config: Config,
        data_dir_path: Path,
        check_memento: bool,
        search_provider: str | None,
        search_provider_index: int | None,
) -> None:
    echo(f"Importing AQL-22 captures from: {data_dir_path}")

    archive_response = (
        Archive.search(using=config.es.client, index=config.es.index_archives)
        .query(
            Term(cdx_api_url="https://web.archive.org/cdx/search/cdx")
        )
        .execute()
    )
    if archive_response.hits.total.value < 1:
        echo("No AQL-22 archive found. Add an archive with the "
             "CDX API URL 'https://web.archive.org/cdx/search/cdx' "
             "first.")
        exit(1)

    archive: Archive = archive_response.hits[0]
    echo(f"Importing captures for archive {archive.id}: {archive.name}")

    archived_urls_path = data_dir_path / "archived-urls"
    if not archived_urls_path.exists():
        echo("No captures found.")
        return

    search_provider_paths = sorted(archived_urls_path.glob("*"))
    if search_provider is not None:
        search_provider_paths = [
            path for path in search_provider_paths
            if path.name == search_provider
        ]
    elif search_provider_index is not None:
        search_provider_paths = [search_provider_paths[search_provider_index]]
    if len(search_provider_paths) == 0:
        echo("No captures found.")
        return
    prefix_paths_list: list[Path] = list(chain.from_iterable((
        search_provider_path.glob("*")
        for search_provider_path in search_provider_paths
    )))

    importable_paths = []
    prefix_paths: Iterable[Path] = prefix_paths_list
    # noinspection PyTypeChecker
    prefix_paths = tqdm(
        prefix_paths,
        desc="Checking URL prefixes",
        unit="prefix",
    )
    for prefix_path in prefix_paths:
        prefix = unquote(prefix_path.name)
        domain = prefix.split("/", maxsplit=1)[0]
        url_path_prefix = prefix.removeprefix(domain)

        provider_response = (
            Provider.search(using=config.es.client, index=config.es.index_providers)
            .query(
                Term(domains=domain) &
                Term(url_path_prefixes=url_path_prefix)
            )
            .execute()
        )
        if provider_response.hits.total.value >= 1:
            provider: Provider = provider_response.hits[0]
            importable_paths.append(_ImportablePath(
                path=prefix_path,
                archive=archive,
                provider=provider,
                domain=domain,
                url_path_prefix=url_path_prefix,
            ))

    for importable_path in importable_paths:
        _import_captures_path(
            config=config,
            importable_path=importable_path,
            check_memento=check_memento,
        )
