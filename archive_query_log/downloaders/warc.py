from dataclasses import dataclass
from itertools import chain
from json import loads, dumps
from pathlib import Path
from typing import Iterable, Iterator, TypeVar, Generic, Type, Callable, cast
from uuid import uuid5
from warnings import warn

from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature

from elasticsearch_dsl.query import Exists
from requests import ConnectionError as RequestsConnectionError
from tqdm.auto import tqdm
from warc_cache import WarcCacheStore, WarcCacheRecord
from warc_s3 import WarcS3Store, WarcS3Record
from warcio.recordloader import ArcWarcRecord
from web_archive_api.memento import MementoApi

from archive_query_log import __version__ as app_version
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_DOWNLOADER
from archive_query_log.orm import (
    Serp,
    InnerDownloader,
    WarcLocation,
    WebSearchResultBlock,
    UuidBaseDocument,
)
from archive_query_log.utils.time import utc_now


_D = TypeVar("_D", bound=UuidBaseDocument)


class _WrapperWarcRecord(ArcWarcRecord, Generic[_D]):
    _wrapped_type: Type[_D]

    def __init__(self, record: ArcWarcRecord, wrapped: _D | Type[_D]) -> None:
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
            self.rec_headers["WARC-Wrapped"] = dumps(wrapped.to_dict(include_meta=True))

    @property
    def wrapped(self) -> _D:
        wrapped = self._wrapped_type.from_es(loads(self.rec_headers["WARC-Wrapped"]))
        return wrapped


_T = TypeVar("_T")


class _AnnotatedWarcRecord(ArcWarcRecord, Generic[_T]):
    annotation: _T

    def __init__(self, record: ArcWarcRecord, annotation: _T) -> None:
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


def _download_serp_warc(
    config: Config,
    serp: Serp,
) -> Iterable[_WrapperWarcRecord[UuidBaseDocument]]:
    if serp.capture.status_code != 200:
        return
    memento_api = MementoApi(
        api_url=serp.archive.memento_api_url.encoded_string(),
        session=config.http.session,
    )
    try:
        records = memento_api.load_url_warc(
            url=serp.capture.url.encoded_string(),
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

    # Only keep the meta fields of the SERP, as the source is not needed for updating it.
    pseudo_serp = UuidBaseDocument(
        id=serp.id,
        index=serp.index,
        seq_no=serp.seq_no,
    )

    for record in records:
        yield _WrapperWarcRecord(record, pseudo_serp)


def download_serps_warc(config: Config, size: int = 10) -> None:
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
        print("No new/changed SERPs.")
        return

    changed_serps: Iterable[Serp] = changed_serps_search.params(size=size).execute()

    changed_serps = tqdm(
        changed_serps, total=num_changed_serps, desc="Downloading WARCs", unit="SERP"
    )

    # Download from Memento API.
    downloaded_records: Iterable[_WrapperWarcRecord[UuidBaseDocument]] = (
        chain.from_iterable(_download_serp_warc(config, serp) for serp in changed_serps)
    )

    # Write to cache.
    locations: Iterator[WarcCacheRecord] = config.warc_cache.store_serps.write(
        downloaded_records
    )
    # Consume iterator to write to cache.
    for _ in locations:
        pass


@dataclass(frozen=True)
class _WithClearCallback(Generic[_T]):
    payload: _T
    clear: Callable[[], None]


def _iter_cached_records(
    warc_store: WarcCacheStore,
) -> Iterator[_WithClearCallback[ArcWarcRecord]]:
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

        if last_path is not None and last_path != path:
            print(f"Read WARC cache file: {path}")

        yield _WithClearCallback(record, _clear)

        if last_path is not None and last_path != path:
            completed_paths.append(last_path)
        last_path = path

    # Ensure last cache file is added to completed paths after all records have been iterated.
    if last_path is not None:
        completed_paths.append(last_path)


def _iter_wrapped_records(
    records: Iterable[_WithClearCallback[ArcWarcRecord]],
    wrapped_type: Type[_D],
) -> Iterator[_WithClearCallback[_WrapperWarcRecord[_D]]]:
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
    records: Iterable[_WithClearCallback[_WrapperWarcRecord[_D]]],
) -> Iterator[_AnnotatedWarcRecord[_WithClearCallback[_D]]]:
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
    records: Iterable[_AnnotatedWarcRecord[_WithClearCallback[_D]]],
    warc_store: WarcS3Store,
    document_type: Type[_D],
) -> Iterator[tuple[_D, WarcLocation]]:
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
        wrapped_type=UuidBaseDocument,
    )

    # Transform to annotated records (document opaque to the actual WARC record).
    annotated_records = _iter_annotated_records(
        records=wrapped_records,
    )

    # Write to S3.
    stored_serps = _iter_s3_stored_records(
        records=annotated_records,
        warc_store=config.s3.warc_s3_store,
        document_type=UuidBaseDocument,
    )

    # Get downloader ID.
    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    )

    # Update Elasticsearch.
    actions = (
        serp.update_action(
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


def _download_web_search_result_block_warc_before_serp(
    config: Config,
    result_block: WebSearchResultBlock,
) -> Iterator[_AnnotatedWarcRecord[WebSearchResultBlock]]:
    if result_block.capture_before_serp is None:
        return

    # Get downloader ID.
    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    )

    result_block.warc_downloader_before_serp = InnerDownloader(
        id=downloader_id,
        should_download=False,
        last_downloaded=utc_now(),
    )
    if result_block.capture_before_serp.status_code != 200:
        result_block.update(
            using=config.es.client,
            index=config.es.index_web_search_result_blocks,
        )
        return

    memento_api = MementoApi(
        api_url=result_block.archive.memento_api_url.encoded_string(),
        session=config.http.session,
    )

    try:
        records = memento_api.load_url_warc(
            url=result_block.capture_before_serp.url.encoded_string(),
            timestamp=result_block.capture_before_serp.timestamp,
            raw=True,
        )
    except RequestsConnectionError:
        warn(
            RuntimeWarning(
                f"Connection error while downloading WARC "
                f"for capture URL {result_block.capture_before_serp.url} at {result_block.capture_before_serp.timestamp}."
            )
        )
        return

    for record in records:
        yield _AnnotatedWarcRecord(record, result_block)


def _download_web_search_result_block_warc_after_serp(
    config: Config,
    result_block: WebSearchResultBlock,
) -> Iterator[_AnnotatedWarcRecord[WebSearchResultBlock]]:
    if result_block.capture_after_serp is None:
        return

    # Get downloader ID.
    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    )

    result_block.warc_downloader_after_serp = InnerDownloader(
        id=downloader_id,
        should_download=False,
        last_downloaded=utc_now(),
    )
    if result_block.capture_after_serp.status_code != 200:
        result_block.update(
            using=config.es.client,
            index=config.es.index_web_search_result_blocks,
        )
        return

    memento_api = MementoApi(
        api_url=result_block.archive.memento_api_url.encoded_string(),
        session=config.http.session,
    )

    try:
        records = memento_api.load_url_warc(
            url=result_block.capture_after_serp.url.encoded_string(),
            timestamp=result_block.capture_after_serp.timestamp,
            raw=True,
        )
    except RequestsConnectionError:
        warn(
            RuntimeWarning(
                f"Connection error while downloading WARC "
                f"for capture URL {result_block.capture_after_serp.url} at {result_block.capture_after_serp.timestamp}."
            )
        )
        return

    for record in records:
        yield _AnnotatedWarcRecord(record, result_block)


