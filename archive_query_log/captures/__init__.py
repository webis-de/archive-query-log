from datetime import datetime
from itertools import chain
from typing import Iterable, Iterator
from urllib.parse import urljoin
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script
from tqdm.auto import tqdm
from web_archive_api.cdx import CdxApi, CdxMatchType

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_CAPTURE
from archive_query_log.orm import Source, Capture
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now, UTC


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


def _add_captures_actions(
        config: Config,
        source: Source,
) -> Iterator[dict]:
    start_time = utc_now()

    # Re-check if fetching captures is necessary.
    if (source.last_fetched_captures is not None and
            source.last_fetched_captures > source.last_modified):
        return

    captures_iter = _iter_captures(config, source, start_time)
    for capture in captures_iter:
        yield capture.to_dict(include_meta=True)

    yield update_action(source, last_fetched_captures=start_time)


def fetch_captures(config: Config) -> None:
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
        changed_sources: Iterable[Source] = changed_sources_search.scan()
        changed_sources = safe_iter_scan(changed_sources)
        # noinspection PyTypeChecker
        changed_sources = tqdm(changed_sources, total=num_changed_sources,
                               desc="Fetching captures", unit="source")
        actions = chain.from_iterable(
            _add_captures_actions(config, source)
            for source in changed_sources
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed sources.")
