from typing import Iterable, Iterator, Any
from urllib.parse import urljoin
from uuid import uuid5

from click import group, echo
from dateutil.tz import UTC
from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Range, Exists, FunctionScore
from elasticsearch_dsl.response import Response
from tqdm.auto import tqdm

from archive_query_log.new.cdx import CdxApi, CdxMatchType
from archive_query_log.new.cli.util import pass_config
from archive_query_log.new.config import Config
from archive_query_log.new.namespaces import NAMESPACE_CAPTURE
from archive_query_log.new.orm import (
    Source, Capture)
from archive_query_log.new.utils.time import EPOCH, current_time


@group()
def captures():
    pass


def _iter_captures(config: Config, source: Source) -> Iterator[Capture]:
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
        )


def _add_captures(
        config: Config,
        source: Source,
) -> None:
    # TODO: Re-check if fetching captures is necessary.
    start_time = current_time()
    captures_iter = _iter_captures(config, source)
    actions = (
        capture.to_dict(include_meta=True)
        for capture in captures_iter
    )
    responses: Iterable[tuple[bool, Any]] = parallel_bulk(
        client=config.es,
        actions=actions,
    )
    for success, info in responses:
        if not success:
            raise RuntimeError(f"Indexing error: {info}")
    source.update(
        using=config.es,
        last_fetched_captures=start_time,
    )


@captures.command()
@pass_config
def fetch(config: Config) -> None:
    Source.init(using=config.es)
    Source.index().refresh(using=config.es)
    Capture.init(using=config.es)

    last_source_response: Response = (
        Source.search(using=config.es)
        .query(Exists(field="last_fetched_captures"))
        .sort("-last_fetched_captures")
        .execute()
    )
    if last_source_response.hits.total.value == 0:
        last_source_time = EPOCH
    else:
        last_source_time = last_source_response[0].last_fetched_captures
    changed_sources_search: Search = (
        Source.search(using=config.es)
        .query(FunctionScore(
            query=~Range(last_fetched_captures={"lte": last_source_time}),
            functions=[RandomScore()]
        ))
    )
    num_changed_sources = (
        changed_sources_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    if num_changed_sources > 0:
        echo(f"Fetching captures for {num_changed_sources} "
             f"new/changed sources "
             f"since {last_source_time.astimezone().strftime('%c')}.")
        changed_sources: Iterator[Source] = changed_sources_search.scan()
        # noinspection PyTypeChecker
        changed_sources = tqdm(changed_sources, total=num_changed_sources,
                               desc="Fetching captures", unit="source")
        for source in changed_sources:
            _add_captures(config, source)
    else:
        echo(f"No changed sources "
             f"since {last_source_time.astimezone().strftime('%c')}.")

    Source.index().refresh(using=config.es)
    Capture.index().refresh(using=config.es)
