from functools import cached_property
from json import dumps as json_dumps
from pathlib import Path
from typing import Iterable, Any, Annotated

from dotenv import find_dotenv
from elasticsearch import Elasticsearch, AsyncElasticsearch
from elasticsearch.helpers import streaming_bulk
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from pyrate_limiter import Limiter, RequestRate, Duration
from requests import Session
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry
from warc_cache import WarcCacheStore
from warc_s3 import WarcS3Store

from archive_query_log import __version__ as version
from archive_query_log.utils.warc import WarcStore, WarcS3StoreWrapper


class EsConfig(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    host: str = "localhost"
    port: int = 9200
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    index_archives: str = "archives"
    index_providers: str = "providers"
    index_sources: str = "sources"
    index_captures: str = "captures"
    index_serps: str = "serps"
    index_web_search_result_blocks: str = "web_search_result_blocks"
    index_special_contents_result_blocks: str = "special_contents_result_blocks"
    max_retries: int = 5
    bulk_chunk_size: int = 500
    bulk_max_chunk_bytes: int = 100 * 1024 * 1024
    bulk_initial_backoff: int = 2
    bulk_max_backoff: int = 60

    @cached_property
    def client(self) -> Elasticsearch:
        return Elasticsearch(
            hosts=f"https://{self.host}:{self.port}",
            api_key=self.api_key,
            http_auth=(self.username, self.password)
            if self.api_key is None
            and self.username is not None
            and self.password is not None
            else None,
            timeout=60,
            max_retries=self.max_retries,
            retry_on_status=(502, 503, 504),
            retry_on_timeout=True,
        )

    @cached_property
    def async_client(self) -> AsyncElasticsearch:
        return AsyncElasticsearch(
            hosts=f"https://{self.host}:{self.port}",
            api_key=self.api_key,
            http_auth=(self.username, self.password)
            if self.api_key is None
            and self.username is not None
            and self.password is not None
            else None,
            timeout=60,
            max_retries=self.max_retries,
            retry_on_status=(502, 503, 504),
            retry_on_timeout=True,
        )

    def streaming_bulk(
        self,
        actions: Iterable[dict],
        dry_run: bool = False,
    ) -> Iterable[tuple[bool, Any]]:
        if dry_run:
            for action in actions:
                print(json_dumps(action))
                yield (True, None)
        else:
            yield from streaming_bulk(
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

    def bulk(
        self,
        actions: Iterable[dict],
        dry_run: bool = False,
    ) -> None:
        for _ in self.streaming_bulk(
            actions=actions,
            dry_run=dry_run,
        ):
            pass


class S3Config(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    endpoint_url: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    bucket_name: str = "serps"

    @cached_property
    def warc_s3_store(self) -> WarcS3Store:
        return WarcS3Store(
            endpoint_url=self.endpoint_url,
            access_key=self.access_key,
            secret_key=self.secret_key,
            bucket_name=self.bucket_name,
            max_file_size=1_000_000_000,
            quiet=False,
        )

    @cached_property
    def warc_store(self) -> WarcStore:
        return WarcS3StoreWrapper(self.warc_s3_store)


class HttpConfig(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

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
        session.mount("http://", _adapter)
        session.mount("https://", _adapter)
        return session


class WarcCacheConfig(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    path_serps: Path = Path("data/cache/warc/serps")
    path_results: Path = Path("data/cache/warc/results")

    @cached_property
    def store_serps(self) -> WarcCacheStore:
        return WarcCacheStore(
            cache_dir_path=self.path_serps,
            max_file_records=100,
            read_all_min_accumulated_bytes=1_000_000_000,
            read_all_include_temporary_files=False,
            quiet=False,
        )

    @cached_property
    def store_results(self) -> WarcCacheStore:
        return WarcCacheStore(
            cache_dir_path=self.path_results,
            max_file_records=100,
            read_all_min_accumulated_bytes=1_000_000_000,
            read_all_include_temporary_files=False,
            quiet=False,
        )


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True,
        env_file=find_dotenv(),
        env_nested_delimiter="_",
        env_nested_max_split=1,
    )

    es: Annotated[
        EsConfig,
        Field(
            validation_alias=AliasChoices("es", "elasticsearch"),
        ),
    ] = EsConfig()
    s3: S3Config = S3Config()
    http: HttpConfig = HttpConfig()
    warc_cache: WarcCacheConfig = WarcCacheConfig()
