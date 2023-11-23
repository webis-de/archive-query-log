from itertools import chain
from typing import Iterable, Iterator, Final, TypeVar, Generic, Type
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Term, RankFeature
from tqdm.auto import tqdm
from warc_s3 import WarcS3Record
from warcio.recordloader import ArcWarcRecord
from web_archive_api.cdx import CdxApi, CdxMatchType
from web_archive_api.memento import MementoApi

from archive_query_log import __version__ as app_version
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_DOWNLOADER
from archive_query_log.orm import Serp, InnerDownloader, WarcLocation, Result
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now

_T = TypeVar("_T")


class _WrapperArcWarcRecord(ArcWarcRecord, Generic[_T]):
    wrapped: Final[_T]

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
    records = memento_api.load_url_warc(
        url=serp.capture.url,
        timestamp=serp.capture.timestamp,
        raw=True,
    )
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
