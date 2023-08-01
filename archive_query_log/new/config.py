from dataclasses import dataclass
from functools import cached_property

from dataclasses_json import DataClassJsonMixin
from elasticsearch import Elasticsearch
from mergedeep import merge, Strategy
from yaml import safe_load

from archive_query_log import PROJECT_DIRECTORY_PATH


@dataclass(frozen=True)
class EsIndex(DataClassJsonMixin):
    name: str
    mapping: dict
    settings: dict


@dataclass(frozen=True)
class Config(DataClassJsonMixin):
    es_host: str
    es_port: 9200
    es_username: str
    es_password: str
    es_index_archives: EsIndex
    es_index_providers: EsIndex
    es_index_filters: EsIndex
    es_index_captures: EsIndex
    es_index_serps: EsIndex
    es_index_results: EsIndex
    es_index_url_query_parsers: EsIndex
    es_index_url_page_parsers: EsIndex
    es_index_url_offset_parsers: EsIndex
    es_index_url_language_parsers: EsIndex
    es_index_serp_query_parsers: EsIndex
    es_index_serp_snippets_parsers: EsIndex
    es_index_serp_direct_answer_parsers: EsIndex

    @cached_property
    def es(self) -> Elasticsearch:
        return Elasticsearch(
            f"https://{self.es_host}:{self.es_port}",
            http_auth=(self.es_username, self.es_password),
        )


CONFIG_PATHS = [
    PROJECT_DIRECTORY_PATH / "config.yml",
    PROJECT_DIRECTORY_PATH / "config.override.yml",
]
CONFIG_DICT = {}
for config_path in CONFIG_PATHS:
    if config_path.exists():
        with config_path.open("rb") as config_file:
            config_dict = safe_load(config_file)
        merge(CONFIG_DICT, config_dict, strategy=Strategy.REPLACE)

CONFIG: Config = Config.from_dict(CONFIG_DICT)
