from datetime import datetime, UTC
from typing import Annotated, TypeAlias, Sequence
from uuid import UUID

from annotated_types import Ge
from elasticsearch_dsl import (
    Date as _Date,
    RankFeature as _RankFeature,
    Keyword as _Keyword,
)
from pydantic import HttpUrl, Field, AliasChoices

from elasticsearch_pydantic import (
    BaseDocument,
    BaseInnerDocument,
    KeywordField as Keyword,
    TextField as Text,
    IntegerField as Integer,
    LongField as Long,
)


IntKeyword: TypeAlias = Annotated[int, _Keyword]
Date: TypeAlias = Annotated[
    datetime,
    _Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    ),
]
DefaultDate: TypeAlias = Annotated[
    Date,
    Field(default_factory=lambda: datetime.now(UTC)),
]
FloatRankFeature: TypeAlias = Annotated[
    float,
    Ge(0),
    _RankFeature(positive_score_impact=True),
]
IntRankFeature: TypeAlias = Annotated[
    int,
    Ge(0),
    _RankFeature(positive_score_impact=True),
]


class UuidBaseDocument(BaseDocument):
    id: UUID = Field(  # type: ignore[override]
        default_factory=UUID,
        validation_alias=AliasChoices("_id", "id"),
        serialization_alias="_id",
    )


class Archive(UuidBaseDocument):
    last_modified: DefaultDate
    name: Text
    description: Text | None = None
    cdx_api_url: HttpUrl
    memento_api_url: HttpUrl
    priority: FloatRankFeature | None = None
    should_build_sources: bool = True
    last_built_sources: Date | None = None

    class Index:
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 2,
        }


class Provider(UuidBaseDocument):
    last_modified: DefaultDate
    name: Text
    description: Text | None = None
    exclusion_reason: Text | None = None
    notes: Text | None = None
    domains: Sequence[Keyword]
    url_path_prefixes: Sequence[Keyword]
    priority: FloatRankFeature | None = None
    should_build_sources: bool = True
    last_built_sources: Date | None = None

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
    last_modified: DefaultDate
    archive: InnerArchive
    provider: InnerProvider
    should_fetch_captures: bool = True
    last_fetched_captures: Date | None = None

    class Index:
        settings = {
            "number_of_shards": 5,
            "number_of_replicas": 2,
        }


class InnerParser(BaseInnerDocument):
    id: UUID | None = None
    should_parse: bool = True
    last_parsed: Date | None = None


class Capture(UuidBaseDocument):
    last_modified: DefaultDate
    archive: InnerArchive
    provider: InnerProvider
    url: HttpUrl
    url_key: Keyword
    timestamp: Date
    status_code: Integer | None = None
    digest: Keyword
    mimetype: Keyword | None = None
    filename: Keyword | None = None
    offset: Integer | None = None
    length: Integer | None = None
    access: Keyword | None = None
    redirect_url: HttpUrl | None = None
    flags: Sequence[Keyword] | None = None
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
    timestamp: Date
    status_code: Integer | None
    digest: Keyword
    mimetype: Keyword | None = None


class InnerDownloader(BaseInnerDocument):
    id: UUID
    should_download: bool = True
    last_downloaded: Date | None = None


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
    last_modified: DefaultDate
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
    warc_web_search_result_blocks: Sequence[WebSearchResultBlockId] | None = None
    warc_web_search_result_blocks_parser: InnerParser | None = None
    warc_special_contents_result_blocks: (
        Sequence[SpecialContentsResultBlockId] | None
    ) = None
    warc_special_contents_result_blocks_parser: InnerParser | None = None

    class Index:
        settings = {
            "number_of_shards": 40,
            "number_of_replicas": 2,
        }


class InnerSerp(BaseInnerDocument):
    id: UUID


class WebSearchResultBlock(UuidBaseDocument):
    last_modified: DefaultDate
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
    last_fetched_captures: Date | None = None
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
    last_modified: DefaultDate
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
