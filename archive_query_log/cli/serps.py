from datetime import datetime
from functools import cache
from typing import Iterable, Iterator, Final
from uuid import uuid5

from click import group, echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script, Term
from tqdm.auto import tqdm
from warc_s3 import WarcS3Record
from warcio.recordloader import ArcWarcRecord
from web_archive_api.memento import MementoApi

from archive_query_log import __version__ as app_version
from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_DOWNLOADER
from archive_query_log.orm import Capture, Serp, InnerCapture, InnerParser, \
    UrlQueryParser, InnerDownloader, WarcLocation, UrlPageParser, \
    UrlOffsetParser
from archive_query_log.parse.url_query import parse_url_query as \
    _parse_url_query
from archive_query_log.parse.url_page import parse_url_page as _parse_url_page
from archive_query_log.parse.url_offset import \
    parse_url_offset as _parse_url_offset
from archive_query_log.utils.es import safe_iter_scan
from archive_query_log.utils.time import utc_now


@group()
def serps():
    pass


@serps.group()
def parse():
    pass


@cache
def _url_query_parsers(
        config: Config,
        provider_id: str,
) -> list[UrlQueryParser]:
    parsers: Iterable[UrlQueryParser] = (
        UrlQueryParser.search(using=config.es.client)
        .filter(Term(provider__id=provider_id))
        .sort("-priority")
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_query(
        config: Config,
        capture: Capture,
        start_time: datetime,
) -> None:
    # Re-check if parsing is necessary.
    if (capture.url_query_parser is not None and
            capture.url_query_parser.last_parsed is not None and
            capture.url_query_parser.last_parsed > capture.last_modified):
        return

    for parser in _url_query_parsers(config, capture.provider.id):
        # Try to parse the query.
        url_query = _parse_url_query(parser, capture.url)
        if url_query is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        url_query_parser = InnerParser(
            id=parser.id,
            last_parsed=start_time,
        )
        serp = Serp(
            archive=capture.archive,
            provider=capture.provider,
            capture=InnerCapture(
                id=capture.id,
                url=capture.url,
                timestamp=capture.timestamp,
                status_code=capture.status_code,
                digest=capture.digest,
                mimetype=capture.mimetype,
            ),
            url_query=url_query,
            url_query_parser=url_query_parser,
            last_modified=start_time,
        )
        serp.save(using=config.es.client)
        capture.update(
            using=config.es.client,
            retry_on_conflict=3,
            url_query_parser=url_query_parser.to_dict(),
        )
        return
    capture.update(
        using=config.es.client,
        retry_on_conflict=3,
        url_query_parser=InnerParser(
            last_parsed=start_time,
        ).to_dict(),
    )
    return


@parse.command("url-query")
@pass_config
def parse_url_query(config: Config) -> None:
    Serp.init(using=config.es.client)
    start_time = utc_now()

    changed_captures_search: Search = (
        Capture.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="url_query_parser.last_parsed") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['url_query_parser.last_parsed']"
                       ".isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['url_query_parser.last_parsed'].value"
                       ")",
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_captures = (
        changed_captures_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    if num_changed_captures > 0:
        changed_captures: Iterable[Capture] = (
            changed_captures_search.params(preserve_order=True).scan())
        changed_captures = safe_iter_scan(changed_captures)
        # noinspection PyTypeChecker
        changed_captures = tqdm(
            changed_captures, total=num_changed_captures,
            desc="Parsing URL query", unit="capture")
        for capture in changed_captures:
            _parse_serp_url_query(
                config=config,
                capture=capture,
                start_time=start_time,
            )
        Capture.index().refresh(using=config.es.client)
    else:
        echo("No new/changed captures.")


@cache
def _url_page_parsers(
        config: Config,
        provider_id: str,
) -> list[UrlPageParser]:
    parsers: Iterable[UrlPageParser] = (
        UrlPageParser.search(using=config.es.client)
        .filter(Term(provider__id=provider_id))
        .sort("-priority")
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_page(
        config: Config,
        serp: Serp,
        start_time: datetime,
) -> None:
    # Re-check if parsing is necessary.
    if (serp.url_page_parser is not None and
            serp.url_page_parser.last_parsed is not None and
            serp.url_page_parser.last_parsed > serp.last_modified):
        return

    for parser in _url_page_parsers(config, serp.provider.id):
        # Try to parse the query.
        url_page = _parse_url_page(parser, serp.capture.url)
        if url_page is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        url_page_parser = InnerParser(
            id=parser.id,
            last_parsed=start_time,
        )
        serp.update(
            using=config.es.client,
            retry_on_conflict=3,
            url_page=url_page,
            url_page_parser=url_page_parser.to_dict(),
        )
        return
    serp.update(
        using=config.es.client,
        retry_on_conflict=3,
        url_page_parser=InnerParser(
            last_parsed=start_time,
        ).to_dict(),
    )
    return


@parse.command("url-page")
@pass_config
def parse_url_page(config: Config) -> None:
    start_time = utc_now()

    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="url_page_parser.last_parsed") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['url_page_parser.last_parsed']"
                       ".isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['url_page_parser.last_parsed'].value"
                       ")",
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_serps = (
        changed_serps_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = (
            changed_serps_search.params(preserve_order=True).scan())
        changed_serps = safe_iter_scan(changed_serps)
        # noinspection PyTypeChecker
        changed_serps = tqdm(
            changed_serps, total=num_changed_serps,
            desc="Parsing URL page", unit="SERP")
        for serp in changed_serps:
            _parse_serp_url_page(
                config=config,
                serp=serp,
                start_time=start_time,
            )
        Serp.index().refresh(using=config.es.client)
    else:
        echo("No new/changed SERPs.")


@cache
def _url_offset_parsers(
        config: Config,
        provider_id: str,
) -> list[UrlOffsetParser]:
    parsers: Iterable[UrlOffsetParser] = (
        UrlOffsetParser.search(using=config.es.client)
        .filter(Term(provider__id=provider_id))
        .sort("-priority")
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_offset(
        config: Config,
        serp: Serp,
        start_time: datetime,
) -> None:
    # Re-check if parsing is necessary.
    if (serp.url_offset_parser is not None and
            serp.url_offset_parser.last_parsed is not None and
            serp.url_offset_parser.last_parsed > serp.last_modified):
        return

    for parser in _url_offset_parsers(config, serp.provider.id):
        # Try to parse the query.
        url_offset = _parse_url_offset(parser, serp.capture.url)
        if url_offset is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        url_offset_parser = InnerParser(
            id=parser.id,
            last_parsed=start_time,
        )
        serp.update(
            using=config.es.client,
            retry_on_conflict=3,
            url_offset=url_offset,
            url_offset_parser=url_offset_parser.to_dict(),
        )
        return
    serp.update(
        using=config.es.client,
        retry_on_conflict=3,
        url_offset_parser=InnerParser(
            last_parsed=start_time,
        ).to_dict(),
    )
    return


@parse.command("url-offset")
@pass_config
def parse_url_offset(config: Config) -> None:
    start_time = utc_now()

    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="url_offset_parser.last_parsed") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['url_offset_parser.last_parsed']"
                       ".isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['url_offset_parser.last_parsed'].value"
                       ")",
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_serps = (
        changed_serps_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = (
            changed_serps_search.params(preserve_order=True).scan())
        changed_serps = safe_iter_scan(changed_serps)
        # noinspection PyTypeChecker
        changed_serps = tqdm(
            changed_serps, total=num_changed_serps,
            desc="Parsing URL offset", unit="SERP")
        for serp in changed_serps:
            _parse_serp_url_offset(
                config=config,
                serp=serp,
                start_time=start_time,
            )
        Serp.index().refresh(using=config.es.client)
    else:
        echo("No new/changed SERPs.")


@serps.group()
def download():
    pass


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


@download.command(help="Download archived documents of captures as WARC.")
@pass_config
def warc(config: Config) -> None:
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

    changed_serps: Iterable[Serp] = (
        changed_serps_search.params(preserve_order=True).scan())
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

    for serp, location in stored_serps:
        serp.update(
            using=config.es.client,
            retry_on_conflict=3,
            warc_location=location.to_dict(),
            warc_downloader=downloader.to_dict(),
        )
    Serp.index().refresh(using=config.es.client)
