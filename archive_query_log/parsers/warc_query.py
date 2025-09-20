from abc import ABC, abstractmethod
from functools import cached_property
from itertools import chain
from typing import Iterable, Iterator, Pattern, Annotated, Sequence
from uuid import uuid5, UUID

from annotated_types import Gt
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from pydantic import BaseModel
from tqdm.auto import tqdm
from warc_s3 import WarcS3Store

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_QUERY_PARSER
from archive_query_log.orm import (
    Serp,
    InnerParser,
)
from archive_query_log.parsers.util import clean_text
from archive_query_log.parsers.warc import open_warc
from archive_query_log.parsers.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.time import utc_now


class WarcQueryParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None
    priority: Annotated[float, Gt(0)] | None = None
    remove_pattern: Pattern | None = None
    space_pattern: Pattern | None = None

    def is_applicable(self, serp: Serp) -> bool:
        # Check if provider matches.
        if self.provider_id is not None and self.provider_id != serp.provider.id:
            return False

        # Check if URL matches pattern.
        if self.url_pattern is not None and not self.url_pattern.match(
            serp.capture.url.encoded_string()
        ):
            return False
        return True

    @cached_property
    def id(self) -> UUID:
        parser_id_components = (
            str(self.provider_id) if self.provider_id is not None else "",
            str(self.url_pattern) if self.url_pattern is not None else "",
            str(self.priority) if self.priority is not None else "",
        )
        return uuid5(
            NAMESPACE_WARC_QUERY_PARSER,
            ":".join(parser_id_components),
        )

    @cached_property
    def inner_parser(self) -> InnerParser:
        return InnerParser(
            id=self.id,
            should_parse=True,
            last_parsed=None,
        )

    @abstractmethod
    def parse(self, serp: Serp, warc_store: WarcS3Store) -> str | None: ...


class XpathWarcQueryParser(WarcQueryParser):
    xpath: str

    def parse(self, serp: Serp, warc_store: WarcS3Store) -> str | None:
        if serp.warc_location is None:
            return None

        with open_warc(warc_store, serp.warc_location) as record:
            tree = parse_xml_tree(record)
        if tree is None:
            return None

        queries = safe_xpath(tree, self.xpath, str)
        for query in queries:
            query_cleaned = clean_text(
                text=query,
                remove_pattern=self.remove_pattern,
                space_pattern=self.space_pattern,
            )
            if query_cleaned is not None:
                return query_cleaned
        return None


# TODO: Add actual parsers.
WARC_QUERY_PARSERS: Sequence[WarcQueryParser] = NotImplemented


def _parse_serp_warc_query_action(
    config: Config,
    serp: Serp,
) -> Iterator[dict]:
    # Re-check if it can be parsed.
    if (
        serp.warc_location is None
        or serp.warc_location.file is None
        or serp.warc_location.offset is None
        or serp.warc_location.length is None
    ):
        return

    # Re-check if parsing is necessary.
    if (
        serp.warc_query_parser is not None
        and serp.warc_query_parser.should_parse is not None
        and not serp.warc_query_parser.should_parse
    ):
        return

    for parser in WARC_QUERY_PARSERS:
        if not parser.is_applicable(serp):
            continue
        warc_query = parser.parse(serp, config.s3.warc_store)
        if warc_query is None:
            # Parsing was not successful.
            continue
        yield serp.update_action(
            warc_query=warc_query,
            warc_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        warc_query_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_query(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location") & ~Term(warc_query_parser__should_parse=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = changed_serps_search.params(size=size).execute()

        changed_serps = tqdm(
            changed_serps,
            total=num_changed_serps,
            desc="Parsing WARC query",
            unit="SERP",
        )
        actions = chain.from_iterable(
            _parse_serp_warc_query_action(config, serp) for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")
