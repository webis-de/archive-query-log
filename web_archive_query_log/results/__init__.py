from dataclasses import dataclass
from functools import cached_property
from itertools import islice
from math import ceil, floor, log10
from pathlib import Path
from tempfile import gettempdir
from typing import Iterable, Iterator, Tuple
from urllib.parse import quote

from tqdm.auto import tqdm

from web_archive_query_log.model import ArchivedSerpUrl, ArchivedSerp, \
    ArchivedSerpContent
from web_archive_query_log.results.parse import SearchResultsParser
from web_archive_query_log.queries import InternetArchiveQueries
from web_archive_query_log.util.http_session import backoff_session

@dataclass(frozen=True)
class InternetArchiveSerps:
    queries: InternetArchiveQueries
    parsers: Iterable[SearchResultsParser]
    chunk_size: int = 10

    @cached_property
    def _result_path(self) -> Path:
        name = quote(self.queries.url_prefix, safe="")
        return self.queries.data_directory_path / f"{name}_serps.jsonl"

    @cached_property
    def _cache_path(self) -> Path:
        cache_path = Path(gettempdir()) / self._result_path.stem
        cache_path.mkdir(exist_ok=True)
        return cache_path

    @cached_property
    def num_chunks(self) -> int:
        return ceil(len(self.queries) / self.chunk_size)

    def _chunk_cache_path(self, chunk: int) -> Path:
        num_digits = floor(log10(self.num_chunks)) + 1
        return self._cache_path / f"chunk_{chunk:0{num_digits}}.jsonl"

    def _fetch_chunk(
            self,
            chunk: int,
            queries: Iterable[ArchivedSerpUrl],
    ) -> Path | None:
        path = self._chunk_cache_path(chunk)
        if path.exists():
            # Chunk was already parsed, skip it.
            assert path.is_file()
            return path

        session = backoff_session()
        schema = ArchivedSerp.schema()
        serps: list[ArchivedSerp] = []
        for query in queries:
            response = session.get(
                query.raw_archive_url,
                timeout=5 * 60  # 5 minutes, better safe than sorry ;)
            )
            content = ArchivedSerpContent(
                url=query.url,
                timestamp=query.timestamp,
                query=query.query,
                content=response.content,
                encoding=response.encoding,
            )
            parsed = None
            for parser in self.parsers:
                parsed = parser.parse(content)
                if parsed is not None:
                    break
            if parsed is None:
                raise ValueError(f"No SERP parser found for query: {query}")
            serps.append(parsed)
        with path.open("wt") as file:
            for serp in serps:
                file.write(schema.dumps(serp))
                file.write("\n")

    def _chunked_queries(
            self
    ) -> Iterator[Tuple[int, Iterable[ArchivedSerpUrl]]]:
        all_queries = iter(self.queries)
        for chunk in range(self.num_chunks):
            yield chunk, list(islice(all_queries, self.chunk_size))

    def _fetch_chunks(self) -> None:
        """
        Fetch queries from each individual page.
        """
        chunked = self._chunked_queries()
        chunked = tqdm(
            chunked,
            total=self.num_chunks,
            desc="Parse SERPs",
            unit="chunk",
        )
        for chunk, queries in chunked:
            self._fetch_chunk(chunk, queries)

    def _missing_chunks(self) -> set[int]:
        """
        Find missing chunks.
        Most often, the missing chunks are caused by parsing errors or
        request timeouts.
        """
        missing_chunks = set()
        chunked = self._chunked_queries()
        for chunk, queries in chunked:
            path = self._chunk_cache_path(chunk)
            if not path.exists() or not path.is_file():
                missing_chunks.add(chunk)
        return missing_chunks

    def _merge_cached_chunks(self) -> None:
        """
        Merge SERPs from all chunks.
        """
        with self._result_path.open("wt") as file:
            for chunk in tqdm(
                    range(self.num_chunks),
                    desc="Merge SERPs",
                    unit="chunk",
            ):
                path = self._chunk_cache_path(chunk)
                with path.open("rt") as chunk_file:
                    lines = chunk_file
                    for line in lines:
                        file.write(line)

    def fetch(self) -> None:
        if self._result_path.exists():
            assert self._result_path.is_file()
            return
        print(f"Storing temporary files at: {self._cache_path}")
        self._fetch_chunks()
        missing_chunks = self._missing_chunks()
        if len(missing_chunks) > 0:
            raise RuntimeError(
                f"Chunks missing: {missing_chunks}\n"
                f"Consider retrying the download, as some requests "
                f"might only have timed out."
            )
        self._merge_cached_chunks()
        for path in self._cache_path.iterdir():
            path.unlink()
        self._cache_path.rmdir()
