from dataclasses import dataclass
from datetime import datetime
from itertools import chain, islice
from json import JSONEncoder, JSONDecoder
from pathlib import Path
from re import (
    compile as re_compile,
    VERBOSE as RE_VERBOSE,
    MULTILINE as RE_MULTILINE,
    DOTALL as RE_DOTALL,
)
from typing import Iterable, Iterator, TypeVar, Generic, Type, Callable, Any
from uuid import uuid5
from warnings import warn

from click import echo
from elasticsearch_dsl import Document, Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature

# from elasticsearch_dsl.query import Exists
from requests import ConnectionError as RequestsConnectionError
from tqdm.auto import tqdm
from warc_cache import WarcCacheStore, WarcCacheRecord
from warc_s3 import WarcS3Store
from warcio.recordloader import ArcWarcRecord as WarcRecord

# from web_archive_api.cdx import CdxApi, CdxMatchType, CdxCapture
from web_archive_api.memento import MementoApi

from archive_query_log import __version__ as app_version
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_DOWNLOADER
from archive_query_log.orm import Serp, InnerDownloader, WarcLocation

# from archive_query_log.orm import Result
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now

_T = TypeVar("_T", bound=Document)


_PATTERN_ISO_FORMAT = re_compile(
    r"\d{4}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d\.\d+([+-][0-2]\d:[0-5]\d|Z)"
)

_PATTERN_WHITESPACE = re_compile(
    r"[ \t\n\r]*", flags=RE_VERBOSE | RE_MULTILINE | RE_DOTALL
)


class _JsonEncoder(JSONEncoder):
    def default(self, object: Any) -> str | Any:
        if isinstance(object, datetime):
            return object.isoformat()
        return super().default(object)


_JSON_ENCODER = _JsonEncoder()


class _JsonDecoder(JSONDecoder):
    def _decode_isoformat(self, object: Any) -> Any:
        if isinstance(object, str) and _PATTERN_ISO_FORMAT.match(object):
            return datetime.fromisoformat(object)
        if isinstance(object, list):
            return [self._decode_isoformat(value) for value in object]
        if isinstance(object, dict):
            return {key: self._decode_isoformat(value) for key, value in object.items()}
        return object

    def decode(self, string: str, _w=_PATTERN_WHITESPACE.match) -> Any:
        obj = super().decode(string, _w)
        obj = self._decode_isoformat(obj)
        return obj


_JSON_DECODER = _JsonDecoder()


class _WrapperWarcRecord(WarcRecord, Generic[_T]):
    _wrapped_type: Type[_T]

    def __init__(self, record: WarcRecord, wrapped: _T | Type[_T]) -> None:
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
        if isinstance(wrapped, type):
            self._wrapped_type = wrapped
        else:
            self._wrapped_type = type(wrapped)
            self.rec_headers["WARC-Wrapped"] = _JSON_ENCODER.encode(
                wrapped.to_dict(include_meta=True)
            )

    @property
    def wrapped(self) -> _T:
        data = _JSON_DECODER.decode(self.rec_headers["WARC-Wrapped"])
        wrapped = self._wrapped_type.from_es(data)
        return wrapped


class _AnnotatedWarcRecord(WarcRecord, Generic[_T]):
    annotation: _T

    def __init__(self, record: WarcRecord, annotation: _T) -> None:
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
        self.annotation = annotation


class _SerpWrapperWarcRecord(_WrapperWarcRecord[Serp]):
    pass


def _download_serp_warc(
    config: Config,
    serp: Serp,
) -> Iterable[_SerpWrapperWarcRecord]:
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
        warn(
            RuntimeWarning(
                f"Connection error while downloading WARC "
                f"for capture URL {serp.capture.url} at {serp.capture.timestamp}."
            )
        )
        return
    for record in records:
        yield _SerpWrapperWarcRecord(record, serp)


