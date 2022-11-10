from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlsplit, quote

from requests import get
from tqdm.auto import tqdm

from internet_archive_query_log.parse import QueryParser
from internet_archive_query_log.util import backoff_session


@dataclass(frozen=True)
class InternetArchiveQueries:
    url_prefix: str
    parser: QueryParser
    data_directory_path: Path
    cdx_api_url: str

    @cached_property
    def _params(self) -> Iterable[tuple[str, Any]]:
        return (
            ("url", self.url_prefix),
            ("matchType", "prefix"),
            ("fl", "original"),
            ("filter", "mimetype:text/html"),
            ("filter", "!statuscode:[45].."),
        )

    @cached_property
    def _output_directory_path(self) -> Path:
        output_directory_path = \
            self.data_directory_path / quote(self.url_prefix, safe="")
        output_directory_path.mkdir(exist_ok=True)
        return output_directory_path

    @cached_property
    def _result_path(self) -> Path:
        return self._output_directory_path / "queries.txt"

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
        return self._output_directory_path / f"page_{page:05}.txt"

    def _fetch_page(self, page: int) -> Optional[Path]:
        path = self._page_cache_path(page)
        if path.exists():
            # Page was already downloaded, skip it.
            assert path.is_file()
            return path

        session = backoff_session()
        with path.open("wt") as file:
            try:
                response = session.get(
                    self.cdx_api_url,
                    params=[
                        *self._params,
                        ("page", page),
                    ],
                    timeout=10 * 60  # 10 minutes, better safe than sorry ;)
                )
            except:
                print(f"Failed to load page {page}.")
                return None
            for url in response.text.splitlines(keepends=False):
                query = self.parser.parse_query(urlsplit(url))
                if query is not None:
                    # TODO we might write CSV format here to
                    #  also include the timestamp and url.
                    file.write(f"{query}\n")

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
        This allows to
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
                    file.write(page_file.read())

    def fetch(self) -> None:
        self._fetch_pages()
        missing_pages = self._missing_pages()
        if len(missing_pages) > 0:
            raise RuntimeError(
                f"Pages missing: {missing_pages}\n"
                f"Consider retrying the download, as some requests "
                f"might only have timed out."
            )
        self._merge_cached_pages()
