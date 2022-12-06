from pathlib import Path

from click import option, Choice, argument
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.config import SERVICES
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam


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
    service = SERVICES[service_name]
    service_dir = data_directory / service.name
    from web_archive_query_log.queries.parse import ArchivedSerpUrlsParser
    parser = ArchivedSerpUrlsParser(
        query_parsers=service.query_parsers,
        page_number_parsers=service.page_num_parsers,
        verbose=True,
    )
    domains = service.domains
    domains = tqdm(
        domains,
        desc=f"Parse queries",
        unit="domain",
    )
    for domain in domains:
        domain_dir = service_dir / domain
        parser.parse(
            input_path=domain_dir / "urls.jsonl.gz",
            output_path=domain_dir / "serp-urls.jsonl.gz",
        )