def download_serps_warc(config: Config, prefetch_limit: int | None = None) -> None:
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Term(capture__status_code=200)
            & ~Term(warc_downloader__should_download=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()

    if num_changed_serps <= 0:
        echo("No new/changed SERPs.")
        return

    changed_serps: Iterable[Serp] = changed_serps_search.params(
        preserve_order=True
    ).scan()
    changed_serps = safe_iter_scan(changed_serps)

    if prefetch_limit is not None:
        num_changed_serps = min(num_changed_serps, prefetch_limit)
        changed_serps = tqdm(changed_serps, total=num_changed_serps, desc="Pre-fetching SERPs", unit="SERP")
        changed_serps = iter(list(islice(changed_serps, prefetch_limit)))
        
    # noinspection PyTypeChecker
    changed_serps = tqdm(
        changed_serps, total=num_changed_serps, desc="Downloading WARCs", unit="SERP"
    )

    # Download from Memento API.
    serp_records: Iterable[_SerpWrapperWarcRecord] = chain.from_iterable(
        _download_serp_warc(config, serp) for serp in changed_serps
    )

    # Write to cache.
    locations: Iterator[WarcCacheRecord] = config.warc_cache.store_serps.write(
        serp_records
    )
    # Consume iterator to write to cache.
    for _ in locations:
        pass


_R = TypeVar("_R", bound=WarcRecord)


@dataclass(frozen=True)
class _WithClearCallback(Generic[_T]):
    payload: _T
    clear: Callable[[], None]


def _iter_cached_records(
    warc_store: WarcCacheStore,
) -> Iterator[_WithClearCallback[WarcRecord]]:
    """
    Re-iterate the cached records from the WARC cache and keep track of the cache files that were completely read.
    A clear callback is provided to remove the completely read cache files.
    """

    completed_paths: list[Path] = []

    def _clear() -> None:
        if len(completed_paths) > 0:
            print(f"Clearing {len(completed_paths)} cached files.")
        while len(completed_paths) > 0:
            path = completed_paths[0]
            if path.exists():
                path.unlink()
            completed_paths.remove(path)

    last_path: Path | None = None
    for cache_record in warc_store.read_all():
        record = cache_record.record

        path = warc_store.cache_dir_path / cache_record.location.key

        yield _WithClearCallback(record, _clear)

        if last_path is not None and last_path != path:
            completed_paths.append(last_path)
        last_path = path

    # Ensure last cache file is added to completed paths after all records have been iterated.
    if last_path is not None:
        completed_paths.append(last_path)


def _iter_wrapped_records(
    records: Iterable[_WithClearCallback[WarcRecord]],
    wrapped_type: Type[_T],
) -> Iterator[_WithClearCallback[_WrapperWarcRecord[_T]]]:
    """
    Interpret the WARC records as wrapped records with a payload of a specific document type in its WARC-Wrapped header.
    For example, a WARC record might contain a SERP document in its WARC-Wrapped header, which we later use to update the corresponding SERP on Elasticsearch.
    """

    for record_with_callback in records:
        yield _WithClearCallback(
            payload=_WrapperWarcRecord(
                record=record_with_callback.payload,
                wrapped=wrapped_type,
            ),
            clear=record_with_callback.clear,
        )


def _iter_annotated_records(
    records: Iterable[_WithClearCallback[_WrapperWarcRecord[_T]]],
) -> Iterator[_AnnotatedWarcRecord[_WithClearCallback[_T]]]:
    """
    Convert the wrapped records (with a visible WARC header) to "annotated" records (where the payload is opaque to the actual WARC record).
    This is useful for storing the records in S3, where the WARC-Wrapped header should be removed. But still, we need to keep track of the payload for later use.
    """

    for record in records:
        document = record.payload.wrapped
        del record.payload.rec_headers["WARC-Wrapped"]

        yield _AnnotatedWarcRecord(
            record=record.payload,
            annotation=_WithClearCallback(
                payload=document,
                clear=record.clear,
            ),
        )


def _iter_s3_stored_records(
    records: Iterable[_AnnotatedWarcRecord[_WithClearCallback[_T]]],
    warc_store: WarcS3Store,
    document_type: Type[_T],
) -> Iterator[tuple[_T, WarcLocation]]:
    """
    Store the annotated records in S3 and yield the stored documents with their corresponding locations on S3.
    """

    stored_records = warc_store.write(records)

    last_key: str | None = None
    last_clear: Callable[[], None] | None = None
    for stored_record in stored_records:
        location = WarcLocation(
            file=stored_record.location.key,
            offset=stored_record.location.offset,
            length=stored_record.location.length,
        )

        record = stored_record.record
        if not isinstance(record, _AnnotatedWarcRecord):
            raise TypeError(f"Expected {_AnnotatedWarcRecord}, got {type(record)}.")

        annotation = record.annotation
        if not isinstance(annotation, _WithClearCallback):
            raise TypeError(f"Expected _WithClearCallback, got {type(annotation)}.")

        document = annotation.payload
        clear = annotation.clear
        if not isinstance(document, document_type):
            raise TypeError(f"Expected {document_type}, got {type(document)}.")

        yield document, location

        # Clear cache file after storing in S3.
        current_key = stored_record.location.key
        if last_key is None:
            last_key = current_key
        elif last_key != current_key:
            clear()
            last_key = current_key
            last_clear = None
        last_clear = clear

    # Ensure last cache file is cleared after all records have been iterated.
    if last_clear is not None:
        last_clear()


def upload_serps_warc(config: Config) -> None:
    # Read from cache.
    cached_records = _iter_cached_records(warc_store=config.warc_cache.store_serps)

    # Parse wrapped records (document visible in a WARC header).
    wrapped_records = _iter_wrapped_records(
        records=cached_records,
        wrapped_type=Serp,
    )

    # Transform to annotated records (document opaque to the actual WARC record).
    annotated_records = _iter_annotated_records(
        records=wrapped_records,
    )

    # Write to S3.
    stored_serps = _iter_s3_stored_records(
        records=annotated_records,
        warc_store=config.s3.warc_store,
        document_type=Serp,
    )

    # Get downloader ID.
    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = str(
        uuid5(
            NAMESPACE_WARC_DOWNLOADER,
            ":".join(downloader_id_components),
        )
    )

    # Update Elasticsearch.
    actions = (
        update_action(
            document=serp,
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


# class _ResultArcWarcRecord(_WrapperWarcRecord[Result]):
#     pass


# def _capture_timestamp_distance(timestamp: datetime) -> Callable[[CdxCapture], float]:
#     def _distance(capture: CdxCapture) -> float:
#         return abs(timestamp - capture.timestamp).total_seconds()

#     return _distance


# def _download_result_warc(
#     config: Config,
#     result: Result,
# ) -> Iterator[_ResultArcWarcRecord]:
#     if result.snippet.url is None:
#         return

#     cdx_api = CdxApi(
#         api_url=result.archive.cdx_api_url,
#         session=config.http.session,
#     )
#     memento_api = MementoApi(
#         api_url=result.archive.memento_api_url,
#         session=config.http.session,
#     )

#     capture_timestamp = result.capture.timestamp
#     nearest_result_capture_before_serp: CdxCapture | None = min(
#         cdx_api.iter_captures(
#             result.snippet.url,
#             match_type=CdxMatchType.EXACT,
#             to_timestamp=capture_timestamp,
#         ),
#         key=_capture_timestamp_distance(capture_timestamp),
#         default=None,
#     )
#     nearest_result_capture_after_serp: CdxCapture | None = min(
#         cdx_api.iter_captures(
#             result.snippet.url,
#             match_type=CdxMatchType.EXACT,
#             from_timestamp=capture_timestamp,
#         ),
#         key=_capture_timestamp_distance(capture_timestamp),
#         default=None,
#     )
#     if nearest_result_capture_before_serp is None:
#         result.update(
#             using=config.es.client,
#             index=config.es.index_results,
#             warc_before_serp_downloader=InnerDownloader(
#                 should_download=False,
#                 last_downloaded=utc_now(),
#             ).to_dict(),
#         )
#     else:
#         records = memento_api.load_capture_warc(
#             capture=nearest_result_capture_before_serp,
#             raw=True,
#         )
#         for record in records:
#             yield _ResultArcWarcRecord(result, record)
#     if nearest_result_capture_after_serp is None:
#         result.update(
#             using=config.es.client,
#             index=config.es.index_results,
#             warc_after_serp_downloader=InnerDownloader(
#                 should_download=False,
#                 last_downloaded=utc_now(),
#             ).to_dict(),
#         )
#     else:
#         records = memento_api.load_capture_warc(
#             capture=nearest_result_capture_after_serp,
#             raw=True,
#         )
#         for record in records:
#             yield _ResultArcWarcRecord(result, record)


# def download_results_warc(config: Config) -> None:
#     changed_results_search: Search = (
#         Result.search(using=config.es.client, index=config.es.index_results)
#         .filter(Exists(field="snippet.url") & ~Term(should_fetch_captures=False))
#         .query(
#             RankFeature(field="archive.priority", saturation={})
#             | RankFeature(field="provider.priority", saturation={})
#             | FunctionScore(functions=[RandomScore()])
#         )
#     )
#     num_changed_results = changed_results_search.count()

#     if num_changed_results <= 0:
#         echo("No new/changed results.")
#         return

#     changed_results: Iterable[Result] = changed_results_search.scan()
#     changed_results = safe_iter_scan(changed_results)
#
#     if prefetch_limit is not None:
#         num_changed_results = min(num_changed_results, prefetch_limit)
#         changed_results = tqdm(changed_results, total=num_changed_results, desc="Pre-fetching results", unit="result")
#         changed_results = iter(list(islice(changed_results, prefetch_limit)))
#
#     # noinspection PyTypeChecker
#     changed_results = tqdm(
#         changed_results,
#         total=num_changed_results,
#         desc="Downloading WARCs",
#         unit="result",
#     )

#     # Download from Memento API.
#     result_records = chain.from_iterable(
#         _download_result_warc(config, result) for result in changed_results
#     )

#     # Write to S3.
#     stored_records: Iterator[WarcS3Record] = config.s3.warc_store.write(result_records)
#     stored_results = (
#         _unwrap(record, _ResultArcWarcRecord) for record in stored_records
#     )

#     downloader_id_components = (
#         config.s3.endpoint_url,
#         config.s3.bucket_name,
#         app_version,
#     )
#     downloader_id = str(
#         uuid5(
#             NAMESPACE_WARC_DOWNLOADER,
#             ":".join(downloader_id_components),
#         )
#     )
#     actions = (
#         update_action(
#             result,
#             warc_location=location,
#             warc_downloader=InnerDownloader(
#                 id=downloader_id,
#                 should_download=False,
#                 last_downloaded=utc_now(),
#             ),
#         )
#         for result, location in stored_results
#     )
#     config.es.bulk(actions)
