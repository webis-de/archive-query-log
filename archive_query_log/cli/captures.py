from datetime import datetime, timezone
from itertools import chain
from os.path import getmtime
from pathlib import Path
from typing import Iterable, Iterator, Any, NamedTuple
from urllib.parse import urljoin, unquote
from uuid import uuid5
from warnings import warn

from click import group, echo, Path as PathType, argument, option
from elasticsearch import ConnectionTimeout
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script, Term
from tqdm.auto import tqdm

from archive_query_log.cdx import CdxApi, CdxMatchType
from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.legacy.model import ArchivedUrl
from archive_query_log.legacy.urls.iterable import ArchivedUrls
from archive_query_log.namespaces import NAMESPACE_CAPTURE
from archive_query_log.orm import Source, Capture, Archive, Provider, \
    InnerProvider, InnerArchive
from archive_query_log.utils.es import safe_iter_scan
from archive_query_log.utils.time import utc_now, CET, UTC


@group()
def captures():
    pass


def _iter_captures(
        config: Config,
        source: Source,
        start_time: datetime,
) -> Iterator[Capture]:
    cdx_api = CdxApi(
        api_url=source.archive.cdx_api_url,
        session=config.http.session,
    )
    url = f"https://{source.provider.domain}"
    url = urljoin(url, source.provider.url_path_prefix)
    url = url.removeprefix("https://")
    cdx_captures = cdx_api.iter_captures(
        url=url,
        match_type=CdxMatchType.PREFIX,
    )
    for cdx_capture in cdx_captures:
        capture_utc_timestamp_text = (
            cdx_capture.timestamp.astimezone(UTC).strftime("%Y%m%d%H%M%S"))
        capture_id_components = (
            source.archive.cdx_api_url,
            cdx_capture.url,
            capture_utc_timestamp_text,
        )
        capture_id = str(uuid5(
            NAMESPACE_CAPTURE,
            ":".join(capture_id_components),
        ))
        yield Capture(
            meta={"id": capture_id},
            archive=source.archive,
            provider=source.provider,
            url=cdx_capture.url,
            url_key=cdx_capture.url_key,
            timestamp=cdx_capture.timestamp.astimezone(UTC),
            status_code=cdx_capture.status_code,
            digest=cdx_capture.digest,
            mimetype=cdx_capture.mimetype,
            filename=cdx_capture.filename,
            offset=cdx_capture.offset,
            length=cdx_capture.length,
            access=cdx_capture.access,
            redirect_url=cdx_capture.redirect_url,
            flags=([flag.value for flag in cdx_capture.flags]
                   if cdx_capture.flags is not None else None),
            collection=cdx_capture.collection,
            source=cdx_capture.source,
            source_collection=cdx_capture.source_collection,
            last_modified=start_time,
        )


def _add_captures(
        config: Config,
        source: Source,
) -> None:
    start_time = utc_now()

    # Refresh source.
    source = Source.get(
        using=config.es.client,
        id=source.id,
    )

    # Re-check if fetching captures is necessary.
    if (source.last_fetched_captures is not None and
            source.last_fetched_captures > source.last_modified):
        return

    captures_iter = _iter_captures(config, source, start_time)
    actions = (
        capture.to_dict(include_meta=True)
        for capture in captures_iter
    )
    try:
        responses: Iterable[tuple[bool, Any]] = config.es.streaming_bulk(
            actions=actions,
            initial_backoff=2,
            max_backoff=600,
        )
    except ConnectionTimeout:
        warn(RuntimeWarning("Connection timeout while indexing captures."))
        return

    for success, info in responses:
        if not success:
            raise RuntimeError(f"Indexing error: {info}")
    Capture.index().refresh(using=config.es.client)

    source.update(
        using=config.es.client,
        retry_on_conflict=3,
        last_fetched_captures=start_time,
        refresh=True,
    )


