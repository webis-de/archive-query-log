from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from click import option, BOOL
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam
from web_archive_query_log.index import ArchivedRawSerpIndex, \
    ArchivedUrlIndex, ArchivedQueryUrlIndex, ArchivedParsedSerpIndex, \
    ArchivedSearchResultSnippetIndex, ArchivedRawSearchResultIndex


@main.command(
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
    archived_url_index = ArchivedUrlIndex(
        data_directory=data_directory,
        focused=focused,
    )
    archived_query_url_index = ArchivedQueryUrlIndex(
        data_directory=data_directory,
        focused=focused,
    )
    archived_raw_serp_index = ArchivedRawSerpIndex(
        data_directory=data_directory,
        focused=focused,
    )
    archived_parsed_serp_index = ArchivedParsedSerpIndex(
        data_directory=data_directory,
        focused=focused,
    )
    archived_search_result_snippet_index = ArchivedSearchResultSnippetIndex(
        data_directory=data_directory,
        focused=focused,
    )
    archived_raw_search_result_index = ArchivedRawSearchResultIndex(
        data_directory=data_directory,
        focused=focused,
    )
    # archived_parsed_search_result_index = ArchivedParsedSearchResultIndex(
    #     data_directory=data_directory,
    #     focused=focused,
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
