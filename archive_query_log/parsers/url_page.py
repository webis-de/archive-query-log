from abc import ABC, abstractmethod
from functools import cached_property
from itertools import chain
from typing import Iterable, Iterator, Pattern, Annotated, Sequence
from uuid import uuid5, UUID

from annotated_types import Gt
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature
from pydantic import BaseModel
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_PAGE_PARSER
from archive_query_log.orm import Serp, InnerParser
from archive_query_log.parsers.url import (
    parse_url_query_parameter,
    parse_url_fragment_parameter,
    parse_url_path_segment,
)
from archive_query_log.parsers.util import clean_int
from archive_query_log.utils.time import utc_now


class UrlPageParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None
    priority: Annotated[float, Gt(0)] | None = None
    remove_pattern: Pattern | None = None
    space_pattern: Pattern | None = None

    @cached_property
    def id(self) -> UUID:
        parser_id_components = (
            str(self.provider_id) if self.provider_id is not None else "",
            str(self.url_pattern) if self.url_pattern is not None else "",
            str(self.priority) if self.priority is not None else "",
        )
        return uuid5(
            NAMESPACE_URL_PAGE_PARSER,
            ":".join(parser_id_components),
        )

    @cached_property
    def inner_parser(self) -> InnerParser:
        return InnerParser(
            id=self.id,
            should_parse=True,
            last_parsed=None,
        )

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

    @abstractmethod
    def parse(self, serp: Serp) -> int | None: ...


class QueryParameterUrlPageParser(UrlPageParser):
    parameter: str

    def parse(self, serp: Serp) -> int | None:
        page_string = parse_url_query_parameter(self.parameter, serp.capture.url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=self.remove_pattern,
        )


class FragmentParameterUrlPageParser(UrlPageParser):
    parameter: str

    def parse(self, serp: Serp) -> int | None:
        page_string = parse_url_fragment_parameter(self.parameter, serp.capture.url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=self.remove_pattern,
        )


class PathSegmentUrlPageParser(UrlPageParser):
    segment: int

    def parse(self, serp: Serp) -> int | None:
        page_string = parse_url_path_segment(self.segment, serp.capture.url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=self.remove_pattern,
        )


# TODO: Add actual parsers.
URL_PAGE_PARSERS: Sequence[UrlPageParser] = NotImplemented


def _parse_serp_url_page_action(serp: Serp) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (
        serp.url_page_parser is not None
        and serp.url_page_parser.should_parse is not None
        and not serp.url_page_parser.should_parse
    ):
        return

    for parser in URL_PAGE_PARSERS:
        if not parser.is_applicable(serp):
            continue
        url_page = parser.parse(serp)
        if url_page is None:
            # Parsing was not successful.
            continue
        yield serp.update_action(
            url_page=url_page,
            url_page_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        url_page_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_url_page(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(~Term(url_page_parser__should_parse=False))
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
            changed_serps, total=num_changed_serps, desc="Parsing URL page", unit="SERP"
        )
        actions = chain.from_iterable(
            _parse_serp_url_page_action(serp) for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")
