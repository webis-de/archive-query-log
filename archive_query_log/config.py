from functools import cached_property
from json import dumps as json_dumps
from pathlib import Path
from typing import Iterable, Any, Annotated, Type

from cyclopts import Parameter
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from pydantic import BaseModel, Field, ConfigDict
from pyrate_limiter import Limiter, RequestRate, Duration
from requests import Session
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry
from warc_cache import WarcCacheStore
from warc_s3 import WarcS3Store

from archive_query_log import __version__ as version


@Parameter(
    name="es",
    show=False,
    help="Elasticsearch configuration.",
)
class EsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: Annotated[str, Parameter(env_var="ELASTICSEARCH_HOST")]
    port: Annotated[int, Parameter(env_var="ELASTICSEARCH_PORT")]
    username: Annotated[str, Parameter(env_var="ELASTICSEARCH_USERNAME")]
    password: Annotated[str, Parameter(env_var="ELASTICSEARCH_PASSWORD")]
    index_archives: Annotated[str, Parameter(env_var="ELASTICSEARCH_INDEX_ARCHIVES")]
    index_providers: Annotated[str, Parameter(env_var="ELASTICSEARCH_INDEX_PROVIDERS")]
    index_sources: Annotated[str, Parameter(env_var="ELASTICSEARCH_INDEX_SOURCES")]
    index_captures: Annotated[str, Parameter(env_var="ELASTICSEARCH_INDEX_CAPTURES")]
    index_serps: Annotated[str, Parameter(env_var="ELASTICSEARCH_INDEX_SERPS")]
    index_web_search_result_blocks: Annotated[
        str, Parameter(env_var="ELASTICSEARCH_INDEX_WEB_SEARCH_RESULT_BLOCKS")
    ]
    index_special_contents_result_blocks: Annotated[
        str, Parameter(env_var="ELASTICSEARCH_INDEX_SPECIAL_CONTENTS_RESULT_BLOCKS")
    ]
    index_url_query_parsers: Annotated[
        str, Parameter(env_var="ELASTICSEARCH_INDEX_URL_QUERY_PARSERS")
    ]
    index_url_page_parsers: Annotated[
        str, Parameter(env_var="ELASTICSEARCH_INDEX_URL_PAGE_PARSERS")
    ]
    index_url_offset_parsers: Annotated[
        str, Parameter(env_var="ELASTICSEARCH_INDEX_URL_OFFSET_PARSERS")
    ]
    index_warc_query_parsers: Annotated[
        str, Parameter(env_var="ELASTICSEARCH_INDEX_WARC_QUERY_PARSERS")
    ]
    index_warc_web_search_result_blocks_parsers: Annotated[
        str,
        Parameter(env_var="ELASTICSEARCH_INDEX_warc_web_search_result_blocks_parserS"),
    ]
    index_warc_special_contents_result_blocks_parsers: Annotated[
        str,
        Parameter(
            env_var="ELASTICSEARCH_INDEX_warc_special_contents_result_blocks_parserS"
        ),
    ]
    index_warc_main_content_parsers: Annotated[
        str, Parameter(env_var="ELASTICSEARCH_INDEX_WARC_MAIN_CONTENT_PARSERS")
    ]
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


@Parameter(
    name="s3",
    # show=False,
    help="S3 storage configuration.",
)
class S3Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    endpoint_url: Annotated[str, Parameter(env_var="S3_ENDPOINT_URL")]
    access_key: Annotated[str, Parameter(env_var="S3_ACCESS_KEY")]
    secret_key: Annotated[str, Parameter(env_var="S3_SECRET_KEY")]
    bucket_name: Annotated[str, Parameter(env_var="S3_BUCKET_NAME")]

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


@Parameter(
    name="http",
    # show=False,
    help="HTTP client configuration.",
)
class HttpConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

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


@Parameter(
    name="warc-cache",
    # show=False,
    help="WARC cache configuration.",
)
class WarcCacheConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    path_serps: Annotated[Path, Parameter(env_var="WARC_CACHE_PATH_SERPS")]
    # path_results: Annotated[Path, Parameter(env_var="WARC_CACHE_PATH_RESULTS")]

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


def _nested_parameter(cls: Type[BaseModel]) -> Any:
    """
    Hack to avoid missing argument warnings for the top-level config parameters that delegate to nested config classes.
    """
    return Field(default_factory=lambda: cls.model_validate({}))


@Parameter(name="*")
class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    es: EsConfig = _nested_parameter(EsConfig)
    s3: S3Config = _nested_parameter(S3Config)
    http: HttpConfig = _nested_parameter(HttpConfig)
    warc_cache: WarcCacheConfig = _nested_parameter(WarcCacheConfig)
