from typing import Iterable, Iterator, Final
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script
from tqdm.auto import tqdm
from warc_s3 import WarcS3Record
from warcio.recordloader import ArcWarcRecord
from web_archive_api.memento import MementoApi

from archive_query_log import __version__ as app_version
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_DOWNLOADER
from archive_query_log.orm import Serp, InnerDownloader, WarcLocation
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


class _SerpArcWarcRecord(ArcWarcRecord):
    serp: Final[Serp]

    def __init__(self, serp: Serp, record: ArcWarcRecord):
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
        self.serp = serp


def _download_warc(config: Config, serp: Serp) -> Iterator[_SerpArcWarcRecord]:
    memento_api = MementoApi(
        api_url=serp.archive.memento_api_url,
        session=config.http.session,
    )
    records = memento_api.load_url_warc(
        url=serp.capture.url,
        timestamp=serp.capture.timestamp,
        raw=True,
    )
    serp_records = (
        _SerpArcWarcRecord(serp, record)
        for record in records
    )
    yield from serp_records


def _download_warcs(
        config: Config,
        serps_: Iterable[Serp],
) -> Iterator[_SerpArcWarcRecord]:
    for serp in serps_:
        yield from _download_warc(config, serp)


def _stored_serp(warc_record: WarcS3Record) -> tuple[Serp, WarcLocation]:
    record: ArcWarcRecord = warc_record.record
    if not isinstance(record, _SerpArcWarcRecord):
        raise TypeError(f"Expected _SerpArcWarcRecord, got {type(record)}.")

    location = WarcLocation(
        file=warc_record.location.key,
        offset=warc_record.location.offset,
        length=warc_record.location.length,
    )
    return record.serp, location


def download_serps_warc(config: Config) -> None:
    start_time = utc_now()
    downloader_id_components = (
        config.s3.endpoint_url,
        config.s3.bucket_name,
        app_version,
    )
    downloader_id = str(uuid5(
        NAMESPACE_WARC_DOWNLOADER,
        ":".join(downloader_id_components),
    ))
    downloader = InnerDownloader(
        id=downloader_id,
        last_downloaded=start_time,
    )

    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="warc_downloader.last_downloaded") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['warc_downloader.last_downloaded']"
                       ".isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['warc_downloader.last_downloaded'].value"
                       ")",
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_serps = (
        changed_serps_search.extra(track_total_hits=True)
        .execute().hits.total.value)

    if num_changed_serps <= 0:
        echo("No new/changed captures.")
        return

    changed_serps: Iterable[Serp] = changed_serps_search.scan()
    changed_serps = safe_iter_scan(changed_serps)
    # noinspection PyTypeChecker
    changed_serps = tqdm(changed_serps, total=num_changed_serps,
                         desc="Downloading WARCs", unit="SERP")

    # Download from Memento API.
    serp_records = _download_warcs(config, changed_serps)

    # Write to S3.
    stored_records: Iterator[WarcS3Record] = (
        config.s3.warc_store.write(serp_records))
    stored_serps = (_stored_serp(record) for record in stored_records)

    actions = (
        update_action(
            serp,
            warc_location=location,
            warc_downloader=downloader,
        )
        for serp, location in stored_serps
    )
    config.es.bulk(actions)
