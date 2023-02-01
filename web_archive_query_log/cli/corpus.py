from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from typing import Collection

from click import option, BOOL, argument
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam
from web_archive_query_log.index import ArchivedRawSerpIndex, \
    ArchivedUrlIndex, ArchivedQueryUrlIndex, ArchivedParsedSerpIndex, \
    ArchivedSearchResultSnippetIndex, ArchivedRawSearchResultIndex, \
    LocatedRecord, Location
from web_archive_query_log.model import ArchivedUrl, CorpusQueryUrl, \
    ArchivedSearchResultSnippet, CorpusDocument, CorpusJsonlLocation, \
    CorpusWarcLocation, CorpusJsonlSnippetLocation, ArchivedRawSerp, \
    ArchivedQueryUrl, ArchivedParsedSerp, CorpusQuery, CorpusSearchResult


@main.command(
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
    is_flag=True,
    default=False,
)
@argument(
    "queries_output",
    type=PathParam(
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    required=True,
)
@argument(
    "documents_output",
    type=PathParam(
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    required=True,
)
def corpus_command(
        data_directory: Path,
        focused: bool,
        queries: bool,
        queries_output: Path,
        documents_output: Path,
) -> None:
    from web_archive_query_log.index import ArchivedUrlIndex, \
        ArchivedQueryUrlIndex, ArchivedRawSerpIndex, ArchivedParsedSerpIndex, \
        ArchivedSearchResultSnippetIndex, ArchivedRawSearchResultIndex

    with ExitStack() as exit_stack:
        archived_url_index = exit_stack.enter_context(
            ArchivedUrlIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_query_url_index = exit_stack.enter_context(
            ArchivedQueryUrlIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_raw_serp_index = exit_stack.enter_context(
            ArchivedRawSerpIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_parsed_serp_index = exit_stack.enter_context(
            ArchivedParsedSerpIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_search_result_snippet_index = exit_stack.enter_context(
            ArchivedSearchResultSnippetIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        archived_raw_search_result_index = exit_stack.enter_context(
            ArchivedRawSearchResultIndex(
                data_directory=data_directory,
                focused=focused,
            )
        )
        # archived_parsed_search_result_index = exit_stack.enter_context.(
        #     ArchivedParsedSearchResultIndex(
        #         data_directory=data_directory,
        #         focused=focused,
        #     )
        # )
    with queries_output.open("w") as queries_file, \
            documents_output.open("w") as documents_file:

        archived_urls: Collection[ArchivedUrl]
        if queries:
            archived_urls = archived_query_url_index.values()
        else:
            archived_urls = archived_url_index.values()
        query_schema = CorpusQuery.schema()
        document_schema = CorpusDocument.schema()

        progress = tqdm(
            total=len(archived_urls),
            desc="Build corpus",
            unit="URL",
        )

        def dump_url(url: ArchivedUrl) -> None:
            query, documents = _build_query_documents(
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
                archived_url=url,
            )
            queries_file.write(query_schema.dumps(query))
            queries_file.write("\n")
            for document in documents:
                documents_file.write(document_schema.dumps(document))
                documents_file.write("\n")
            progress.update()

        with ThreadPoolExecutor() as executor:
            executor.map(dump_url, archived_urls)

    print()


def _build_query_url(
        archived_url: ArchivedUrl,
        archived_url_loc: LocatedRecord[Location, ArchivedUrl],
        archived_query_url_loc: LocatedRecord[Location, ArchivedQueryUrl],
        archived_raw_serp_loc: LocatedRecord[Location, ArchivedRawSerp],
        archived_parsed_serp_loc: LocatedRecord[Location, ArchivedParsedSerp],
) -> CorpusQueryUrl:
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
        archived_url_location=CorpusJsonlLocation(
            relative_path=archived_url_loc.location.relative_path,
            byte_offset=archived_url_loc.location.offset,
        ),
        archived_query_url_location=(
            CorpusJsonlLocation(
                relative_path=archived_query_url_loc.location.relative_path,
                byte_offset=archived_query_url_loc.location.offset,
            )
            if archived_query_url_loc is not None else None
        ),
        archived_raw_serp_location=(
            CorpusWarcLocation(
                relative_path=archived_raw_serp_loc.location.relative_path,
                byte_offset=archived_raw_serp_loc.location.offset,
            )
            if archived_raw_serp_loc is not None else None
        ),
        archived_parsed_serp_location=(
            CorpusJsonlLocation(
                relative_path=archived_parsed_serp_loc.location.relative_path,
                byte_offset=archived_parsed_serp_loc.location.offset,
            )
            if archived_parsed_serp_loc is not None else None
        ),
    )


def _build_search_result(
        archived_search_result_snippet_index: ArchivedSearchResultSnippetIndex,
        archived_raw_search_result_index: ArchivedRawSearchResultIndex,
        # archived_parsed_search_result_index: ArchivedParsedSearchResultIndex,
        archived_search_result_snippet: ArchivedSearchResultSnippet,
        corpus_query_url: CorpusQueryUrl,
) -> CorpusSearchResult:
    archived_snippet_loc = archived_search_result_snippet_index \
        .locate(archived_search_result_snippet.id)
    archived_raw_search_result_loc = archived_raw_search_result_index \
        .locate(archived_search_result_snippet.id)
    # archived_parsed_search_result_loc = archived_parsed_search_result_index \
    #     .locate(archived_search_result_snippet.id)
    return CorpusDocument(
        id=archived_search_result_snippet.id,
        url=archived_search_result_snippet.url,
        timestamp=archived_search_result_snippet.timestamp,
        wayback_url=archived_search_result_snippet.archive_url,
        wayback_raw_url=archived_search_result_snippet.raw_archive_url,
        query=corpus_query_url,
        snippet_rank=archived_search_result_snippet.rank,
        snippet_title=archived_search_result_snippet.title,
        snippet_text=archived_search_result_snippet.snippet,
        archived_snippet_location=CorpusJsonlSnippetLocation(
            relative_path=archived_snippet_loc.location.relative_path,
            byte_offset=archived_snippet_loc.location.offset,
            index=archived_snippet_loc.location.index,
        ),
        archived_raw_search_result_location=(
            CorpusWarcLocation(
                relative_path=archived_raw_search_result_loc
                .location.relative_path,
                byte_offset=archived_raw_search_result_loc.location.offset,
            )
            if archived_raw_search_result_loc is not None else None
        ),
        archived_parsed_search_result_location=None,
        # archived_parsed_search_result_location=(
        #     CorpusJsonlLocation(
        #         relative_path=archived_parsed_search_result_loc
        #         .location.relative_path,
        #         line=archived_parsed_search_result_loc.location.offset,
        #     )
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
        archived_url: ArchivedUrl,
) -> tuple[CorpusQuery, list[CorpusDocument]]:
    archived_url_loc = archived_url_index \
        .locate(archived_url.id)
    archived_query_url_loc = archived_query_url_index \
        .locate(archived_url.id)
    archived_raw_serp_loc = archived_raw_serp_index \
        .locate(archived_url.id)
    archived_parsed_serp_loc = archived_parsed_serp_index \
        .locate(archived_url.id)
    query_url = _build_query_url(
        archived_url,
        archived_url_loc,
        archived_query_url_loc,
        archived_raw_serp_loc,
        archived_parsed_serp_loc,
    )
    snippets = archived_parsed_serp_loc.record.results \
        if archived_parsed_serp_loc is not None else []

    def convert_search_result(
            archived_search_result_snippet: ArchivedSearchResultSnippet
    ) -> CorpusSearchResult:
        return _build_search_result(
            archived_search_result_snippet_index,
            archived_raw_search_result_index,
            # archived_parsed_search_result_index,
            archived_search_result_snippet,
            query_url,
        )

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(convert_search_result, snippets))
    query = CorpusQuery(
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
