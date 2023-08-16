from datetime import datetime
from typing import Iterable, Iterator, Any
from urllib.parse import urljoin
from uuid import uuid5
from warnings import warn

from click import group, echo
from dateutil.tz import UTC
from elasticsearch import ConnectionTimeout
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script
from tqdm.auto import tqdm

from archive_query_log.new.cdx import CdxApi, CdxMatchType
from archive_query_log.new.cli.util import pass_config
from archive_query_log.new.config import Config
from archive_query_log.new.namespaces import NAMESPACE_CAPTURE
from archive_query_log.new.orm import (
    Source, Capture)
from archive_query_log.new.utils.time import utc_now


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
        session=config.http_session,
    )
    url = f"https://{source.provider.domain}"
    url = urljoin(url, source.provider.url_path_prefix)
    url = url.removeprefix("https://")
    cdx_captures = cdx_api.iter_captures(
        url=url,
        match_type=CdxMatchType.PREFIX,
    )
    for cdx_capture in cdx_captures:
        capture_id_components = (
            source.archive.cdx_api_url,
            cdx_capture.url,
            cdx_capture.timestamp.astimezone(UTC).strftime("%Y%m%d%H%M%S"),
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
            mimetype=cdx_capture.mimetype,
            status_code=cdx_capture.status_code,
            digest=cdx_capture.digest,
            filename=cdx_capture.filename,
            offset=cdx_capture.offset,
            length=cdx_capture.length,
            flags=cdx_capture.flags,
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
        id=source.meta.id,
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

    source.update(
        using=config.es.client,
        retry_on_conflict=3,
        last_fetched_captures=start_time,
    )


@captures.command()
@pass_config
def fetch(config: Config) -> None:
    Source.init(using=config.es.client)
    Source.index().refresh(using=config.es.client)
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
        changed_sources: Iterator[Source] = (
            changed_sources_search.params(preserve_order=True).scan())
        # noinspection PyTypeChecker
        changed_sources = tqdm(changed_sources, total=num_changed_sources,
                               desc="Fetching captures", unit="source")
        for source in changed_sources:
            _add_captures(config, source)
    else:
        echo(f"No changed sources.")

    Source.index().refresh(using=config.es.client)
    Capture.index().refresh(using=config.es.client)
