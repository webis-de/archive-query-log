from datetime import datetime
from functools import cached_property
from re import Pattern, compile as pattern
from typing import Literal

from elasticsearch_dsl import Document, Keyword, Text, Date, RankFeature, \
    InnerDoc as InnerDocument, Object, Index, Integer, Nested, Long, Boolean


class BaseDocument(Document):
    last_modified: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    # TODO: At the moment, this is used more as a creation date.
    #  We could use a different field for that and use this one for the last
    #  modified date.

    # noinspection PyShadowingBuiltins
    def __init__(self, id: str | None = None, **kwargs):
        if id is not None:
            if "meta" not in kwargs:
                kwargs["meta"] = {}
            kwargs["meta"]["id"] = id
        super().__init__(**kwargs)

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
    priority: float | None = RankFeature(positive_score_impact=True)
    should_build_sources: bool = Boolean()
    last_built_sources: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class Provider(BaseDocument):
    name: str = Text()
    description: str = Text()
    exclusion_reason: str = Text()
    notes: str = Text()
    domains: list[str] = Keyword()
    url_path_prefixes: list[str] = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
    should_build_sources: bool = Boolean()
    last_built_sources: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class InnerArchive(InnerDocument):
    id: str = Keyword()
    cdx_api_url: str = Keyword()
    memento_api_url: str = Keyword()
    priority: int | None = RankFeature(positive_score_impact=True)


class InnerProvider(InnerDocument):
    id: str = Keyword()
    domain: str = Keyword()
    url_path_prefix: str = Keyword()
    priority: int | None = RankFeature(positive_score_impact=True)


class Source(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    should_fetch_captures: bool = Boolean()
    last_fetched_captures: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    class Index:
        settings = {
            "number_of_shards": 5,
            "number_of_replicas": 2,
        }


class InnerParser(InnerDocument):
    id: str = Keyword()
    should_parse: bool = Boolean()
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
        settings = {
            "number_of_shards": 40,
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
    should_download: bool = Boolean()
    last_downloaded: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )


class WarcLocation(InnerDocument):
    file: str = Keyword()
    offset: int = Long()
    length: int = Long()


class SnippetId(InnerDocument):
    id: str = Keyword()
    rank: int = Integer()


class Snippet(SnippetId):
    content: str = Text()
    url: str | None = Keyword()
    title: str | None = Text()
    text: str | None = Text()


class DirectAnswerId(InnerDocument):
    id: str = Keyword()


class DirectAnswer(DirectAnswerId):
    content: str = Text()
    url: str | None = Keyword()
    text: str | None = Text()


class Serp(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    capture: InnerCapture = Object(InnerCapture)
    url_query: str = Text()
    url_query_parser: InnerParser | None = Object(InnerParser)
    url_page: int | None = Integer()
    url_page_parser: InnerParser | None = Object(InnerParser)
    url_offset: int | None = Integer()
    url_offset_parser: InnerParser | None = Object(InnerParser)
    # url_language: str | None = Keyword()
    # url_language_parser: InnerParser | None = Object(InnerParser)
    warc_location: WarcLocation | None = Object(WarcLocation)
    warc_downloader: InnerDownloader | None = Object(InnerDownloader)
    warc_query: str | None = Text()
    warc_query_parser: InnerParser | None = Object(InnerParser)
    warc_snippets: list[SnippetId] | None = Nested(SnippetId)
    warc_snippets_parser: InnerParser | None = Object(InnerParser)
    warc_direct_answers: list[DirectAnswerId] | None = Nested(DirectAnswerId)
    warc_direct_answers_parser: InnerParser | None = Object(InnerParser)

    # rendered_warc_location: WarcLocation | None = Object(WarcLocation)
    # rendered_warc_downloader: InnerDownloader | None = (
    #     Object(InnerDownloader))

    class Index:
        settings = {
            "number_of_shards": 40,
            "number_of_replicas": 2,
        }


class InnerSerp(InnerDocument):
    id: str = Keyword()


class Result(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    capture: InnerCapture = Object(InnerCapture)
    serp: InnerSerp = Object(InnerSerp)
    snippet: Snippet = Object(Snippet)
    snippet_parser: InnerParser | None = Object(InnerParser)
    warc_before_serp_location: WarcLocation | None = Object(WarcLocation)
    warc_before_serp_downloader: InnerDownloader | None = (
        Object(InnerDownloader))
    warc_after_serp_location: WarcLocation | None = Object(WarcLocation)
    warc_after_serp_downloader: InnerDownloader | None = (
        Object(InnerDownloader))

    class Index:
        settings = {
            "number_of_shards": 20,
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
    provider: InnerProviderId | None = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
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
    provider: InnerProviderId | None = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
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
    provider: InnerProviderId | None = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
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
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


WarcQueryParserType = Literal[
    "xpath",
]


class WarcQueryParser(BaseDocument):
    provider: InnerProviderId | None = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
    parser_type: WarcQueryParserType = Keyword()
    xpath: str | None = Keyword()
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
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


WarcSnippetsParserType = Literal[
    "xpath",
]


class WarcSnippetsParser(BaseDocument):
    provider: InnerProviderId | None = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
    parser_type: WarcSnippetsParserType = Keyword()
    xpath: str | None = Keyword()
    url_xpath: str | None = Keyword()
    title_xpath: str | None = Keyword()
    text_xpath: str | None = Keyword()

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


WarcDirectAnswersParserType = Literal[
    "xpath",
]


class WarcDirectAnswersParser(BaseDocument):
    provider: InnerProviderId | None = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
    parser_type: WarcDirectAnswersParserType = Keyword()
    xpath: str | None = Keyword()
    url_xpath: str | None = Keyword()
    text_xpath: str | None = Keyword()

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


WarcMainContentParserType = Literal[
    "resiliparse",
]


class WarcMainContentParser(BaseDocument):
    provider: InnerProviderId | None = Object(InnerProviderId)
    url_pattern_regex: str | None = Keyword()
    priority: float | None = RankFeature(positive_score_impact=True)
    parser_type: WarcMainContentParserType = Keyword()

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
