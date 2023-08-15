from datetime import datetime

from elasticsearch_dsl import Document, Keyword, Text, Date, InnerDoc, \
    Object, Boolean, Index


class _BaseDocument(Document):

    @classmethod
    def index(cls) -> Index:
        return cls._index


class Archive(_BaseDocument):
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


class InterfaceAnnotations(InnerDoc):
    has_input_field: bool = Boolean()
    has_search_form: bool = Boolean()
    has_search_div: bool = Boolean()


class Provider(_BaseDocument):
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


class SourceArchive(InnerDoc):
    id: str = Keyword()
    cdx_api_url: str = Keyword()
    memento_api_url: str = Keyword()


class SourceProvider(InnerDoc):
    id: str = Keyword()
    domain: str = Keyword()
    url_path_prefix: str = Keyword()


class Source(_BaseDocument):
    archive: SourceArchive = Object(SourceArchive)
    provider: SourceProvider = Object(SourceProvider)

    class Index:
        name = "aql_sources"
        settings = {
            "number_of_shards": 5,
            "number_of_replicas": 2,
        }
