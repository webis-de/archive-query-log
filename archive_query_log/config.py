from dataclasses import dataclass, field
from functools import cached_property
from os import environ
from pathlib import Path
from typing import Iterable, Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from pyrate_limiter import Limiter, RequestRate, Duration
from requests import Session
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry
from warc_cache import WarcCacheStore
from warc_s3 import WarcS3Store

from archive_query_log import __version__ as version


@dataclass(frozen=True)
class EsConfig:
    host: str = field(default_factory=lambda: environ["ELASTICSEARCH_HOST"])
    port: int = field(default_factory=lambda: int(environ["ELASTICSEARCH_PORT"]))
    username: str = field(default_factory=lambda: environ["ELASTICSEARCH_USERNAME"])
    password: str = field(default_factory=lambda: environ["ELASTICSEARCH_PASSWORD"])
    max_retries: int = 5
    bulk_chunk_size: int = 500
    bulk_max_chunk_bytes: int = 100 * 1024 * 1024
    bulk_initial_backoff: int = 2
    bulk_max_backoff: int = 60
    index_archives: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_ARCHIVES"]
    )
    index_providers: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_PROVIDERS"]
    )
    index_sources: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_SOURCES"]
    )
    index_captures: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_CAPTURES"]
    )
    index_serps: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_SERPS"]
    )
    index_results: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_RESULTS"]
    )
    index_url_query_parsers: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_URL_QUERY_PARSERS"]
    )
    index_url_page_parsers: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_URL_PAGE_PARSERS"]
    )
    index_url_offset_parsers: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_URL_OFFSET_PARSERS"]
    )
    index_warc_query_parsers: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_WARC_QUERY_PARSERS"]
    )
    index_warc_snippets_parsers: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_WARC_SNIPPETS_PARSERS"]
    )
    index_warc_direct_answers_parsers: str = field(
        default_factory=lambda: environ[
            "ELASTICSEARCH_INDEX_WARC_DIRECT_ANSWERS_PARSERS"
        ]
    )
    index_warc_main_content_parsers: str = field(
        default_factory=lambda: environ["ELASTICSEARCH_INDEX_WARC_MAIN_CONTENT_PARSERS"]
    )

    @cached_property
    def client(self) -> Elasticsearch:
        return Elasticsearch(
            hosts=f"https://{self.host}:{self.port}",
            http_auth=(self.username, self.password),
            timeout=60,
            max_retries=self.max_retries,
            retry_on_status=(502, 503, 504),
            retry_on_timeout=True,
        )

    def streaming_bulk(
        self,
        actions: Iterable[dict],
    ) -> Iterable[tuple[bool, Any]]:
        return streaming_bulk(
            client=self.client,
            actions=actions,
            chunk_size=self.bulk_chunk_size,
            max_chunk_bytes=self.bulk_max_chunk_bytes,
            initial_backoff=self.bulk_initial_backoff,
            max_backoff=self.bulk_max_backoff,
            max_retries=self.max_retries,
            raise_on_error=True,
            raise_on_exception=True,
            yield_ok=True,
        )

    def bulk(self, actions: Iterable[dict]) -> None:
        for _ in self.streaming_bulk(actions):
            pass


@dataclass(frozen=True)
class S3Config:
    endpoint_url: str = field(default_factory=lambda: environ["S3_ENDPOINT_URL"])
    access_key: str = field(default_factory=lambda: environ["S3_ACCESS_KEY"])
    secret_key: str = field(default_factory=lambda: environ["S3_SECRET_KEY"])
    bucket_name: str = field(default_factory=lambda: environ["S3_BUCKET_NAME"])

    @cached_property
    def warc_store(self) -> WarcS3Store:
        return WarcS3Store(
            endpoint_url=self.endpoint_url,
            access_key=self.access_key,
            secret_key=self.secret_key,
            bucket_name=self.bucket_name,
            max_file_size=1_000_000_000,
            quiet=False,
        )


@dataclass(frozen=True)
class HttpConfig:
    max_retries: int = 5

    @cached_property
    def session(self) -> Session:
        session = Session()
        session.headers.update(
            {
                "User-Agent": f"AQL/{version} (Webis group)",
            }
        )
        _retries = Retry(
            total=20,
            connect=5,
            read=5,
            redirect=10,
            status=10,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
            respect_retry_after_header=True,
        )
        _limiter = Limiter(
            RequestRate(1, Duration.SECOND * 10),
        )
        _adapter = LimiterAdapter(
            max_retries=_retries,
            limiter=_limiter,
            per_host=True,
        )
        # noinspection HttpUrlsUsage
        session.mount("http://", _adapter)
        session.mount("https://", _adapter)
        return session

    @cached_property
    def session_no_retry(self) -> Session:
        session = Session()
        session.headers.update(
            {
                "User-Agent": f"AQL/{version} (Webis group)",
            }
        )
        _limiter = Limiter(
            RequestRate(1, Duration.SECOND * 10),
        )
        _adapter = LimiterAdapter(
            limiter=_limiter,
        )
        # noinspection HttpUrlsUsage
        session.mount("http://", _adapter)
        session.mount("https://", _adapter)
        return session


@dataclass(frozen=True)
class WarcCacheConfig:
    path_serps: Path = field(
        default_factory=lambda: Path(environ["WARC_CACHE_PATH_SERPS"])
    )
    # path_results: Path = field(
    #     default_factory=lambda: Path(environ["WARC_CACHE_PATH_RESULTS"])
    # )

    @cached_property
    def store_serps(self) -> WarcCacheStore:
        return WarcCacheStore(
            cache_dir_path=self.path_serps,
            max_file_records=100,
            read_all_min_accumulated_bytes=1_000_000_000,
            read_all_include_temporary_files=False,
            quiet=False,
        )

    # @cached_property
    # def store_results(self) -> WarcCacheStore:
    #     return WarcCacheStore(
    #         cache_dir_path=self.path_results,
    #         max_file_records=100,
    #         read_all_min_accumulated_bytes=1_000_000_000,
    #         read_all_include_temporary_files=False,
    #         quiet=False,
    #     )


@dataclass(frozen=True)
class Config:
    es: EsConfig = field(default_factory=EsConfig)
    s3: S3Config = field(default_factory=S3Config)
    http: HttpConfig = field(default_factory=HttpConfig)
    warc_cache: WarcCacheConfig = field(default_factory=WarcCacheConfig)
