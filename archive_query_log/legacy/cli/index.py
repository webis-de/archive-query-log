from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path

from click import option, BOOL, command
from tqdm.auto import tqdm

from archive_query_log.legacy import DATA_DIRECTORY_PATH
from archive_query_log.legacy.cli.util import PathParam
from archive_query_log.legacy.index import ArchivedRawSerpIndex, \
    ArchivedUrlIndex, ArchivedQueryUrlIndex, ArchivedParsedSerpIndex, \
    ArchivedSearchResultSnippetIndex, ArchivedRawSearchResultIndex


@command(
    "index",
    help="Generate helper indices.",
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
def index_command(
        data_directory: Path,
        focused: bool,
) -> None:
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
        indexes = [
            archived_url_index,
            archived_query_url_index,
            archived_raw_serp_index,
            archived_parsed_serp_index,
            archived_search_result_snippet_index,
            archived_raw_search_result_index,
            # archived_parsed_search_result_index,
        ]

        pool = ThreadPoolExecutor()
        progress = tqdm(
            total=len(indexes),
            desc="Build indices",
            unit="index",
        )

        def run_index(index) -> None:
            index.index()
            progress.update()

        for _ in pool.map(run_index, indexes):
            pass
