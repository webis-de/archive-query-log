from asyncio import sleep, gather, ensure_future
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import floor, log10
from pathlib import Path
from random import random
from tempfile import gettempdir
from typing import AbstractSet, Sequence, Any, Callable
from urllib.parse import urlencode

from aiohttp import ClientResponseError
from aiohttp_retry import RetryClient
from tqdm.auto import tqdm

from web_archive_query_log import CDX_API_URL
from web_archive_query_log.model import ArchivedUrl
from web_archive_query_log.util.archive_http import archive_http_client
from web_archive_query_log.util.urls import _safe_quote_url


class UrlMatchScope(Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    HOST = "host"
    DOMAIN = "domain"


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

    def _params(self, url: str) -> Sequence[tuple[Any, Any]]:
        params = [
            ("url", url),
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

    @staticmethod
    def _cache_path(output_path: Path) -> Path:
        cache_path = Path(gettempdir()) / output_path.stem
        cache_path.mkdir(exist_ok=True)
        return cache_path

    async def _num_pages(self, url: str) -> int:
        params = [
            *self._params(url),
            ("showNumPages", True),
        ]
        url = f"{self.cdx_api_url}?{urlencode(params)}"
        async with archive_http_client(limit=1) as client:
            async with client.get(url) as response:
                text = await response.text()
                return int(text)

    @staticmethod
    def _page_cache_path(
            cache_path: Path,
            page: int,
            num_pages: int,
    ) -> Path:
        num_digits = floor(log10(num_pages)) + 1
        return cache_path / f"page_{page:0{num_digits}}.jsonl"

    async def _fetch_page(
            self,
            cache_path: Path,
            url: str,
            page: int,
            num_pages: int,
            client: RetryClient,
    ) -> None:
        file_path = self._page_cache_path(cache_path, page, num_pages)
        if file_path.exists():
            return
        params = [
            *self._params(url),
            ("page", page),
        ]
        url = f"{self.cdx_api_url}?{urlencode(params)}"
        await sleep(1.0 * random())
        try:
            async with client.get(url) as response:
                response.raise_for_status()
                text = await response.text()
                schema = ArchivedUrl.schema()
                with file_path.open("wt") as file:
                    for line in text.splitlines(keepends=False):
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
                        file.write(schema.dumps(archived_url))
                        file.write("\n")
                return
        except ClientResponseError:
            file_path.unlink(missing_ok=True)
            return None
        except BaseException as e:
            file_path.unlink(missing_ok=True)
            raise e

    async def _fetch_page_progress(
            self,
            cache_path: Path,
            url: str,
            page: int,
            num_pages: int,
            client: RetryClient,
            progress: tqdm,
    ) -> None:
        await self._fetch_page(
            cache_path=cache_path,
            url=url,
            page=page,
            num_pages=num_pages,
            client=client,
        )
        progress.update(1)

    @staticmethod
    @asynccontextmanager
    async def _http_client(client: RetryClient | None) -> RetryClient:
        if client is not None:
            yield client
            return
        async with archive_http_client(limit=5) as client:
            yield client

    async def _fetch_pages(
            self,
            cache_path: Path,
            url: str,
            num_pages: int,
            client: RetryClient | None,
    ) -> None:
        """
        Fetch URLs from each individual page.
        """
        progress = tqdm(
            total=num_pages,
            desc="Fetch archived URLs",
            unit="URL",
        )
        async with self._http_client(client) as client:
            await gather(*(
                ensure_future(self._fetch_page_progress(
                    cache_path=cache_path,
                    url=url,
                    page=page,
                    num_pages=num_pages,
                    client=client,
                    progress=progress,
                ))
                for page in range(num_pages)
            ))

    @staticmethod
    def _missing_pages(cache_path: Path, num_pages: int) -> set[int]:
        """
        Find missing pages.
        Most often, the missing pages are caused by request timeouts.
        """
        missing_pages = set()
        for page in range(num_pages):
            path = ArchivedUrlsFetcher._page_cache_path(cache_path, page,
                                                        num_pages)
            if not path.exists() or not path.is_file():
                missing_pages.add(page)
        return missing_pages

    @staticmethod
    def _merge_cached_pages(
            cache_path: Path,
            num_pages: int,
            output_path: Path,
    ) -> None:
        """
        Merge queries from all pages.
        """
        with output_path.open("wt") as file:
            for page in tqdm(
                    range(num_pages),
                    desc="Merge queries",
                    unit="page",
            ):
                path = ArchivedUrlsFetcher._page_cache_path(
                    cache_path,
                    page,
                    num_pages,
                )
                with path.open("rt") as page_file:
                    lines = page_file
                    for line in lines:
                        file.write(line)

    async def fetch(
            self,
            output_path: Path,
            url: str,
            client: RetryClient | None = None,
    ) -> None:
        cache_path = self._cache_path(output_path)
        num_pages = await self._num_pages(url)
        if output_path.exists():
            assert output_path.is_file()
            return
        print(f"Storing temporary files at: {cache_path}")
        await self._fetch_pages(cache_path, url, num_pages, client)
        missing_pages = self._missing_pages(cache_path, num_pages)
        if len(missing_pages) > 0:
            raise RuntimeError(
                f"Pages missing: {missing_pages}\n"
                f"Consider retrying the download, as some requests "
                f"might only have timed out.\n"
                f"The intermediate files are stored in {str(cache_path)}. "
                f"Delete that directory if you don't need it anymore."
            )
        self._merge_cached_pages(cache_path, num_pages, output_path)
        for path in cache_path.iterdir():
            path.unlink()
        cache_path.rmdir()

    async def _fetch_progress(
            self,
            output_path: Path,
            url: str,
            progress: tqdm,
            client: RetryClient,
    ) -> None:
        await self.fetch(output_path, url, client)
        progress.update(1)

    async def fetch_many(
            self,
            output_path: Path,
            urls: AbstractSet[str],
            file_name: Callable[[str], str] = _safe_quote_url,
            client: RetryClient | None = None,
    ) -> None:
        output_path.mkdir(exist_ok=True)
        progress = tqdm(
            total=len(urls),
            desc="Fetch archived URLs for URLs",
            unit="URL",
        )
        async with self._http_client(client) as client:
            await gather(*(
                ensure_future(self._fetch_progress(
                    output_path=output_path / f"{file_name(url)}.jsonl",
                    url=url,
                    progress=progress,
                    client=client,
                ))
                for url in urls
            ))