def _unwrap_records(
    record: Iterable[WarcS3Record], wrapper_type: Type[_D]
) -> Iterator[tuple[_D, WarcLocation]]:
    for stored_record in record:
        location = WarcLocation(
            file=stored_record.location.key,
            offset=stored_record.location.offset,
            length=stored_record.location.length,
        )

        annotated_record = cast(_AnnotatedWarcRecord[_D], stored_record.record)
        annotation = annotated_record.annotation
        yield annotation, location


def download_web_search_result_block_warc_before_serp(
    config: Config, size: int = 10
) -> None:
    changed_result_blocks_search: Search = (
        WebSearchResultBlock.search(
            using=config.es.client, index=config.es.index_web_search_result_blocks
        )
        .filter(
            Exists(field="capture_before_serp.url")
            & Term(capture_before_serp__status_code=200)
            & ~Term(warc_downloader_before_serp__should_download=False)
        )
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

    changed_result_blocks: Iterable[WebSearchResultBlock] = (
        changed_result_blocks_search.params(size=size).execute()
    )

    changed_result_blocks = tqdm(
        changed_result_blocks,
        total=num_changed_result_blocks,
        desc="Downloading WARCs",
        unit="web search result block",
    )

    # Download from Memento API.
    downloaded_records = chain.from_iterable(
        _download_web_search_result_block_warc_before_serp(
            config=config,
            result_block=result_block,
        )
        for result_block in changed_result_blocks
    )

    # Write to S3.
    stored_records: Iterator[WarcS3Record] = config.s3.warc_s3_store.write(
        downloaded_records
    )
    stored_result_blocks = _unwrap_records(stored_records, WebSearchResultBlock)

    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    )
    actions = (
        result_block.update_action(
            warc_location=location,
            warc_downloader=InnerDownloader(
                id=downloader_id,
                should_download=False,
                last_downloaded=utc_now(),
            ),
        )
        for result_block, location in stored_result_blocks
    )
    config.es.bulk(actions)


def download_web_search_result_block_warc_after_serp(
    config: Config, size: int = 10
) -> None:
    changed_result_blocks_search: Search = (
        WebSearchResultBlock.search(
            using=config.es.client, index=config.es.index_web_search_result_blocks
        )
        .filter(
            Exists(field="capture_after_serp.url")
            & Term(capture_after_serp__status_code=200)
            & ~Term(warc_downloader_after_serp__should_download=False)
        )
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

    changed_result_blocks: Iterable[WebSearchResultBlock] = (
        changed_result_blocks_search.params(size=size).execute()
    )

    changed_result_blocks = tqdm(
        changed_result_blocks,
        total=num_changed_result_blocks,
        desc="Downloading WARCs",
        unit="web search result block",
    )

    # Download from Memento API.
    downloaded_records = chain.from_iterable(
        _download_web_search_result_block_warc_after_serp(
            config=config,
            result_block=result_block,
        )
        for result_block in changed_result_blocks
    )

    # Write to S3.
    stored_records: Iterator[WarcS3Record] = config.s3.warc_s3_store.write(
        downloaded_records
    )
    stored_result_blocks = _unwrap_records(stored_records, WebSearchResultBlock)

    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    )
    actions = (
        result_block.update_action(
            warc_location=location,
            warc_downloader=InnerDownloader(
                id=downloader_id,
                should_download=False,
                last_downloaded=utc_now(),
            ),
        )
        for result_block, location in stored_result_blocks
    )
    config.es.bulk(actions)
