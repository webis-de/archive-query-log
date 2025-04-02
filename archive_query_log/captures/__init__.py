from itertools import chain, islice
from typing import Iterable, Iterator
from urllib.parse import urljoin
from uuid import uuid5
from warnings import warn

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, RankFeature, Term
from requests import ConnectTimeout, HTTPError, Response
from tqdm.auto import tqdm
from web_archive_api.cdx import CdxApi, CdxMatchType

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_CAPTURE
from archive_query_log.orm import Source, Capture, InnerParser
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now, UTC


def _iter_captures(
        config: Config,
        source: Source,
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
        if len(cdx_capture.url) > 32766:
            warn(RuntimeWarning(
                f"The URL {cdx_capture.url} exceeds the "
                f"maximum length of Elasticsearch."
                f" It will be skipped."
            ))
            continue

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
            id=capture_id,
            last_modified=utc_now(),
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
            url_query_parser=InnerParser(
                should_parse=True,
            ),
        )


def _add_captures_actions(
        config: Config,
        source: Source,
) -> Iterator[dict]:
    # Re-check if fetching captures is necessary.
    if (source.should_fetch_captures is not None and
            not source.should_fetch_captures):
        return

    captures_iter = _iter_captures(config, source)
    try:
        for capture in captures_iter:
            capture.meta.index = config.es.index_captures
            yield capture.to_dict(include_meta=True)
    except ConnectTimeout as e:
        # The archives' CDX are usually very slow, so we expect timeouts.
        # Rather than failing, we just warn and continue with the next source.
        # But we do not mark this source as fetched, so that we try again.
        warn(RuntimeWarning(
            f"Connection timeout while fetching captures "
            f"for source {source.id}: {e}"))
        return
    except HTTPError as e:
        ignored = False
        response: Response = e.response
        if response.status_code == 403:
            warn(RuntimeWarning(
                f"Unauthorized to fetch captures for source "
                f"domain {source.provider.domain} and "
                f"URL prefix {source.provider.url_path_prefix}."
            ))
            ignored = True
        if not ignored:
            raise e

    yield update_action(
        source,
        should_fetch_captures=False,
        last_fetched_captures=utc_now(),
    )


def fetch_captures(config: Config, prefetch_limit: int | None = None) -> None:
    changed_sources_search: Search = (
        Source.search(using=config.es.client, index=config.es.index_sources)
        .filter(
            ~Term(should_fetch_captures=False)
            # FIXME: The UK Web Archive is facing an outage: https://www.webarchive.org.uk/#en
            & ~Term(archive__id="90be629c-2a95-52da-9ae8-ca58454c9826")
        )
        .query(
            RankFeature(field="archive.priority", saturation={}) |
            RankFeature(field="provider.priority", saturation={}) |
            FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_sources = changed_sources_search.count()
    if num_changed_sources > 0:
        echo(f"Fetching captures for {num_changed_sources} "
             f"new/changed sources.")
        changed_sources: Iterable[Source] = (
            changed_sources_search
            .params(preserve_order=True)
            .scan()
        )
        changed_sources = safe_iter_scan(changed_sources)

        if prefetch_limit is not None:
            num_changed_sources = min(num_changed_sources, prefetch_limit)
            changed_sources = tqdm(changed_sources, total=num_changed_sources, desc="Pre-fetching sources", unit="source")
            changed_sources = iter(list(islice(changed_sources, prefetch_limit)))

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
