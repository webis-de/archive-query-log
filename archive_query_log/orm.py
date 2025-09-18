from datetime import datetime, UTC
from functools import cached_property
from re import Pattern, compile as pattern
from typing import Literal, Annotated, Any, TypeAlias
from uuid import UUID

from annotated_types import Ge
from elasticsearch_dsl import (
    Keyword as KeywordField,
    Text as TextField,
    Date,
    RankFeature,
    Integer as IntegerField,
    Long as LongField,
)
from pydantic import HttpUrl, Field

from archive_query_log.utils.es import BaseDocument, BaseInnerDocument

Keyword: TypeAlias = Annotated[str, KeywordField()]
IntKeyword: TypeAlias = Annotated[int, KeywordField()]
Text: TypeAlias = Annotated[str, TextField()]
Integer: TypeAlias = Annotated[int, IntegerField()]
Long: TypeAlias = Annotated[int, LongField()]
StrictUtcDateTimeNoMillis: TypeAlias = Annotated[
    datetime,
    Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    ),
]
DefaultStrictUtcDateTimeNoMillis: TypeAlias = Annotated[
    StrictUtcDateTimeNoMillis,
    Field(default_factory=lambda: datetime.now(UTC)),
]
FloatRankFeature: TypeAlias = Annotated[
    float,
    Ge(0),
    RankFeature(positive_score_impact=True),
]
IntRankFeature: TypeAlias = Annotated[
    int,
    Ge(0),
    RankFeature(positive_score_impact=True),
]


class UuidBaseDocument(BaseDocument):
    def __init__(
        self,
        /,
        id: UUID,
        meta: dict[str, Any] | None = None,
        **data: Any,
    ) -> None:
        super().__init__(
            id=str(id),
            meta=meta,
            **data,
        )

    @property
    def id(self) -> UUID:
        return UUID(self.meta.id)

    @id.setter
    def id(self, value: UUID) -> None:
        self.meta.id = str(value)


