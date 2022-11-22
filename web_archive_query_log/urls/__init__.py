from asyncio import sleep, run, gather, ensure_future
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import cached_property
from math import floor, log10
from pathlib import Path
from random import random
from tempfile import gettempdir
from typing import Iterable, Any, Sized, AbstractSet, Sequence, Iterator
from urllib.parse import urlencode, quote

from aiohttp import ClientResponseError
from aiohttp_retry import RetryClient
from tqdm.auto import tqdm

from web_archive_query_log import CDX_API_URL, DATA_DIRECTORY_PATH
from web_archive_query_log.model import ArchivedUrl, ArchivedSerpUrl
from web_archive_query_log.util.archive_http import archive_http_client


class UrlMatchScope(Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    HOST = "host"
    DOMAIN = "domain"


@dataclass(frozen=True)
class WebArchiveUrls(Sized, Iterable[ArchivedUrl]):
    url: str
    match_scope: UrlMatchScope = UrlMatchScope.EXACT
    include_status_codes: AbstractSet[int] = frozenset({200})
    exclude_status_codes: AbstractSet[int] = frozenset({})
    include_mime_types: AbstractSet[str] = frozenset({"text/html"})
    exclude_mime_types: AbstractSet[str] = frozenset({})
    data_directory_path: Path = DATA_DIRECTORY_PATH
    cdx_api_url: str = CDX_API_URL

    @cached_property
    def _params(self) -> Sequence[tuple[Any, Any]]:
        params = [
            ("url", self.url),
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

    @cached_property
    def _result_path(self) -> Path:
        urls_data_directory_path = self.data_directory_path / "urls"
        urls_data_directory_path.mkdir(exist_ok=True)
        url = quote(self.url, safe="")
        return urls_data_directory_path / f"{url}.jsonl"

    @cached_property
    def _cache_path(self) -> Path:
        cache_path = Path(gettempdir()) / self._result_path.stem
        cache_path.mkdir(exist_ok=True)
        return cache_path

    async def _num_pages(self) -> int:
        params = [
            *self._params,
            ("showNumPages", True),
        ]
        url = f"{self.cdx_api_url}?{urlencode(params)}"
        async with archive_http_client(limit=1) as client:
            async with client.get(url) as response:
                text = await response.text()
                return int(text)

    def _page_cache_path(self, page: int, num_pages: int) -> Path:
        num_digits = floor(log10(num_pages)) + 1
        return self._cache_path / f"page_{page:0{num_digits}}.jsonl"

    async def _download_pages(self, num_pages: int) -> None:
        """
        Fetch URLs from each individual page.
        """
        progress = tqdm(
            total=num_pages,
            desc="Fetch archived URLs",
            unit="URL",
        )
        async with archive_http_client(limit=5) as client:
            await gather(*(
                ensure_future(self._download_single_progress(
                    page=page,
                    num_pages=num_pages,
                    client=client,
                    progress=progress,
                ))
                for page in range(num_pages)
            ))

    def _missing_pages(self, num_pages: int) -> set[int]:
        """
        Find missing pages.
        Most often, the missing pages are caused by request timeouts.
        """
        missing_pages = set()
        for page in range(num_pages):
            path = self._page_cache_path(page, num_pages)
            if not path.exists() or not path.is_file():
                missing_pages.add(page)
        return missing_pages

    def _merge_cached_pages(self, num_pages: int) -> None:
        """
        Merge queries from all pages.
        """
        with self._result_path.open("wt") as file:
            for page in tqdm(
                    range(num_pages),
                    desc="Merge queries",
                    unit="page",
            ):
                path = self._page_cache_path(page, num_pages)
                with path.open("rt") as page_file:
                    lines = page_file
                    for line in lines:
                        file.write(line)

    async def download(self) -> None:
        num_pages = await self._num_pages()
        if self._result_path.exists():
            assert self._result_path.is_file()
            return
        print(f"Storing temporary files at: {self._cache_path}")
        await self._download_pages(num_pages)
        missing_pages = self._missing_pages(num_pages)
        if len(missing_pages) > 0:
            raise RuntimeError(
                f"Pages missing: {missing_pages}\n"
                f"Consider retrying the download, as some requests "
                f"might only have timed out."
            )
        self._merge_cached_pages(num_pages)
        for path in self._cache_path.iterdir():
            path.unlink()
        self._cache_path.rmdir()

    async def _download_single(
            self,
            page: int,
            num_pages: int,
            client: RetryClient,
    ) -> None:
        file_path = self._page_cache_path(page, num_pages)
        if file_path.exists():
            return
        params = [
            *self._params,
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

    async def _download_single_progress(
            self,
            page: int,
            num_pages: int,
            client: RetryClient,
            progress: tqdm,
    ) -> None:
        await self._download_single(
            page=page,
            num_pages=num_pages,
            client=client,
        )
        progress.update(1)

    def __len__(self) -> int:
        run(self.download())
        with self._result_path.open("rt") as file:
            return sum(1 for _ in file)

    def __iter__(self) -> Iterator[ArchivedSerpUrl]:
        run(self.download())
        schema = ArchivedUrl.schema()
        with self._result_path.open("rt") as file:
            for line in file:
                yield schema.loads(line)


if __name__ == '__main__':
    u = WebArchiveUrls(
        url="google.com/search?",
        match_scope=UrlMatchScope.PREFIX,
    )
    run(u.download())
