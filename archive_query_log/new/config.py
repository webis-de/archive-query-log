from dataclasses import dataclass
from functools import cached_property

from dataclasses_json import DataClassJsonMixin
from elasticsearch import Elasticsearch
from pyrate_limiter import Limiter, RequestRate, Duration
from requests import Session
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from archive_query_log import __version__ as version


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
            hosts=f"https://{self.es_host}:{self.es_port}",
            http_auth=(self.es_username, self.es_password),
            max_retries=5,
            retry_on_status=(502, 503, 504),
            retry_on_timeout=True,
        )

    @cached_property
    def http_session(self) -> Session:
        session = Session()
        session.headers.update({
            "User-Agent": f"AQL/{version} (Webis group)",
        })
        _retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
        )
        _limiter = Limiter(
            RequestRate(1, Duration.SECOND * 10),
        )
        _adapter = LimiterAdapter(
            max_retries=_retries,
            limiter=_limiter,
        )
        # noinspection HttpUrlsUsage
        session.mount("http://", _adapter)
        session.mount("https://", _adapter)
        return session