@captures.command()
@pass_config
def fetch(config: Config) -> None:
    Capture.init(using=config.es.client)

    changed_sources_search: Search = (
        Source.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="last_fetched_captures") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['last_fetched_captures'].isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['last_fetched_captures'].value)",
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_sources = (
        changed_sources_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    if num_changed_sources > 0:
        echo(f"Fetching captures for {num_changed_sources} "
             f"new/changed sources.")
        changed_sources: Iterable[Source] = (
            changed_sources_search.params(preserve_order=True).scan())
        changed_sources = safe_iter_scan(changed_sources)
        # noinspection PyTypeChecker
        changed_sources = tqdm(changed_sources, total=num_changed_sources,
                               desc="Fetching captures", unit="source")
        for source in changed_sources:
            if "web.archive.org" in source.archive.cdx_api_url:
                _add_captures(config, source)
    else:
        echo("No new/changed sources.")


@captures.group("import")
def import_() -> None:
    pass


class _Aql22ImportablePath(NamedTuple):
    path: Path
    archive: Archive
    provider: Provider
    domain: str
    url_path_prefix: str


def _iter_aql22_captures(
        config: Config,
        importable_path: _Aql22ImportablePath,
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
            meta={"id": capture_id},
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
            last_modified=last_modified.replace(microsecond=0),
        )


def _import_aql22_path(
        config: Config,
        importable_path: _Aql22ImportablePath,
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
    print(f"Found {total_count} captures.")

    archived_urls: Iterable[ArchivedUrl] = chain.from_iterable(
        urls_iterators_list)
    # noinspection PyTypeChecker
    archived_urls = tqdm(
        archived_urls,
        total=total_count,
        desc="Importing captures",
        unit="capture",
    )
    captures_iter = _iter_aql22_captures(
        config=config,
        importable_path=importable_path,
        last_modified=oldest_modification_time,
        archived_urls=archived_urls,
        check_memento=check_memento,
    )
    actions = (
        {
            **capture.to_dict(include_meta=True),
            "_op_type": "create",
        }
        for capture in captures_iter
    )
    try:
        responses: Iterable[tuple[bool, Any]] = config.es.streaming_bulk(
            actions=actions,
            initial_backoff=2,
            max_backoff=600,
            raise_on_error=False,
        )
    except ConnectionTimeout:
        warn(RuntimeWarning("Connection timeout while indexing captures."))
        return
    for success, info in responses:
        if not success:
            if ("create" in info and
                    info["create"]["error"]["type"] ==
                    "version_conflict_engine_exception"):
                continue
            raise RuntimeError(f"Indexing error: {info}")
    Capture.index().refresh(using=config.es.client)


_CEPH_DIR = Path("/mnt/ceph/storage/")
_DEFAULT_DATA_DIR = (
    _CEPH_DIR / "data-in-progress/data-research/web-search/"
                "archive-query-log/focused/"
    if _CEPH_DIR.is_mount() and _CEPH_DIR.exists()
    else None)


@import_.command(help="Import captures from the AQL-22 dataset.")
@argument("data_dir_path",
          type=PathType(path_type=Path, exists=True, file_okay=False,
                        dir_okay=True, readable=True, writable=False,
                        resolve_path=True, allow_dash=False),
          metavar="DATA_DIR", required=True, default=_DEFAULT_DATA_DIR)
@option("--check-memento/--no-check-memento", default=True)
@option("--search-provider", type=str, envvar="SEARCH_PROVIDER")
@option("--search-provider-index", type=int,
        envvar="SEARCH_PROVIDER_INDEX")
@pass_config
def aql_22(
        config: Config,
        data_dir_path: Path,
        check_memento: bool,
        search_provider: str | None,
        search_provider_index: int | None,
) -> None:
    echo(f"Importing AQL-22 captures from: {data_dir_path}")

    archive_response = (
        Archive.search(using=config.es.client)
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
            Provider.search(using=config.es.client)
            .query(
                Term(domains=domain) &
                Term(url_path_prefixes=url_path_prefix)
            )
            .execute()
        )
        if provider_response.hits.total.value >= 1:
            provider: Provider = provider_response.hits[0]
            importable_paths.append(_Aql22ImportablePath(
                path=prefix_path,
                archive=archive,
                provider=provider,
                domain=domain,
                url_path_prefix=url_path_prefix,
            ))

    Capture.init(using=config.es.client)
    for importable_path in importable_paths:
        _import_aql22_path(
            config=config,
            importable_path=importable_path,
            check_memento=check_memento,
        )
