from datetime import timedelta, datetime
from itertools import chain
from typing import Any, Iterable, Iterator, Callable
from urllib.parse import urljoin
from uuid import uuid5, UUID
from warnings import warn

from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, RankFeature, Term, Range, Exists
from pydantic import HttpUrl, ValidationError
from requests import ConnectTimeout, HTTPError, Response
from tqdm.auto import tqdm
from web_archive_api.cdx import CdxApi, CdxMatchType, CdxCapture

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_CAPTURE
from archive_query_log.orm import (
    Source,
    Capture,
    InnerParser,
    OrganicResult,
    InnerCapture,
)
from archive_query_log.utils.time import utc_now, UTC


REFETCH_DELTA = timedelta(weeks=4)


def _iter_captures(
    config: Config,
    source: Source,
) -> Iterator[Capture]:
    cdx_api = CdxApi(
        api_url=source.archive.cdx_api_url.encoded_string(),
        session=config.http.session,
    )
    url = f"https://{source.provider.domain}"
    url = urljoin(url, source.provider.url_path_prefix)
    url = url.removeprefix("https://")
    cdx_captures = cdx_api.iter_captures(
        url=url,
        match_type=CdxMatchType.PREFIX,
        # If the source was not fetched before, fetch all captures.
        # Otherwise, only fetch new captures captured since the last fetch.
        from_timestamp=source.last_fetched_captures
        if not source.should_fetch_captures
        else None,
    )
    for cdx_capture in cdx_captures:
        if len(cdx_capture.url) > 32766:
            warn(
                RuntimeWarning(
                    f"The URL {cdx_capture.url} exceeds the "
                    f"maximum length of Elasticsearch."
                    f" It will be skipped."
                )
            )
            continue

        capture_utc_timestamp_text = cdx_capture.timestamp.astimezone(UTC).strftime(
            "%Y%m%d%H%M%S"
        )
        capture_id_components = (
            source.archive.cdx_api_url.encoded_string(),
            cdx_capture.url,
            capture_utc_timestamp_text,
        )
        capture_id = uuid5(
            NAMESPACE_CAPTURE,
            ":".join(capture_id_components),
        )
        yield Capture(
            id=capture_id,
            last_modified=utc_now(),
            archive=source.archive,
            provider=source.provider,
            url=HttpUrl(cdx_capture.url),
            url_key=cdx_capture.url_key,
            timestamp=cdx_capture.timestamp.astimezone(UTC),
            status_code=cdx_capture.status_code,
            digest=cdx_capture.digest,
            mimetype=cdx_capture.mimetype,
            filename=cdx_capture.filename,
            offset=cdx_capture.offset,
            length=cdx_capture.length,
            access=cdx_capture.access,
            redirect_url=HttpUrl(cdx_capture.redirect_url)
            if cdx_capture.redirect_url is not None
            else None,
            flags=(
                [flag.value for flag in cdx_capture.flags]
                if cdx_capture.flags is not None
                else None
            ),
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
    if (
        source.should_fetch_captures is not None
        and not source.should_fetch_captures
        and (
            source.last_fetched_captures is None
            or source.last_fetched_captures >= utc_now() - REFETCH_DELTA
        )
    ):
        return

    captures_iter = _iter_captures(config, source)
    try:
        for capture in captures_iter:
            capture.index = config.es.index_captures
            # Use an idempotent upsert instead of a failing create, since a
            # capture's id is a deterministic hash of its CDX identity, so a
            # duplicate id always means identical content (e.g., duplicate
            # rows across CDX pagination boundaries, or a re-fetch after an
            # interrupted run).
            yield capture.index_action()
    except ConnectTimeout as e:
        # The archives' CDX are usually very slow, so we expect timeouts.
        # Rather than failing, we just warn and continue with the next source.
        # But we do not mark this source as fetched, so that we try again.
        warn(
            RuntimeWarning(
                f"Connection timeout while fetching captures "
                f"for source {source.id}: {e}"
            )
        )
        return
    except HTTPError as e:
        ignored = False
        response: Response = e.response
        if response.status_code == 403:
            warn(
                RuntimeWarning(
                    f"Unauthorized to fetch captures for source "
                    f"domain {source.provider.domain} and "
                    f"URL prefix {source.provider.url_path_prefix}."
                )
            )
            ignored = True
        if not ignored:
            raise e

    yield source.update_action(
        should_fetch_captures=False,
        last_fetched_captures=utc_now(),
    )


def fetch_captures(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    changed_sources_search: Search = (
        Source.search(using=config.es.client, index=config.es.index_sources)
        .filter(
            (
                ~Term(should_fetch_captures=False)
                | Range(
                    last_fetched_captures={
                        "lt": utc_now() - REFETCH_DELTA,
                    }
                )
            )
            # FIXME: The UK Web Archive is facing an outage: https://www.webarchive.org.uk/#en
            & ~Term(archive__id="90be629c-2a95-52da-9ae8-ca58454c9826")
        )
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_sources = changed_sources_search.count()
    if num_changed_sources == 0:
        print("No new/changed sources.")
        return

    changed_sources: Iterable[Source] = changed_sources_search.params(
        size=size
    ).execute()

    changed_sources = tqdm(
        changed_sources,
        total=num_changed_sources,
        desc="Fetching captures",
        unit="source",
    )
    actions = chain.from_iterable(
        _add_captures_actions(config, source) for source in changed_sources
    )
    config.es.bulk(
        actions=actions,
        dry_run=dry_run,
    )


def _capture_timestamp_distance(timestamp: datetime) -> Callable[[CdxCapture], float]:
    def _distance(capture: CdxCapture) -> float:
        return abs(timestamp - capture.timestamp).total_seconds()

    return _distance


def _cdx_capture_to_inner_capture(cdx_capture: CdxCapture) -> InnerCapture:
    return InnerCapture(
        id=UUID(int=0),
        url=HttpUrl(cdx_capture.url),
        timestamp=cdx_capture.timestamp,
        status_code=cdx_capture.status_code,
        digest=cdx_capture.digest,
        mimetype=cdx_capture.mimetype,
    )


def _organic_result_capture_update_action(
    result_block: OrganicResult,
    capture_before_serp: InnerCapture | None,
    capture_after_serp: InnerCapture | None,
) -> dict:
    updates: dict[str, Any] = {
        "capture_before_serp": capture_before_serp,
        "capture_after_serp": capture_after_serp,
        "should_fetch_captures": False,
        "last_fetched_captures": utc_now(),
    }

    # Only discard already downloaded WARCs if the capture they belong to changed.
    # Omitting the fields from the update action keeps their current values.
    # Added in case there are already WARCs that have been downloaded with the old version.
    if capture_before_serp != result_block.capture_before_serp:
        updates["warc_location_before_serp"] = None
        updates["warc_downloader_before_serp"] = None
    if capture_after_serp != result_block.capture_after_serp:
        updates["warc_location_after_serp"] = None
        updates["warc_downloader_after_serp"] = None

    # Drop the search-relevance score, if set, since it must not end up in
    # the update action's document body (unlike `id`/`index`/etc., which are
    # needed to route the update, `score` is never a valid field to send).
    result_block = result_block.model_copy()
    result_block.__pydantic_fields_set__.discard("score")

    return result_block.update_action(**updates)


def _update_organic_result_capture_action(
    config: Config,
    result_block: OrganicResult,
) -> dict:
    if result_block.url is None:
        raise ValueError("Web search result block has no URL.")

    cdx_api = CdxApi(
        api_url=result_block.archive.cdx_api_url.encoded_string(),
        session=config.http.session,
    )

    serp_capture_timestamp = result_block.serp_capture.timestamp
    nearest_capture_before_serp: CdxCapture | None = min(
        cdx_api.iter_captures(
            url=result_block.url.encoded_string(),
            match_type=CdxMatchType.EXACT,
            to_timestamp=serp_capture_timestamp,
        ),
        key=_capture_timestamp_distance(serp_capture_timestamp),
        default=None,
    )
    nearest_capture_after_serp: CdxCapture | None = min(
        cdx_api.iter_captures(
            url=result_block.url.encoded_string(),
            match_type=CdxMatchType.EXACT,
            from_timestamp=serp_capture_timestamp,
        ),
        key=_capture_timestamp_distance(serp_capture_timestamp),
        default=None,
    )

    return _organic_result_capture_update_action(
        result_block=result_block,
        capture_before_serp=_cdx_capture_to_inner_capture(nearest_capture_before_serp)
        if nearest_capture_before_serp is not None
        else None,
        capture_after_serp=_cdx_capture_to_inner_capture(nearest_capture_after_serp)
        if nearest_capture_after_serp is not None
        else None,
    )


def fetch_organic_result_captures(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    changed_result_blocks_search: Search = (
        OrganicResult.search(
            using=config.es.client, index=config.es.index_organic_results
        )
        .filter(Exists(field="url") & ~Term(should_fetch_captures=False))
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_result_blocks = changed_result_blocks_search.count()

    if num_changed_result_blocks <= 0:
        print("No new/changed web search result blocks.")
        return

    changed_result_blocks: Iterable[OrganicResult] = (
        changed_result_blocks_search.params(size=size).execute()
    )

    changed_result_blocks = tqdm(
        changed_result_blocks,
        total=num_changed_result_blocks,
        desc="Fetch captures",
        unit="web search result block",
    )

    actions = (
        _update_organic_result_capture_action(
            config=config,
            result_block=organic_result,
        )
        for organic_result in changed_result_blocks
        if organic_result.url is not None
    )
    config.es.bulk(
        actions=actions,
        dry_run=dry_run,
    )
