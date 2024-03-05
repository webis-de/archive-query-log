from datetime import datetime
from itertools import chain
from typing import Iterable, Iterator, TypeVar, Generic, Type, Callable
from uuid import uuid5
from warnings import warn

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Term, RankFeature
from requests import ConnectionError as RequestsConnectionError
from tqdm.auto import tqdm
from warc_s3 import WarcS3Record
from warcio.recordloader import ArcWarcRecord
from web_archive_api.cdx import CdxApi, CdxMatchType, CdxCapture
from web_archive_api.memento import MementoApi

from archive_query_log import __version__ as app_version
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_DOWNLOADER
from archive_query_log.orm import Serp, InnerDownloader, WarcLocation, Result
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now

_T = TypeVar("_T")


class _WrapperArcWarcRecord(ArcWarcRecord, Generic[_T]):
    wrapped: _T

    def __init__(self, wrapped: _T, record: ArcWarcRecord):
        super().__init__(
            record.format,
            record.rec_type,
            record.rec_headers,
            record.raw_stream,
            record.http_headers,
            record.content_type,
            record.length,
            payload_length=record.payload_length,
            digest_checker=record.digest_checker,
        )
        self.wrapped = wrapped


def _unwrap(
        warc_record: WarcS3Record,
        wrapper_type: Type[_WrapperArcWarcRecord[_T]],
) -> tuple[_T, WarcLocation]:
    record: ArcWarcRecord = warc_record.record
    if not isinstance(record, wrapper_type):
        raise TypeError(f"Expected {wrapper_type}, got {type(record)}.")

    location = WarcLocation(
        file=warc_record.location.key,
        offset=warc_record.location.offset,
        length=warc_record.location.length,
    )
    return record.wrapped, location


class _SerpArcWarcRecord(_WrapperArcWarcRecord[Serp]):
    pass


def _download_serp_warc(
        config: Config,
        serp: Serp,
) -> Iterable[_SerpArcWarcRecord]:
    if serp.capture.status_code != 200:
        return
    memento_api = MementoApi(
        api_url=serp.archive.memento_api_url,
        session=config.http.session,
    )
    try:
        records = memento_api.load_url_warc(
            url=serp.capture.url,
            timestamp=serp.capture.timestamp,
            raw=True,
        )
    except RequestsConnectionError:
        warn(RuntimeWarning(
            f"Connection error while downloading WARC "
            f"for capture URL {serp.capture.url} at {serp.capture.timestamp}."
        ))
        return
    for record in records:
        yield _SerpArcWarcRecord(serp, record)


def download_serps_warc(config: Config) -> None:
    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(
            Term(capture__status_code=200) &
            ~Term(warc_downloader__should_download=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={}) |
            RankFeature(field="provider.priority", saturation={}) |
            FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()

    if num_changed_serps <= 0:
        echo("No new/changed SERPs.")
        return

    changed_serps: Iterable[Serp] = (
        changed_serps_search
        # Downloading WARCs is very slow, so we keep track
        # of the Elasticsearch query for a full day, assuming that
        # 1000 WARCs can be downloaded in 24h.
        .params(scroll="24h")
        .scan()
    )
    changed_serps = safe_iter_scan(changed_serps)
    # noinspection PyTypeChecker
    changed_serps = tqdm(changed_serps, total=num_changed_serps,
                         desc="Downloading WARCs", unit="SERP")

    # Download from Memento API.
    serp_records = chain.from_iterable(
        _download_serp_warc(config, serp)
        for serp in changed_serps
    )

    # Write to S3.
    stored_records: Iterator[WarcS3Record] = (
        config.s3.warc_store.write(serp_records))
    stored_serps = (
        _unwrap(record, _SerpArcWarcRecord)
        for record in stored_records
    )

    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = str(uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    ))
    actions = (
        update_action(
            serp,
            warc_location=location,
            warc_downloader=InnerDownloader(
                id=downloader_id,
                should_download=False,
                last_downloaded=utc_now(),
            ),
        )
        for serp, location in stored_serps
    )
    config.es.bulk(actions)


class _ResultArcWarcRecord(_WrapperArcWarcRecord[Result]):
    pass


def _capture_timestamp_distance(
        timestamp: datetime) -> Callable[[CdxCapture], float]:
    def _distance(capture: CdxCapture) -> float:
        return abs(timestamp - capture.timestamp).total_seconds()

    return _distance


def _download_result_warc(
        config: Config,
        result: Result,
) -> Iterator[_ResultArcWarcRecord]:
    if result.snippet.url is None:
        return

    cdx_api = CdxApi(
        api_url=result.archive.cdx_api_url,
        session=config.http.session,
    )
    memento_api = MementoApi(
        api_url=result.archive.memento_api_url,
        session=config.http.session,
    )

    capture_timestamp = result.capture.timestamp
    nearest_result_capture_before_serp: CdxCapture | None = min(
        cdx_api.iter_captures(
            result.snippet.url,
            match_type=CdxMatchType.EXACT,
            to_timestamp=capture_timestamp,
        ),
        key=_capture_timestamp_distance(capture_timestamp),
        default=None,
    )
    nearest_result_capture_after_serp: CdxCapture | None = min(
        cdx_api.iter_captures(
            result.snippet.url,
            match_type=CdxMatchType.EXACT,
            from_timestamp=capture_timestamp,
        ),
        key=_capture_timestamp_distance(capture_timestamp),
        default=None,
    )
    if nearest_result_capture_before_serp is None:
        result.update(
            using=config.es.client,
            warc_before_serp_downloader=InnerDownloader(
                should_download=False,
                last_downloaded=utc_now(),
            ).to_dict(),
        )
    else:
        records = memento_api.load_capture_warc(
            capture=nearest_result_capture_before_serp,
            raw=True,
        )
        for record in records:
            yield _ResultArcWarcRecord(result, record)
    if nearest_result_capture_after_serp is None:
        result.update(
            using=config.es.client,
            warc_after_serp_downloader=InnerDownloader(
                should_download=False,
                last_downloaded=utc_now(),
            ).to_dict(),
        )
    else:
        records = memento_api.load_capture_warc(
            capture=nearest_result_capture_after_serp,
            raw=True,
        )
        for record in records:
            yield _ResultArcWarcRecord(result, record)


def download_results_warc(config: Config) -> None:
    changed_results_search: Search = (
        Result.search(using=config.es.client)
        .filter(
            Exists(field="snippet.url") &
            ~Term(should_fetch_captures=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={}) |
            RankFeature(field="provider.priority", saturation={}) |
            FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_results = changed_results_search.count()

    if num_changed_results <= 0:
        echo("No new/changed results.")
        return

    changed_results: Iterable[Result] = changed_results_search.scan()
    changed_results = safe_iter_scan(changed_results)
    # noinspection PyTypeChecker
    changed_results = tqdm(changed_results, total=num_changed_results,
                           desc="Downloading WARCs", unit="result")

    # Download from Memento API.
    result_records = chain.from_iterable(
        _download_result_warc(config, result)
        for result in changed_results
    )

    # Write to S3.
    stored_records: Iterator[WarcS3Record] = (
        config.s3.warc_store.write(result_records))
    stored_results = (
        _unwrap(record, _ResultArcWarcRecord)
        for record in stored_records
    )

    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = str(uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    ))
    actions = (
        update_action(
            result,
            warc_location=location,
            warc_downloader=InnerDownloader(
                id=downloader_id,
                should_download=False,
                last_downloaded=utc_now(),
            ),
        )
        for result, location in stored_results
    )
    config.es.bulk(actions)
