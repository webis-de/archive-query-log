from dataclasses import dataclass
from functools import cached_property
from typing import Iterable, Any

from dataclasses_json import DataClassJsonMixin
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from pyrate_limiter import Limiter, RequestRate, Duration
from requests import Session
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry
from warc_s3 import WarcS3Store

from archive_query_log import __version__ as version


@dataclass(frozen=True)
class EsConfig(DataClassJsonMixin):
    host: str
    port: int
    username: str
    password: str
    max_retries: int = 5
    bulk_chunk_size: int = 500
    bulk_max_chunk_bytes: int = 100 * 1024 * 1024
    bulk_initial_backoff: int = 2
    bulk_max_backoff: int = 60

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
class S3Config(DataClassJsonMixin):
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket_name: str

    @cached_property
    def warc_store(self) -> WarcS3Store:
        return WarcS3Store(
            endpoint_url=self.endpoint_url,
            access_key=self.access_key,
            secret_key=self.secret_key,
            bucket_name=self.bucket_name,
            max_file_records=1000,
            quiet=True,
        )


@dataclass(frozen=True)
class HttpConfig(DataClassJsonMixin):
    max_retries: int = 5

    @cached_property
    def session(self) -> Session:
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

    @cached_property
    def session_no_retry(self) -> Session:
        session = Session()
        session.headers.update({
            "User-Agent": f"AQL/{version} (Webis group)",
        })
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
class Config(DataClassJsonMixin):
    es: EsConfig
    s3: S3Config
    http: HttpConfig = HttpConfig()
