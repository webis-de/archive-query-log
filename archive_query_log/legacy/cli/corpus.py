from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from csv import writer
from datetime import datetime
from gzip import GzipFile
from pathlib import Path
from typing import Collection
from uuid import UUID

from click import option, BOOL, command
from tqdm.auto import tqdm

from archive_query_log.legacy import DATA_DIRECTORY_PATH
from archive_query_log.legacy.cli.util import PathParam
from archive_query_log.legacy.index import ArchivedRawSerpIndex, \
    ArchivedUrlIndex, ArchivedQueryUrlIndex, ArchivedParsedSerpIndex, \
    ArchivedSearchResultSnippetIndex, ArchivedRawSearchResultIndex, \
    LocatedRecord
from archive_query_log.legacy.model import ArchivedUrl, CorpusQueryUrl, \
    ArchivedSearchResultSnippet, CorpusDocument, CorpusJsonlLocation, \
    CorpusWarcLocation, ArchivedRawSerp, \
    ArchivedQueryUrl, ArchivedParsedSerp, CorpusQuery, CorpusSearchResult


@command(
    "corpus",
    help="Generate corpus.",
)
@option(
    "-d", "--data-directory", "--data-directory-path",
    type=PathParam(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH
)
@option(
    "-f", "--focused",
    type=BOOL,
    default=False,
    is_flag=True,
)
@option(
    "-q", "--queries",
    type=BOOL,
    default=False,
    is_flag=True,
)
@option(
    "-o", "--output-directory", "--output-directory-path",
    type=PathParam(
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
    required=False,
)
def corpus_command(
        data_directory: Path,
        focused: bool,
        queries: bool,
        output_directory: Path,
) -> None:
    output_path: Path
    if output_directory is not None:
        output_path = output_directory
    elif focused:
        output_path = data_directory / "focused" / "corpus"
    else:
        output_path = data_directory / "corpus"
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    queries_path = output_path / f"queries-{timestamp}.jsonl.gz"
    queries_path.touch(exist_ok=True)
    queries_offsets_path = output_path / f"queries-{timestamp}.jsonl.offsets"
    queries_offsets_path.touch(exist_ok=True)
    documents_path = output_path / f"documents-{timestamp}.jsonl.gz"
    documents_path.touch(exist_ok=True)
    documents_offsets_path = \
        output_path / f"documents-{timestamp}.jsonl.offsets"
    documents_offsets_path.touch(exist_ok=True)

    # Load indices.
    with ExitStack() as stack:
        archived_url_index = stack.enter_context(
            ArchivedUrlIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_query_url_index = stack.enter_context(
            ArchivedQueryUrlIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_raw_serp_index = stack.enter_context(
            ArchivedRawSerpIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_parsed_serp_index = stack.enter_context(
            ArchivedParsedSerpIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_search_result_snippet_index = stack.enter_context(
            ArchivedSearchResultSnippetIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_raw_search_result_index = stack.enter_context(
            ArchivedRawSearchResultIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        # archived_parsed_search_result_index = stack.enter_context(
        #     ArchivedParsedSearchResultIndex(
        #         data_directory=data_directory,
        #         focused=focused,
        #     )
        # )

        query_schema = CorpusQuery.schema()
        document_schema = CorpusDocument.schema()
        with queries_path.open("wb") as queries_file, \
                queries_offsets_path.open("w") as queries_offsets_file, \
                documents_path.open("wb") as documents_file, \
                documents_offsets_path.open("w") as documents_offsets_file:
            queries_offsets_writer = writer(queries_offsets_file)
            documents_offsets_writer = writer(documents_offsets_file)

            archived_ids: Collection[UUID]
            if queries:
                archived_ids = set(archived_query_url_index)
            else:
                archived_ids = set(archived_url_index)

            # noinspection PyTypeChecker
            archived_ids = tqdm(
                archived_ids,
                desc="Build corpus",
                unit="ID",
            )

            for archived_id in archived_ids:
                query_documents = _build_query_documents(
                    archived_url_index=archived_url_index,
                    archived_query_url_index=archived_query_url_index,
                    archived_raw_serp_index=archived_raw_serp_index,
                    archived_parsed_serp_index=archived_parsed_serp_index,
                    archived_search_result_snippet_index=(
                        archived_search_result_snippet_index
                    ),
                    archived_raw_search_result_index=(
                        archived_raw_search_result_index
                    ),
                    # archived_parsed_search_result_index=(
                    #     archived_parsed_search_result_index
                    # ),
                    archived_id=archived_id,
                )
                if query_documents is None:
                    continue
                query, documents = query_documents
                queries_file_offset = queries_file.tell()
                with GzipFile(
                        fileobj=queries_file,
                        mode="w",
                ) as queries_gzip_file:
                    queries_gzip_file.write(
                        f"{query_schema.dumps(query)}\n".encode("utf8")
                    )
                queries_offsets_writer.writerow(
                    [str(query.id), str(queries_file_offset)]
                )
                for document in documents:
                    documents_file_offset = documents_file.tell()
                    with GzipFile(
                            fileobj=documents_file,
                            mode="w",
                    ) as documents_gzip_file:
                        documents_gzip_file.write(
                            f"{document_schema.dumps(document)}\n".encode(
                                "utf8")
                        )
                    documents_offsets_writer.writerow(
                        [str(document.id), str(documents_file_offset)]
                    )


def _build_query_url(
        archived_url_loc: LocatedRecord[
            CorpusJsonlLocation, ArchivedUrl
        ],
        archived_query_url_loc: LocatedRecord[
                                    CorpusJsonlLocation, ArchivedQueryUrl
                                ] | None,
        archived_raw_serp_loc: LocatedRecord[
                                   CorpusWarcLocation, ArchivedRawSerp
                               ] | None,
        archived_parsed_serp_loc: LocatedRecord[
                                      CorpusJsonlLocation, ArchivedParsedSerp
                                  ] | None,
) -> CorpusQueryUrl:
    archived_url = archived_url_loc.record
    return CorpusQueryUrl(
        id=archived_url.id,
        url=archived_url.url,
        timestamp=archived_url.timestamp,
        wayback_url=archived_url.archive_url,
        wayback_raw_url=archived_url.raw_archive_url,
        url_query=(
            archived_query_url_loc.record.query
            if archived_query_url_loc is not None else None
        ),
        url_page=(
            archived_query_url_loc.record.page
            if archived_query_url_loc is not None else None
        ),
        url_offset=(
            archived_query_url_loc.record.offset
            if archived_query_url_loc is not None else None
        ),
        serp_query=(
            archived_parsed_serp_loc.record.interpreted_query
            if archived_parsed_serp_loc is not None else None
        ),
        archived_url_location=(
            archived_url_loc.location
            if archived_url_loc is not None else None
        ),
        archived_query_url_location=(
            archived_query_url_loc.location
            if archived_query_url_loc is not None else None
        ),
        archived_raw_serp_location=(
            archived_raw_serp_loc.location
            if archived_raw_serp_loc is not None else None
        ),
        archived_parsed_serp_location=(
            archived_parsed_serp_loc.location
            if archived_parsed_serp_loc is not None else None
        ),
    )


def _build_search_result(
        archived_search_result_snippet_index: ArchivedSearchResultSnippetIndex,
        archived_raw_search_result_index: ArchivedRawSearchResultIndex,
        # archived_parsed_search_result_index: ArchivedParsedSearchResultIndex,
        archived_search_result_snippet: ArchivedSearchResultSnippet,
) -> CorpusSearchResult:
    archived_snippet_loc = archived_search_result_snippet_index[
        archived_search_result_snippet.id]
    archived_raw_search_result_loc = archived_raw_search_result_index \
        .get(archived_search_result_snippet.id)
    # archived_parsed_search_result_loc = archived_parsed_search_result_index \
    #     .get(archived_search_result_snippet.id)
    # archived_parsed_search_result_loc = None
    return CorpusSearchResult(
        id=archived_search_result_snippet.id,
        url=archived_search_result_snippet.url,
        timestamp=archived_search_result_snippet.timestamp,
        wayback_url=archived_search_result_snippet.archive_url,
        wayback_raw_url=archived_search_result_snippet.raw_archive_url,
        snippet_rank=archived_search_result_snippet.rank,
        snippet_title=archived_search_result_snippet.title,
        snippet_text=archived_search_result_snippet.snippet,
        archived_snippet_location=archived_snippet_loc.location,
        archived_raw_search_result_location=(
            archived_raw_search_result_loc.location
            if archived_raw_search_result_loc is not None else None
        ),
        archived_parsed_search_result_location=None,
        # archived_parsed_search_result_location=(
        #     archived_parsed_search_result_loc.location
        #     if archived_parsed_search_result_loc is not None else None
        # ),
    )


def _build_query_documents(
        archived_url_index: ArchivedUrlIndex,
        archived_query_url_index: ArchivedQueryUrlIndex,
        archived_raw_serp_index: ArchivedRawSerpIndex,
        archived_parsed_serp_index: ArchivedParsedSerpIndex,
        archived_search_result_snippet_index: ArchivedSearchResultSnippetIndex,
        archived_raw_search_result_index: ArchivedRawSearchResultIndex,
        # archived_parsed_search_result_index: ArchivedParsedSearchResultIndex,
        archived_id: UUID,
) -> tuple[CorpusQuery, list[CorpusDocument]] | None:
    archived_url_loc = archived_url_index.get(archived_id)
    archived_query_url_loc = archived_query_url_index.get(archived_id)
    archived_raw_serp_loc = archived_raw_serp_index.get(archived_id)
    archived_parsed_serp_loc = archived_parsed_serp_index.get(archived_id)
    if archived_url_loc is None:
        return None
    query_url = _build_query_url(
        archived_url_loc,
        archived_query_url_loc,
        archived_raw_serp_loc,
        archived_parsed_serp_loc,
    )
    snippets = archived_parsed_serp_loc.record.results \
        if archived_parsed_serp_loc is not None else []
    path_components = archived_url_loc.location.relative_path.parts
    service = path_components[2] \
        if path_components[0] == "focused" else path_components[1]

    def convert_search_result(
            archived_search_result_snippet: ArchivedSearchResultSnippet
    ) -> CorpusSearchResult:
        return _build_search_result(
            archived_search_result_snippet_index,
            archived_raw_search_result_index,
            # archived_parsed_search_result_index,
            archived_search_result_snippet,
        )

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(convert_search_result, snippets))
    query = CorpusQuery(
        service=service,
        id=query_url.id,
        url=query_url.url,
        timestamp=query_url.timestamp,
        wayback_url=query_url.wayback_url,
        wayback_raw_url=query_url.wayback_raw_url,
        url_query=query_url.url_query,
        url_page=query_url.url_page,
        url_offset=query_url.url_offset,
        serp_query=query_url.serp_query,
        archived_url_location=query_url.archived_url_location,
        archived_query_url_location=query_url.archived_query_url_location,
        archived_raw_serp_location=query_url.archived_raw_serp_location,
        archived_parsed_serp_location=query_url.archived_parsed_serp_location,
        results=results,
    )

    documents = [
        CorpusDocument(
            service=service,
            id=result.id,
            url=result.url,
            timestamp=result.timestamp,
            wayback_url=result.wayback_url,
            wayback_raw_url=result.wayback_raw_url,
            query=query,
            snippet_rank=result.snippet_rank,
            snippet_title=result.snippet_title,
            snippet_text=result.snippet_text,
            archived_snippet_location=result.archived_snippet_location,
            archived_raw_search_result_location=(
                result.archived_raw_search_result_location
            ),
            archived_parsed_search_result_location=None,
            # archived_parsed_search_result_location=(
            #     result.archived_parsed_search_result_location
            # ),
        )
        for result in results
    ]

    return query, documents
