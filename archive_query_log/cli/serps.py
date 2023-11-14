from datetime import datetime
from itertools import chain
from typing import Iterable, Iterator, Any, Final
from warnings import warn

from click import group, echo
from elasticsearch import ConnectionTimeout
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script, Term
from tqdm.auto import tqdm
from warc_s3 import WarcS3Record
from warcio.recordloader import ArcWarcRecord
from web_archive_api.memento import MementoApi

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Capture, Serp, InnerCapture, InnerParser, \
    UrlQueryParser, Provider
from archive_query_log.parse.url_query import parse_url_query as \
    _parse_url_query
from archive_query_log.utils.es import safe_iter_scan
from archive_query_log.utils.time import utc_now


@group()
def serps():
    pass




@serps.group()
def parse():
    pass


def _provider_url_query_parsers(
        config: Config,
        provider: Provider,
) -> list[UrlQueryParser]:
    parsers: Iterable[UrlQueryParser] = (
        UrlQueryParser.search(using=config.es.client)
        .filter(Term(provider__id=provider.id))
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_save_serp(
        config: Config,
        capture: Capture,
        query_parsers: list[UrlQueryParser],
        start_time: datetime,
) -> None:
    # Re-check if parsing is necessary.
    if (capture.url_query_parser is not None and
            capture.url_query_parser.last_parsed is not None and
            capture.url_query_parser.last_parsed > capture.last_modified):
        return

    for parser in query_parsers:
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
        )
        serp.save(using=config.es.client)
        capture.update(
            using=config.es.client,
            retry_on_conflict=3,
            url_query_parser=url_query_parser.to_dict(),
        )
        return
    return

@parse.command("url-query")
@pass_config
def parse_url_query(config: Config) -> None:
    Serp.init(using=config.es.client)

    providers_search: Search = (
        Provider.search(using=config.es.client)
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_providers = (
        providers_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    providers: Iterable[Provider] = providers_search.scan()
    providers = safe_iter_scan(providers)
    # noinspection PyTypeChecker
    providers = tqdm(providers, total=num_providers, desc="Parsing URL query",
                     unit="provider")

    for provider in providers:
        parsers = _provider_url_query_parsers(config, provider)
        changed_captures_search: Search = (
            Capture.search(using=config.es.client)
            .filter(
                Term(provider__id=provider.id) &
                (
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
                _parse_save_serp(
                    config=config,
                    capture=capture,
                    query_parsers=parsers,
                    start_time=utc_now(),
                )
            Capture.index().refresh(using=config.es.client)
        else:
            echo("No new/changed captures.")

