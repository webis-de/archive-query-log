from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import cached_property
from gzip import GzipFile
from itertools import chain
from pathlib import Path
from typing import AbstractSet, Sequence, Any, Iterable, Iterator, NamedTuple
from urllib.parse import urlencode, quote

from aiohttp import ClientResponseError
from aiohttp_retry import RetryClient
from asyncio_pool import AioPool
from diskcache import Cache
from marshmallow import Schema
from tqdm.auto import tqdm

from archive_query_log.legacy import CDX_API_URL
from archive_query_log.legacy.model import ArchivedUrl, Service
from archive_query_log.legacy.util.archive_http import archive_http_client
from archive_query_log.legacy.util.text import text_io_wrapper


class UrlMatchScope(Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    HOST = "host"
    DOMAIN = "domain"


class _CdxPage(NamedTuple):
    url: str
    page: int
    path: Path


@dataclass(frozen=True)
class ArchivedUrlsFetcher:
    """
    Fetch archived URLs from the Wayback Machine's CDX API and
    store them in a JSONL file.
    """

    match_scope: UrlMatchScope = UrlMatchScope.EXACT
    include_status_codes: AbstractSet[int] = frozenset({200})
    exclude_status_codes: AbstractSet[int] = frozenset({})
    include_mime_types: AbstractSet[str] = frozenset({"text/html"})
    exclude_mime_types: AbstractSet[str] = frozenset({})
    cdx_api_url: str = CDX_API_URL
    overwrite: bool = False

    @cached_property
    def _base_params(self) -> Sequence[tuple[Any, Any]]:
        params = [
            ("matchType", self.match_scope.value),
            ("fl", "timestamp,original"),
        ]
        if len(self.include_mime_types) > 0:
            pattern = "|".join(self.include_mime_types)
            params.append(("filter", f"mimetype:{pattern}"))
        if len(self.exclude_mime_types) > 0:
            pattern = "|".join(self.exclude_mime_types)
            params.append(("filter", f"mimetype:{pattern}"))
        if len(self.include_status_codes) > 0:
            pattern = "|".join(str(code) for code in self.include_status_codes)
            params.append(("filter", f"statuscode:{pattern}"))
        if len(self.exclude_status_codes) > 0:
            pattern = "|".join(str(code) for code in self.exclude_status_codes)
            params.append(("filter", f"statuscode:{pattern}"))
        return params

    def _params(self, url: str) -> Sequence[tuple[Any, Any]]:
        return [
            ("url", url),
            *self._base_params,
        ]

    async def _num_pages(
            self,
            cache: Cache,
            url: str,
            client: RetryClient,
    ) -> int:
        params = self._params(url)
        params_hash = urlencode(params)
        if params_hash in cache:
            return cache[params_hash]
        num_pages_params = [
            *params,
            ("showNumPages", True),
        ]
        url = f"{self.cdx_api_url}?{urlencode(num_pages_params)}"
        async with client.get(url) as response:
            text = await response.text()
            # noinspection PyBroadException
            try:
                num_pages = int(text)
            except Exception:
                num_pages = 0
        cache[params_hash] = num_pages
        return num_pages

    @staticmethod
    def _parse_response_lines(
            lines: Iterable[str],
            schema: Schema,
    ) -> Iterator[str]:
        for line in lines:
            line = line.strip()
            timestamp_string, url = line.split()
            timestamp = datetime.strptime(
                timestamp_string,
                "%Y%m%d%H%M%S"
            )
            archived_url = ArchivedUrl(
                url=url,
                timestamp=int(timestamp.timestamp()),
            )
            yield schema.dumps(archived_url)

    async def _fetch_page(
            self,
            page: _CdxPage,
            client: RetryClient,
            progress: tqdm | None = None,
    ) -> None:
        if page.path.exists() and not self.overwrite and progress is not None:
            progress.update()
            return
        params = [
            *self._params(page.url),
            ("page", page.page),
        ]
        url = f"{self.cdx_api_url}?{urlencode(params)}"
        try:
            async with client.get(url) as response:
                response.raise_for_status()
                text = await response.text()
                schema = ArchivedUrl.schema()
                lines = self._parse_response_lines(
                    text.splitlines(keepends=False),
                    schema,
                )
                page.path.parent.mkdir(parents=True, exist_ok=True)
                with page.path.open("wb") as file, \
                        GzipFile(fileobj=file, mode="wb") as gzip_file, \
                        text_io_wrapper(gzip_file) as text_file:
                    for line in lines:
                        text_file.write(line)
                        text_file.write("\n")
                return
        except ClientResponseError as e:
            page.path.unlink(missing_ok=True)
            print(
                f"HTTP error {e.status} when fetching {url}. "
                f"Please try again later. Continuing with next URL."
            )
            return None
        except BaseException as e:
            page.path.unlink(missing_ok=True)
            raise e
        finally:
            if progress is not None:
                progress.update()

    async def _service_pages(
            self,
            data_directory: Path,
            focused: bool,
            service: Service,
            domain: str | None,
            cdx_page: int | None,
            client: RetryClient,
    ) -> Sequence[_CdxPage]:
        """
        List all items that need to be downloaded.
        """
        output_format_path = data_directory / "archived-urls"
        output_format_path.mkdir(parents=True, exist_ok=True)
        if cdx_page is not None:
            if domain is None:
                raise RuntimeError(
                    "Domain must be specified when page is specified.")
            service_path = output_format_path / service.name
            domain_path = service_path / quote(domain, safe="")
            cdx_page_path = domain_path / f"{cdx_page:010}.jsonl.gz"
            return [
                _CdxPage(
                    path=cdx_page_path,
                    url=domain,
                    page=cdx_page,
                )
            ]
        elif domain is not None:

            async def cdx_page_pages(_cdx_page: int) -> Sequence[_CdxPage]:
                return await self._service_pages(
                    data_directory=data_directory,
                    focused=focused,
                    service=service,
                    domain=domain,
                    cdx_page=_cdx_page,
                    client=client,
                )

            with Cache(str(output_format_path / ".pages")) as cache:
                num_cdx_pages = await self._num_pages(
                    cache,
                    domain,
                    client,
                )
            pool = AioPool(size=1)

            if num_cdx_pages <= 0:
                return []

            return list(chain.from_iterable(
                await pool.map(cdx_page_pages, range(num_cdx_pages))
            ))
        else:
            domains = service.domains
            if focused:
                domains = [
                    f"{domain}{url_prefix}"
                    for domain in domains
                    for url_prefix in service.focused_url_prefixes
                ]
            else:
                suffix_free_domains: list[str] = []
                for domain in sorted(domains, key=len):
                    if not any(
                            domain.endswith(suffix)
                            for suffix in suffix_free_domains
                    ):
                        suffix_free_domains.append(domain)
                domains = suffix_free_domains

            if len(domains) == 0:
                return []

            domains = sorted(domains)
            progress = tqdm(
                domains,
                total=len(domains),
                desc="Fetching number of pages",
                unit="domain",
            )

            async def domain_pages(_domain: str) -> Sequence[_CdxPage]:
                res = await self._service_pages(
                    data_directory=data_directory,
                    focused=focused,
                    service=service,
                    domain=_domain,
                    cdx_page=None,
                    client=client,
                )
                progress.update()
                return res

            pool = AioPool(size=100)

            res: Sequence[Sequence[_CdxPage]]
            res = await pool.map(domain_pages, domains)
            for val in res:
                if isinstance(val, Exception):
                    raise val
            res = sorted(res, key=len, reverse=True)
            return list(chain.from_iterable(res))

    async def fetch_service(
            self,
            data_directory: Path,
            focused: bool,
            service: Service,
            domain: str | None = None,
            cdx_page: int | None = None,
    ):
        async with archive_http_client(limit=5) as client:
            pages = await self._service_pages(
                data_directory=data_directory,
                focused=focused,
                service=service,
                domain=domain,
                cdx_page=cdx_page,
                client=client,
            )

            if len(pages) == 0:
                return

            progress = None
            if len(pages) > 1:
                progress = tqdm(
                    total=len(pages),
                    desc="Fetch archived URLs",
                    unit="page",
                )

            async def fetch_page(page: _CdxPage):
                return await self._fetch_page(
                    page=page,
                    client=client,
                    progress=progress,
                )

            pool = AioPool(size=1000)
            await pool.map(fetch_page, pages)

    async def num_service_pages(
            self,
            data_directory: Path,
            focused: bool,
            service: Service,
            domain: str | None = None,
            cdx_page: int | None = None,
    ) -> int:
        async with archive_http_client(limit=2) as client:
            pages = await self._service_pages(
                data_directory=data_directory,
                focused=focused,
                service=service,
                domain=domain,
                cdx_page=cdx_page,
                client=client,
            )
            return len(pages)