class Archive(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    name: Text
    description: Text
    cdx_api_url: HttpUrl
    memento_api_url: HttpUrl
    priority: FloatRankFeature | None = None
    should_build_sources: bool = True
    last_built_sources: StrictUtcDateTimeNoMillis | None = None

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class Provider(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    name: Text
    description: Text
    exclusion_reason: Text
    notes: Text
    domains: list[Keyword]
    url_path_prefixes: list[Keyword]
    priority: FloatRankFeature | None = None
    should_build_sources: bool = True
    last_built_sources: StrictUtcDateTimeNoMillis | None = None

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class InnerArchive(BaseInnerDocument):
    id: UUID
    cdx_api_url: HttpUrl
    memento_api_url: HttpUrl
    priority: IntRankFeature | None = None


class InnerProvider(BaseInnerDocument):
    id: UUID
    domain: Keyword
    url_path_prefix: Keyword
    priority: IntRankFeature | None = None


class Source(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    archive: InnerArchive
    provider: InnerProvider
    should_fetch_captures: bool = True
    last_fetched_captures: StrictUtcDateTimeNoMillis | None = None

    class Index:
        settings = {
            "number_of_shards": 5,
            "number_of_replicas": 2,
        }


class InnerParser(BaseInnerDocument):
    id: UUID | None = None
    should_parse: bool = True
    last_parsed: StrictUtcDateTimeNoMillis | None = None


class Capture(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    archive: InnerArchive
    provider: InnerProvider
    url: HttpUrl
    url_key: Keyword
    timestamp: StrictUtcDateTimeNoMillis
    status_code: Integer
    digest: Keyword
    mimetype: Keyword | None = None
    filename: Keyword | None = None
    offset: Integer | None = None
    length: Integer | None = None
    access: Keyword | None = None
    redirect_url: HttpUrl | None = None
    flags: list[Keyword] | None = None
    collection: Keyword | None = None
    source: Keyword | None = None
    source_collection: Keyword | None = None
    url_query_parser: InnerParser | None = None

    class Index:
        settings = {
            "number_of_shards": 40,
            "number_of_replicas": 2,
        }


class InnerCapture(BaseInnerDocument):
    id: UUID
    url: HttpUrl
    timestamp: StrictUtcDateTimeNoMillis
    status_code: Integer
    digest: Keyword
    mimetype: Keyword | None = None


class InnerDownloader(BaseInnerDocument):
    id: UUID
    should_download: bool = True
    last_downloaded: StrictUtcDateTimeNoMillis | None = None


class WarcLocation(BaseInnerDocument):
    file: Keyword
    offset: Long
    length: Long


class WebSearchResultBlockId(BaseInnerDocument):
    id: UUID
    rank: Integer


class SpecialContentsResultBlockId(BaseInnerDocument):
    id: UUID
    rank: Integer


class Serp(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    archive: InnerArchive
    provider: InnerProvider
    capture: InnerCapture
    url_query: Text
    url_query_parser: InnerParser | None = None
    url_page: Integer | None = None
    url_page_parser: InnerParser | None = None
    url_offset: Integer | None = None
    url_offset_parser: InnerParser | None = None
    # url_language: Keyword | None = None
    # url_language_parser: InnerParser | None = None
    warc_location: WarcLocation | None = None
    warc_downloader: InnerDownloader | None = None
    warc_query: Text | None = None
    warc_query_parser: InnerParser | None = None
    warc_web_search_result_blocks: list[WebSearchResultBlockId] | None = None
    warc_web_search_result_blocks_parser: InnerParser | None = None
    warc_special_contents_result_blocks: list[SpecialContentsResultBlockId] | None = (
        None
    )
    warc_special_contents_result_blocks_parser: InnerParser | None = None

    class Index:
        settings = {
            "number_of_shards": 40,
            "number_of_replicas": 2,
        }


class InnerSerp(BaseInnerDocument):
    id: UUID


class WebSearchResultBlock(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    archive: InnerArchive
    provider: InnerProvider
    serp_capture: InnerCapture
    serp: InnerSerp
    content: Text
    rank: Integer
    url: HttpUrl | None = None
    title: Text | None = None
    text: Text | None = None
    parser: InnerParser | None = None
    should_fetch_captures: bool = True
    last_fetched_captures: StrictUtcDateTimeNoMillis | None = None
    capture_before_serp: InnerCapture | None = None
    warc_location_before_serp: WarcLocation | None = None
    warc_downloader_before_serp: InnerDownloader | None = None
    capture_after_serp: InnerCapture | None = None
    warc_location_after_serp: WarcLocation | None = None
    warc_downloader_after_serp: InnerDownloader | None = None

    class Index:
        settings = {
            "number_of_shards": 20,
            "number_of_replicas": 2,
        }


class SpecialContentsResultBlock(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    archive: InnerArchive
    provider: InnerProvider
    serp_capture: InnerCapture
    serp: InnerSerp
    content: Text
    rank: Integer
    url: HttpUrl | None = None
    text: Text | None = None
    parser: InnerParser | None = None

    class Index:
        settings = {
            "number_of_shards": 10,
            "number_of_replicas": 2,
        }


class InnerProviderId(BaseInnerDocument):
    id: UUID


UrlQueryParserType = Literal[
    "query_parameter",
    "fragment_parameter",
    "path_segment",
]


class UrlQueryParser(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    provider: InnerProviderId | None = None
    url_pattern_regex: Keyword | None = None
    priority: FloatRankFeature | None = None
    parser_type: UrlQueryParserType
    parameter: Keyword | None = None
    segment: IntKeyword | None = None
    remove_pattern_regex: Keyword | None = None
    space_pattern_regex: Keyword | None = None

    @cached_property
    def url_pattern(self) -> Pattern | None:
        if self.url_pattern_regex is None:
            raise ValueError("No URL pattern regex.")
        return pattern(self.url_pattern_regex)

    @cached_property
    def remove_pattern(self) -> Pattern | None:
        if self.remove_pattern_regex is None:
            return None
        return pattern(self.remove_pattern_regex)

    @cached_property
    def space_pattern(self) -> Pattern | None:
        if self.space_pattern_regex is None:
            return None
        return pattern(self.space_pattern_regex)

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


UrlPageParserType = Literal[
    "query_parameter",
    "fragment_parameter",
    "path_segment",
]


class UrlPageParser(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    provider: InnerProviderId | None = None
    url_pattern_regex: Keyword | None = None
    priority: FloatRankFeature | None = None
    parser_type: UrlPageParserType
    parameter: Keyword | None = None
    segment: IntKeyword | None = None
    remove_pattern_regex: Keyword | None = None
    space_pattern_regex: Keyword | None = None

    @cached_property
    def url_pattern(self) -> Pattern | None:
        if self.url_pattern_regex is None:
            raise ValueError("No URL pattern regex.")
        return pattern(self.url_pattern_regex)

    @cached_property
    def remove_pattern(self) -> Pattern | None:
        if self.remove_pattern_regex is None:
            return None
        return pattern(self.remove_pattern_regex)

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


UrlOffsetParserType = Literal[
    "query_parameter",
    "fragment_parameter",
    "path_segment",
]


class UrlOffsetParser(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    provider: InnerProviderId | None = None
    url_pattern_regex: Keyword | None = None
    priority: FloatRankFeature | None = None
    parser_type: UrlOffsetParserType
    parameter: Keyword | None = None
    segment: IntKeyword | None = None
    remove_pattern_regex: Keyword | None = None
    space_pattern_regex: Keyword | None = None

    @cached_property
    def url_pattern(self) -> Pattern | None:
        if self.url_pattern_regex is None:
            raise ValueError("No URL pattern regex.")
        return pattern(self.url_pattern_regex)

    @cached_property
    def remove_pattern(self) -> Pattern | None:
        if self.remove_pattern_regex is None:
            return None
        return pattern(self.remove_pattern_regex)

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


WarcQueryParserType = Literal["xpath"]


class WarcQueryParser(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    provider: InnerProviderId | None = None
    url_pattern_regex: Keyword | None = None
    priority: FloatRankFeature | None = None
    parser_type: WarcQueryParserType
    xpath: Keyword | None = None
    remove_pattern_regex: Keyword | None = None
    space_pattern_regex: Keyword | None = None

    @cached_property
    def url_pattern(self) -> Pattern | None:
        if self.url_pattern_regex is None:
            raise ValueError("No URL pattern regex.")
        return pattern(self.url_pattern_regex)

    @cached_property
    def remove_pattern(self) -> Pattern | None:
        if self.remove_pattern_regex is None:
            return None
        return pattern(self.remove_pattern_regex)

    @cached_property
    def space_pattern(self) -> Pattern | None:
        if self.space_pattern_regex is None:
            return None
        return pattern(self.space_pattern_regex)

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


WarcWebSearchResultBlocksParserType = Literal["xpath"]


class WarcWebSearchResultBlocksParser(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    provider: InnerProviderId | None = None
    url_pattern_regex: Keyword | None = None
    priority: FloatRankFeature | None = None
    parser_type: WarcWebSearchResultBlocksParserType
    xpath: Keyword | None = None
    url_xpath: Keyword | None = None
    title_xpath: Keyword | None = None
    text_xpath: Keyword | None = None

    @cached_property
    def url_pattern(self) -> Pattern | None:
        if self.url_pattern_regex is None:
            raise ValueError("No URL pattern regex.")
        return pattern(self.url_pattern_regex)

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


WarcSpecialContentsResultBlocksParserType = Literal["xpath"]


class WarcSpecialContentsResultBlocksParser(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    provider: InnerProviderId | None = None
    url_pattern_regex: Keyword | None = None
    priority: FloatRankFeature | None = None
    parser_type: WarcSpecialContentsResultBlocksParserType
    xpath: Keyword | None = None
    url_xpath: Keyword | None = None
    text_xpath: Keyword | None = None

    @cached_property
    def url_pattern(self) -> Pattern | None:
        if self.url_pattern_regex is None:
            raise ValueError("No URL pattern regex.")
        return pattern(self.url_pattern_regex)

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


WarcMainContentParserType = Literal["resiliparse"]


class WarcMainContentParser(UuidBaseDocument):
    last_modified: DefaultStrictUtcDateTimeNoMillis
    provider: InnerProviderId | None = None
    url_pattern_regex: Keyword | None = None
    priority: FloatRankFeature | None = None
    parser_type: WarcMainContentParserType

    @cached_property
    def url_pattern(self) -> Pattern | None:
        if self.url_pattern_regex is None:
            raise ValueError("No URL pattern regex.")
        return pattern(self.url_pattern_regex)

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }
