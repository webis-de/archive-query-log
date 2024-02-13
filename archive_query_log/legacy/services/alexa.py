from asyncio import run
from csv import reader
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from io import TextIOWrapper
from itertools import islice
from math import floor, log10
from pathlib import Path
from tempfile import gettempdir
from typing import Sized, Iterable, Any, Iterator, Mapping, Set, NamedTuple
from zipfile import ZipFile

from publicsuffixlist import PublicSuffixList
from ranx import Run, fuse
from requests import get, HTTPError
from requests.exceptions import ChunkedEncodingError
from tqdm.auto import tqdm

from archive_query_log.legacy.model import ArchivedUrl
from archive_query_log.legacy.download.raw import WebArchiveRawDownloader
from archive_query_log.legacy.util.http_session import backoff_session


@dataclass(frozen=True)
class AlexaTop1MArchivedUrls(Sized, Iterable[ArchivedUrl]):
    """
    Get all archived URLs of Alexa top-1M rankings.
    """
    output_path: Path
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
        return self.output_path

    @cached_property
    def _cache_path(self) -> Path:
        cache_path = Path(gettempdir()) / self.output_path.stem
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
            # 10 minutes
            timeout=10 * 60  # nosec: B113
        )
        return int(num_pages_response.text)

    def _page_cache_path(self, page: int) -> Path:
        num_digits = floor(log10(self.num_pages)) + 1
        return self._cache_path / f"page_{page:{num_digits}}.jsonl"

    def _fetch_page(self, page: int) -> None:
        path = self._page_cache_path(page)
        if path.exists():
            # Page was already downloaded, skip it.
            if not path.is_file():
                raise RuntimeError(f"Path must be a file: {path}")
            return

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
        pages: Iterable[int] = range(self.num_pages)
        # noinspection PyTypeChecker
        pages = tqdm(
            pages,
            desc="Fetch urls",
            unit="page",
        )
        for page in pages:
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
        with self.output_path.open("wt", encoding="utf8") as file:
            pages: Iterable[int] = range(self.num_pages)
            # noinspection PyTypeChecker
            pages = tqdm(
                pages,
                desc="Merge urls",
                unit="page",
            )
            for page in pages:
                path = self._page_cache_path(page)
                with path.open("rt") as page_file:
                    lines = page_file
                    for line in lines:
                        file.write(line)

    def fetch(self) -> None:
        if self.output_path.exists():
            if not self.output_path.is_file():
                raise RuntimeError(f"Path must be a file: {self.output_path}")
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
        with self.output_path.open("rt", encoding="utf8") as file:
            return sum(1 for _ in file)

    def __iter__(self) -> Iterator[ArchivedUrl]:
        self.fetch()
        schema = ArchivedUrl.schema()
        with self.output_path.open("rt", encoding="utf8") as file:
            for line in file:
                url = schema.loads(line, many=True)
                if isinstance(url, list):
                    raise ValueError(f"Expected one URL per line: {line}")
                yield url


def _iter_deduplicated(domains: Iterable[str]) -> Iterator[str]:
    public_suffix_list = PublicSuffixList()
    second_level_domains = set()
    for domain in domains:
        public_suffix = public_suffix_list.publicsuffix(domain)
        second_level_domain = public_suffix_list.subdomain(domain, 0)
        if second_level_domain is None:
            second_level_domain = public_suffix
        second_level_domain = second_level_domain.removesuffix(
            f".{public_suffix}"
        )
        if second_level_domain in second_level_domains:
            continue
        second_level_domains.add(second_level_domain)
        yield domain


class AlexaTop1MDomain(NamedTuple):
    rank: int
    domain: str
    public_suffix: str


