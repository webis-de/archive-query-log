from pathlib import Path

from click import option, Choice, argument
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.config import SERVICES
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam
from web_archive_query_log.queries.parse import ArchivedSerpUrlsParser


@main.group("queries")
def queries():
    pass


@queries.command("parse-service")
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
@argument(
    "service_name",
    type=Choice(sorted(SERVICES.keys())),
    required=True,
)
def fetch_service(
        data_directory: Path,
        service_name: str,
) -> None:
    from web_archive_query_log.config import SERVICES
    service = SERVICES[service_name]
    service_dir = data_directory / service.name
    parser = ArchivedSerpUrlsParser(
        query_parsers=service.query_parsers,
        page_number_parsers=service.page_num_parsers,
        verbose=True,
    )
    service_domain_dirs = list(service_dir.glob("*"))
    service_domain_dirs = tqdm(
        service_domain_dirs,
        desc=f"Parse queries",
        unit="domains",
    )
    for service_domain_dir in service_domain_dirs:
        parser.parse(
            input_path=service_domain_dir / "urls.jsonl",
            output_path=service_domain_dir / "serp-urls.jsonl",
        )
