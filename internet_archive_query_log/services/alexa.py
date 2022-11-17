from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from io import TextIOWrapper
from math import floor, log10
from pathlib import Path
from tempfile import gettempdir
from typing import Sized, Iterable, Any, Iterator
from zipfile import ZipFile

from requests import get, HTTPError
from requests.exceptions import ChunkedEncodingError
from tqdm.auto import tqdm

from internet_archive_query_log.model import ArchivedUrl
from internet_archive_query_log.util.http import backoff_session

"""
Fuse rankings from all Alexa top-1M snapshots:
http://s3.amazonaws.com/alexa-static/top-1m.csv.zip
https://web.archive.org/web/20220000000000*/http://s3.amazonaws.com/alexa-static/top-1m.csv.zip
https://amenra.github.io/ranx/run/
https://amenra.github.io/ranx/fusion/
"""


@dataclass(frozen=True)
class AlexaTop1MArchivedUrls(Sized, Iterable[ArchivedUrl]):
    data_directory_path: Path
    cdx_api_url: str

    @cached_property
    def _params(self) -> Iterable[tuple[str, Any]]:
        return (
            ("url", "s3.amazonaws.com/alexa-static/top-1m.csv.zip"),
            ("fl", "timestamp,original"),
            ("filter", "mimetype:application/zip"),
            ("filter", "statuscode:200"),
        )

    @cached_property
    def _result_path(self) -> Path:
        return self.data_directory_path / f"alexa-top-1m-archived-urls.jsonl"

    @cached_property
    def _cache_path(self) -> Path:
        cache_path = Path(gettempdir()) / self._result_path.stem
        cache_path.mkdir(exist_ok=True)
        return cache_path

    @cached_property
    def num_pages(self) -> int:
        num_pages_response = get(
            self.cdx_api_url,
            params=[
                *self._params,
                ("showNumPages", True),
            ],
        )
        return int(num_pages_response.text)

    def _page_cache_path(self, page: int) -> Path:
        num_digits = floor(log10(self.num_pages)) + 1
        return self._cache_path / f"page_{page:{num_digits}}.jsonl"

    def _fetch_page(self, page: int) -> Path | None:
        path = self._page_cache_path(page)
        if path.exists():
            # Page was already downloaded, skip it.
            assert path.is_file()
            return path

        session = backoff_session()
        try:
            response = session.get(
                self.cdx_api_url,
                params=[
                    *self._params,
                    ("page", page),
                ],
                timeout=10 * 60  # 10 minutes, better safe than sorry ;)
            )
        except HTTPError:
            print(f"Failed to load page: {page}")
            return None
        except ChunkedEncodingError:
            print(f"Failed to read page contents: {page}")
            return None
        schema = ArchivedUrl.schema()
        with path.open("wt") as file:
            for line in response.text.splitlines(keepends=False):
                timestamp_string, url = line.split()
                timestamp = datetime.strptime(
                    timestamp_string,
                    "%Y%m%d%H%M%S"
                )
                archived_url = ArchivedUrl(url, int(timestamp.timestamp()))
                file.write(schema.dumps(archived_url))
                file.write("\n")

    def _fetch_pages(self) -> None:
        """
        Fetch queries from each individual page.
        """
        for page in tqdm(
                range(self.num_pages),
                desc="Fetch urls",
                unit="page",
        ):
            self._fetch_page(page)

    def _missing_pages(self) -> set[int]:
        """
        Find missing pages.
        Most often, the missing pages are caused by request timeouts.
        """
        missing_pages = set()
        for page in range(self.num_pages):
            path = self._page_cache_path(page)
            if not path.exists() or not path.is_file():
                missing_pages.add(page)
        return missing_pages

    def _merge_cached_pages(self) -> None:
        """
        Merge queries from all pages.
        """
        with self._result_path.open("wt") as file:
            for page in tqdm(
                    range(self.num_pages),
                    desc="Merge urls",
                    unit="page",
            ):
                path = self._page_cache_path(page)
                with path.open("rt") as page_file:
                    lines = page_file
                    for line in lines:
                        file.write(line)

    def fetch(self) -> None:
        if self._result_path.exists():
            assert self._result_path.is_file()
            return
        print(f"Storing temporary files at: {self._cache_path}")
        self._fetch_pages()
        missing_pages = self._missing_pages()
        if len(missing_pages) > 0:
            raise RuntimeError(
                f"Pages missing: {missing_pages}\n"
                f"Consider retrying the download, as some requests "
                f"might only have timed out."
            )
        self._merge_cached_pages()
        for path in self._cache_path.iterdir():
            path.unlink()
        self._cache_path.rmdir()

    def __len__(self) -> int:
        self.fetch()
        with self._result_path.open("rt") as file:
            return sum(1 for _ in file)

    def __iter__(self) -> Iterator[ArchivedUrl]:
        self.fetch()
        schema = ArchivedUrl.schema()
        with self._result_path.open("rt") as file:
            for line in file:
                yield schema.loads(line)