@dataclass(frozen=True)
class AlexaTop1MFusedDomains(Sized, Iterable[AlexaTop1MDomain]):
    """
    Fuse the rop-1000 of all archived Alexa top-1M rankings.
    """
    data_directory_path: Path
    cdx_api_url: str
    fusion_method: str = "rrf"
    max_domains_per_ranking: int | None = 1000
    deduplicate_per_ranking: bool = True
    deduplicate_fused_ranking: bool = False

    @cached_property
    def _urls(self) -> Set[ArchivedUrl]:
        alexa_path = self.data_directory_path / \
                     "alexa-top-1m-archived-urls.jsonl"
        urls = AlexaTop1MArchivedUrls(
            output_path=alexa_path,
            cdx_api_url=self.cdx_api_url
        )
        return set(urls)

    @cached_property
    def _result_path(self) -> Path:
        name = f"alexa-top-1m-fused-domains-{self.fusion_method}" \
               f"-top-{self.max_domains_per_ranking}.csv"
        return self.data_directory_path / name

    @cached_property
    def _cache_path(self) -> Path:
        cache_path = Path(gettempdir()) / "alexa-top-1m-fused-domains"
        cache_path.mkdir(exist_ok=True)
        return cache_path

    def _fetch_rankings(self) -> Iterable[Path]:
        downloader = WebArchiveRawDownloader()
        paths: Mapping[ArchivedUrl, Path] = run(downloader.download(
            self._urls,
            self._cache_path,
            lambda url: f"{url.timestamp}.zip",
        ))
        if len(paths) < len(self._urls):
            raise RuntimeError("Some downloads were unsuccessful. Try again.")
        return paths.values()

    def _fuse_cached_rankings(self) -> None:
        runs: list[Run] = []
        num_runs = sum(1 for _ in self._cache_path.iterdir())
        paths: Iterable[Path] = self._cache_path.iterdir()
        # noinspection PyTypeChecker
        paths = tqdm(
            paths,
            total=num_runs,
            desc="Fuse rankings",
            unit="ranking",
        )
        for path in paths:
            with path.open("rb") as file:
                with ZipFile(file) as zip_file:
                    with zip_file.open("top-1m.csv", "r") as csv_file:
                        with TextIOWrapper(csv_file) as lines:
                            domains: Iterable[str] = (
                                line[1]
                                for line in reader(lines)
                            )
                            if self.deduplicate_per_ranking:
                                domains = _iter_deduplicated(domains)
                            if self.max_domains_per_ranking is not None:
                                domains = islice(
                                    domains,
                                    self.max_domains_per_ranking,
                                )
                            scores: dict[str, float] = {
                                domain: 1_000_000 - index
                                for index, domain in enumerate(domains)
                            }
                            alexa_run = Run({"_": scores})
                            runs.append(alexa_run)
        print(f"Fusing {len(runs)} rankings.")
        combined_run = fuse(
            runs=runs,
            norm="min-max",
            method=self.fusion_method,
        ).to_dict()
        items = sorted(
            combined_run["_"].items(),
            key=lambda item: item[1],
            reverse=True,
        )
        fused_domains: Iterable[str] = (domain for domain, _ in items)
        if self.deduplicate_fused_ranking and not self.deduplicate_per_ranking:
            fused_domains = _iter_deduplicated(fused_domains)
        public_suffix_list = PublicSuffixList(only_icann=True)
        with self._result_path.open("wt") as file:
            for index, domain in enumerate(fused_domains):
                public_suffix = public_suffix_list.publicsuffix(domain)
                file.write(f"{index + 1},{domain},{public_suffix}\n")

    def fetch(self) -> None:
        if self._result_path.exists():
            if not self._result_path.is_file():
                raise RuntimeError(f"Path must be a file: {self._result_path}")
            return
        print(f"Storing temporary files at: {self._cache_path}")
        self._fetch_rankings()
        self._fuse_cached_rankings()
        # for path in self._cache_path.iterdir():
        #     path.unlink()
        # self._cache_path.rmdir()

    def __len__(self) -> int:
        self.fetch()
        with self._result_path.open("rt") as file:
            return sum(1 for _ in file)

    def __iter__(self) -> Iterator[AlexaTop1MDomain]:
        self.fetch()
        with self._result_path.open("rt") as file:
            for line in file:
                index, domain, public_suffix = line.split(",")
                yield AlexaTop1MDomain(int(index), domain, public_suffix)
