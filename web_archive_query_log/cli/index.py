from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from math import inf
from pathlib import Path

from click import option, BOOL, IntRange
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam
from web_archive_query_log.config import SERVICES
from web_archive_query_log.index import ArchivedRawSerpIndex, \
    ArchivedUrlIndex, ArchivedQueryUrlIndex, ArchivedParsedSerpIndex, \
    ArchivedSearchResultSnippetIndex, ArchivedRawSearchResultIndex
from web_archive_query_log.model import Service


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
@option(
    "--min-rank", "--min-alexa-rank",
    type=IntRange(min=1),
    required=False,
)
@option(
    "--max-rank", "--max-alexa-rank",
    type=IntRange(min=1),
    required=False,
)
def index_command(
        data_directory: Path,
        focused: bool,
        min_rank: int | None,
        max_rank: int | None,
) -> None:
    services = SERVICES.values()
    if min_rank is not None:
        services = (
            service
            for service in services
            if (service.alexa_rank is not None and
                service.alexa_rank >= min_rank)
        )
    if max_rank is not None:
        services = (
            service
            for service in services
            if (service.alexa_rank is not None and
                service.alexa_rank <= max_rank)
        )
    services = sorted(services, key=lambda service: service.alexa_rank or inf)

    pool = ThreadPoolExecutor()
    progress = tqdm(
        total=len(services),
        desc="Index services",
        unit="service",
    )

    def index(service: Service) -> None:
        _index_service(
            data_directory=data_directory,
            focused=focused,
            service=service,
        )
        progress.update()

    for _ in pool.map(index, services):
        pass


def _index_service(
        data_directory: Path,
        focused: bool,
        service: Service,
) -> None:
    with ExitStack() as exit_stack:
        archived_url_index = exit_stack.enter_context(
            ArchivedUrlIndex(
                data_directory=data_directory,
                focused=focused,
                service=service.name,
            )
        )
        archived_query_url_index = exit_stack.enter_context(
            ArchivedQueryUrlIndex(
                data_directory=data_directory,
                focused=focused,
                service=service.name,
            )
        )
        archived_raw_serp_index = exit_stack.enter_context(
            ArchivedRawSerpIndex(
                data_directory=data_directory,
                focused=focused,
                service=service.name,
            )
        )
        archived_parsed_serp_index = exit_stack.enter_context(
            ArchivedParsedSerpIndex(
                data_directory=data_directory,
                focused=focused,
                service=service.name,
            )
        )
        archived_search_result_snippet_index = exit_stack.enter_context(
            ArchivedSearchResultSnippetIndex(
                data_directory=data_directory,
                focused=focused,
                service=service.name,
            )
        )
        archived_raw_search_result_index = exit_stack.enter_context(
            ArchivedRawSearchResultIndex(
                data_directory=data_directory,
                focused=focused,
                service=service.name,
            )
        )
        # archived_parsed_search_result_index = exit_stack.enter_context.(
        #     ArchivedParsedSearchResultIndex(
        #         data_directory=data_directory,
        #         focused=focused,
        #         service=service_name,
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
            desc="Build indexes",
            unit="index",
        )

        def index(indexer) -> None:
            indexer.index(parallel=True)
            progress.update()

        for _ in pool.map(index, indexes):
            pass