@dataclass(frozen=True)
class AlexaTop1MFusedDomains(Sized, Iterable[Path]):
    data_directory_path: Path
    cdx_api_url: str

    @cached_property
    def _urls(self) -> AlexaTop1MArchivedUrls:
        return AlexaTop1MArchivedUrls(
            data_directory_path=self.data_directory_path,
            cdx_api_url=self.cdx_api_url
        )

    @cached_property
    def _result_path(self) -> Path:
        return self.data_directory_path / f"alexa-top-1m-fused-domains.jsonl"

    @cached_property
    def _cache_path(self) -> Path:
        cache_path = Path(gettempdir()) / self._result_path.stem
        cache_path.mkdir(exist_ok=True)
        return cache_path

    def _url_cache_path(self, url: ArchivedUrl) -> Path:
        return self._cache_path / f"{url.timestamp}.zip"

    def _fetch_url(self, url: ArchivedUrl) -> Path | None:
        path = self._url_cache_path(url)
        if path.exists():
            # Page was already downloaded, skip it.
            assert path.is_file()
            return path

        session = backoff_session()
        try:
            response = session.get(
                url.raw_archive_url,
                timeout=5 * 60  # 5 minutes, better safe than sorry ;)
            )
        except HTTPError:
            print(f"Failed to load URL: {url}")
            return None
        except ChunkedEncodingError:
            print(f"Failed to read URL contents: {url}")
            return None
        with path.open("wb") as file:
            file.write(response.content)

    def _fetch_urls(self) -> None:
        """
        Fetch queries from each individual page.
        """
        for url in tqdm(
                self._urls,
                desc="Fetch urls",
                unit="page",
        ):
            self._fetch_url(url)

    def _missing_urls(self) -> set[ArchivedUrl]:
        """
        Find missing URLs.
        Most often, the missing URLs are caused by request timeouts.
        """
        missing_urls = set()
        for url in self._urls:
            path = self._url_cache_path(url)
            if not path.exists() or not path.is_file():
                missing_urls.add(url)
        return missing_urls

    def _fuse_cached_urls(self) -> None:
        """
        Fuse cached rankings.
        """
        for url in self._urls:
            path = self._url_cache_path(url)
            with path.open("rb") as file:
                with ZipFile(file) as zip_file:
                    with zip_file.open("top-1m.csv", "r") as csv_file:
                        with TextIOWrapper(csv_file) as csv_text_file:
                            print(sum(1 for _ in csv_text_file))

    def fetch(self) -> None:
        if self._result_path.exists():
            assert self._result_path.is_file()
            return
        print(f"Storing temporary files at: {self._cache_path}")
        self._fetch_urls()
        missing_urls = self._missing_urls()
        if len(missing_urls) > 0:
            raise RuntimeError(
                f"URLs missing: {missing_urls}\n"
                f"Consider retrying the download, as some requests "
                f"might only have timed out."
            )
        self._fuse_cached_urls()
        # for path in self._cache_path.iterdir():
        #     path.unlink()
        # self._cache_path.rmdir()

    def __len__(self) -> int:
        self.fetch()
        with self._result_path.open("rt") as file:
            return sum(1 for _ in file)

    def __iter__(self) -> Iterator[ArchivedUrl]:
        self.fetch()
        schema = ArchivedUrl.schema()
        with self._result_path.open("rt") as file:
            for line in file:
                yield schema.loads(line)
