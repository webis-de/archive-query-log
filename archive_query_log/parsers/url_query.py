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
from archive_query_log.namespaces import NAMESPACE_URL_QUERY_PARSER
from archive_query_log.orm import (
    Capture,
    Serp,
    InnerCapture,
    InnerParser,
)
from archive_query_log.parsers.utils import clean_text
from archive_query_log.parsers.utils.url import (
    parse_url_query_parameter,
    parse_url_fragment_parameter,
    parse_url_path_segment,
)
from archive_query_log.utils.time import utc_now


class UrlQueryParser(BaseModel, ABC):
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
            NAMESPACE_URL_QUERY_PARSER,
            ":".join(parser_id_components),
        )

    @cached_property
    def inner_parser(self) -> InnerParser:
        return InnerParser(
            id=self.id,
            should_parse=True,
            last_parsed=None,
        )

    def is_applicable(self, capture: Capture) -> bool:
        # Check if provider matches.
        if self.provider_id is not None and self.provider_id != capture.provider.id:
            return False

        # Check if URL matches pattern.
        if self.url_pattern is not None and not self.url_pattern.match(
            capture.url.encoded_string()
        ):
            return False
        return True

    @abstractmethod
    def parse(self, capture: Capture) -> str | None: ...


class QueryParameterUrlQueryParser(UrlQueryParser):
    parameter: str

    def parse(self, capture: Capture) -> str | None:
        query = parse_url_query_parameter(self.parameter, capture.url)
        if query is None:
            return None
        return clean_text(
            text=query,
            remove_pattern=self.remove_pattern,
            space_pattern=self.space_pattern,
        )


class FragmentParameterUrlQueryParser(UrlQueryParser):
    parameter: str

    def parse(self, capture: Capture) -> str | None:
        fragment = parse_url_fragment_parameter(self.parameter, capture.url)
        if fragment is None:
            return None
        return clean_text(
            text=fragment,
            remove_pattern=self.remove_pattern,
            space_pattern=self.space_pattern,
        )


class PathSegmentUrlQueryParser(UrlQueryParser):
    segment: int

    def parse(self, capture: Capture) -> str | None:
        segment = parse_url_path_segment(self.segment, capture.url)
        if segment is None:
            return None
        return clean_text(
            text=segment,
            remove_pattern=self.remove_pattern,
            space_pattern=self.space_pattern,
        )


def _parse_serp_url_query_action(
    config: Config,
    capture: Capture,
) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (
        capture.url_query_parser is not None
        and capture.url_query_parser.should_parse is not None
        and not capture.url_query_parser.should_parse
    ):
        return

    for parser in URL_QUERY_PARSERS:
        if not parser.is_applicable(capture):
            continue
        url_query = parser.parse(capture)
        if url_query is None:
            # Parsing was not successful.
            continue
        serp = Serp(
            index=config.es.index_serps,
            id=capture.id,
            last_modified=utc_now(),
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
            url_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
            url_page_parser=InnerParser(
                should_parse=True,
            ),
            url_offset_parser=InnerParser(
                should_parse=True,
            ),
            warc_query_parser=InnerParser(
                should_parse=True,
            ),
            warc_web_search_result_blocks_parser=InnerParser(
                should_parse=True,
            ),
        )
        yield serp.create_action()
        yield capture.update_action(
            url_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield capture.update_action(
        url_query_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_url_query(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_captures)
    changed_captures_search: Search = (
        Capture.search(using=config.es.client, index=config.es.index_captures)
        .filter(~Term(url_query_parser__should_parse=False))
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_captures = changed_captures_search.count()
    if num_changed_captures > 0:
        changed_captures: Iterable[Capture] = changed_captures_search.params(
            size=size
        ).execute()

        changed_captures = tqdm(
            changed_captures,
            total=num_changed_captures,
            desc="Parsing URL query",
            unit="capture",
        )
        actions = chain.from_iterable(
            _parse_serp_url_query_action(config, capture)
            for capture in changed_captures
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed captures.")


# TODO: Add actual parsers.
URL_QUERY_PARSERS: Sequence[UrlQueryParser] = NotImplemented
