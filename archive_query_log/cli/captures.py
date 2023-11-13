from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Any
from urllib.parse import urljoin
from uuid import uuid5
from warnings import warn

from click import group, echo, Path as PathType, argument, option
from elasticsearch import ConnectionTimeout
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script
from tqdm.auto import tqdm
from web_archive_api.cdx import CdxApi, CdxMatchType

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_CAPTURE
from archive_query_log.orm import Source, Capture
from archive_query_log.utils.es import safe_iter_scan
from archive_query_log.utils.time import utc_now, UTC


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
            _add_captures(config, source)
    else:
        echo("No new/changed sources.")


@captures.group("import")
def import_() -> None:
    pass


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
    from archive_query_log.compat.aql22 import import_captures
    import_captures(
        config=config,
        data_dir_path=data_dir_path,
        check_memento=check_memento,
        search_provider=search_provider,
        search_provider_index=search_provider_index,
    )
