from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from math import log10, floor
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Iterable, Iterator, Sized
from urllib.parse import quote

from requests import get, HTTPError
from requests.exceptions import ChunkedEncodingError
from tqdm.auto import tqdm

from web_archive_query_log.model import ArchivedSerpUrl, ArchivedUrl
from web_archive_query_log.parse import QueryParser
from web_archive_query_log.util.http_session import backoff_session


@dataclass(frozen=True)
class InternetArchiveQueries(Sized, Iterable[ArchivedSerpUrl]):
    url_prefix: str
    parser: QueryParser
    data_directory_path: Path
    cdx_api_url: str

    @cached_property
    def _params(self) -> Iterable[tuple[str, Any]]:
        return (
            ("url", quote(self.url_prefix)),
            ("matchType", "prefix"),
            ("fl", "timestamp,original"),
            ("filter", "mimetype:text/html"),
            ("filter", "statuscode:200"),
            # ("filter", "!statuscode:[45].."),  # Less strict, with redirects.
        )

    @cached_property
    def _result_path(self) -> Path:
        name = quote(self.url_prefix, safe="")
        return self.data_directory_path / f"{name}.jsonl"

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
        return self._cache_path / f"page_{page:0{num_digits}}.jsonl"

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
        schema = ArchivedSerpUrl.schema()
        with path.open("wt") as file:
            for line in response.text.splitlines(keepends=False):
                timestamp_string, url = line.split()
                timestamp = datetime.strptime(
                    timestamp_string,
                    "%Y%m%d%H%M%S"
                )
                archived_url = ArchivedUrl(url, int(timestamp.timestamp()))
                query = self.parser.parse(archived_url)
                if query is not None:
                    file.write(schema.dumps(query))
                    file.write("\n")

    def _fetch_pages(self) -> None:
        """
        Fetch queries from each individual page.
        """
        for page in tqdm(
                range(self.num_pages),
                desc="Fetch queries",
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
                    desc="Merge queries",
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

    def __iter__(self) -> Iterator[ArchivedSerpUrl]:
        self.fetch()
        schema = ArchivedSerpUrl.schema()
        with self._result_path.open("rt") as file:
            for line in file:
                yield schema.loads(line)
