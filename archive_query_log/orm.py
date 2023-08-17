from datetime import datetime

from elasticsearch_dsl import Document, Keyword, Text, Date, InnerDoc, \
    Object, Boolean, Index, Integer


class BaseDocument(Document):

    @classmethod
    def index(cls) -> Index:
        return cls._index


class Archive(BaseDocument):
    name: str = Text()
    description: str = Text()
    cdx_api_url: str = Keyword()
    memento_api_url: str = Keyword()
    last_modified: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )
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


class InterfaceAnnotations(InnerDoc):
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
    last_modified: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )
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


class InnerArchive(InnerDoc):
    id: str = Keyword()
    cdx_api_url: str = Keyword()
    memento_api_url: str = Keyword()


class InnerProvider(InnerDoc):
    id: str = Keyword()
    domain: str = Keyword()
    url_path_prefix: str = Keyword()


class Source(BaseDocument):
    archive: InnerArchive = Object(InnerArchive)
    provider: InnerProvider = Object(InnerProvider)
    last_modified: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )
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
    last_modified: datetime = Date(
        default_timezone="UTC",
        format="strict_date_time_no_millis",
    )

    class Index:
        name = "aql_captures"
        settings = {
            "number_of_shards": 10,
            "number_of_replicas": 2,
        }
