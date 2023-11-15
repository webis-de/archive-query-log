from datetime import datetime
from functools import cached_property
from re import Pattern, compile as pattern
from typing import Literal

from elasticsearch_dsl import Document, Keyword, Text, Date, \
    InnerDoc as InnerDocument, Object, Boolean, Index, Integer, Nested, Long


class BaseDocument(Document):
    last_modified: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    @classmethod
    def index(cls) -> Index:
        return cls._index

    @property
    def id(self) -> str:
        return self.meta.id

    @id.setter
    def id(self, value: str):
        self.meta.id = value


class Archive(BaseDocument):
    name: str = Text()
    description: str = Text()
    cdx_api_url: str = Keyword()
    memento_api_url: str = Keyword()
    last_built_sources: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    class Index:
        name = "aql_archives"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class InterfaceAnnotations(InnerDocument):
    has_input_field: bool = Boolean()
    has_search_form: bool = Boolean()
    has_search_div: bool = Boolean()


class Provider(BaseDocument):
    name: str = Text()
    description: str = Text()
    exclusion_reason: str = Text()
    notes: str = Text()
    website_type: str = Keyword()
    content_type: str = Keyword()
    interface_annotations: InterfaceAnnotations = Object(InterfaceAnnotations)
    domains: list[str] = Keyword()
    url_path_prefixes: list[str] = Keyword()
    last_built_sources: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    class Index:
        name = "aql_providers"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class InnerArchive(InnerDocument):
    id: str = Keyword()
    cdx_api_url: str = Keyword()
    memento_api_url: str = Keyword()


class InnerProvider(InnerDocument):
    id: str = Keyword()
    domain: str = Keyword()
    url_path_prefix: str = Keyword()


class Source(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    last_fetched_captures: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    class Index:
        name = "aql_sources"
        settings = {
            "number_of_shards": 5,
            "number_of_replicas": 2,
        }


class InnerProviderId(InnerDocument):
    id: str = Keyword()


UrlQueryParserType = Literal[
    "query_parameter",
    "fragment_parameter",
    "path_segment",
]


class UrlQueryParser(BaseDocument):
    provider: InnerProviderId = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: int | None = Integer()
    parser_type: UrlQueryParserType = Keyword()
    parameter: str | None = Keyword()
    segment: int | None = Keyword()
    remove_pattern_regex: str | None = Keyword()
    space_pattern_regex: str | None = Keyword()

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
        name = "aql_url_query_parsers"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


UrlPageParserType = Literal[
    "query_parameter",
    "fragment_parameter",
    "path_segment",
]


class UrlPageParser(BaseDocument):
    provider: InnerProviderId = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: int | None = Integer()
    parser_type: UrlPageParserType = Keyword()
    parameter: str | None = Keyword()
    segment: int | None = Keyword()
    remove_pattern_regex: str | None = Keyword()
    space_pattern_regex: str | None = Keyword()

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
        name = "aql_url_page_parsers"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


UrlOffsetParserType = Literal[
    "query_parameter",
    "fragment_parameter",
    "path_segment",
]


class UrlOffsetParser(BaseDocument):
    provider: InnerProviderId = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: int | None = Integer()
    parser_type: UrlOffsetParserType = Keyword()
    parameter: str | None = Keyword()
    segment: int | None = Keyword()
    remove_pattern_regex: str | None = Keyword()
    space_pattern_regex: str | None = Keyword()

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
        name = "aql_url_offset_parsers"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class InnerParser(InnerDocument):
    id: str = Keyword()
    last_parsed: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )


class Capture(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    url: str = Keyword()
    url_key: str = Keyword()
    timestamp: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )
    status_code: int = Integer()
    digest: str = Keyword()
    mimetype: str | None = Keyword()
    filename: str | None = Keyword()
    offset: int | None = Integer()
    length: int | None = Integer()
    access: str | None = Keyword()
    redirect_url: str | None = Keyword()
    flags: list[str] | None = Keyword()
    collection: str | None = Keyword()
    source: str | None = Keyword()
    source_collection: str | None = Keyword()
    url_query_parser: InnerParser | None = Object(InnerParser)

    class Index:
        name = "aql_captures"
        settings = {
            "number_of_shards": 10,
            "number_of_replicas": 2,
        }


class InnerCapture(InnerDocument):
    id: str = Keyword()
    url: str = Keyword()
    timestamp: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )
    status_code: int = Integer()
    digest: str = Keyword()
    mimetype: str | None = Keyword()


class InnerDownloader(InnerDocument):
    id: str = Keyword()
    last_downloaded: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )


class WarcLocation(InnerDocument):
    file: str = Keyword()
    offset: int = Long()
    length: int = Long()


class Snippet(InnerDocument):
    url: str = Keyword()
    rank: int | None = Integer()
    title: str | None = Keyword()
    text: str | None = Keyword()


class Serp(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    capture: InnerCapture = Object(InnerCapture)
    url_query: str = Keyword()
    url_query_parser: InnerParser | None = Object(InnerParser)
    url_page: int | None = Integer()
    url_page_parser: InnerParser | None = Object(InnerParser)
    url_offset: int | None = Integer()
    url_offset_parser: InnerParser | None = Object(InnerParser)
    # url_language: str | None = Keyword()
    # url_language_parser: InnerParser | None = Object(InnerParser)
    warc_location: WarcLocation | None = Object(WarcLocation)
    warc_downloader: InnerDownloader | None = Object(InnerDownloader)
    # rendered_warc_location: WarcLocation | None = Object(WarcLocation)
    # rendered_warc_downloader: InnerDownloader | None = (
    #     Object(InnerDownloader))
    serp_query: str | None = Keyword()
    serp_query_parser: InnerParser | None = Object(InnerParser)
    serp_snippets: list[Snippet] | None = Nested(Snippet)
    serp_snippets_parser: InnerParser | None = Object(InnerParser)

    class Index:
        name = "aql_serps"
        settings = {
            "number_of_shards": 10,
            "number_of_replicas": 2,
        }


class InnerSerp(InnerDocument):
    id: str = Keyword()


class Result(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    serp: InnerSerp = Object(InnerSerp)
    url: str = Keyword()

    class Index:
        name = "aql_results"
        settings = {
            "number_of_shards": 20,
            "number_of_replicas": 2,
        }
