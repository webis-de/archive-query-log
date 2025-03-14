from pathlib import Path
from typing import Iterable
from webbrowser import open_new_tab

from approvaltests import verify_as_json, ApprovalException
from approvaltests.core.options import Options
from approvaltests.namer.cli_namer import CliNamer
from slugify import slugify
from tqdm.auto import tqdm

from archive_query_log.legacy import PROJECT_DIRECTORY_PATH
from archive_query_log.legacy.config import SERVICES
from archive_query_log.legacy.download.iterable import ArchivedRawSerps
from archive_query_log.legacy.model import ArchivedParsedSerp, \
    ArchivedRawSerp, ResultsParser, InterpretedQueryParser, Service
from archive_query_log.legacy.results.parse import ArchivedParsedSerpParser

_expected_dir = PROJECT_DIRECTORY_PATH / \
                "data/manual-annotations/" \
                "archived-raw-serps/expected/"
_warc_dir = PROJECT_DIRECTORY_PATH / \
            "data/manual-annotations/" \
            "archived-raw-serps/warcs/"


def verify_serp_parsing(
        wayback_raw_url: str,
        service_name: str | None = None,
) -> None:
    services: Iterable[Service]
    if service_name is None:
        services = SERVICES.values()
    else:
        services = [SERVICES[service_name]]

    result_parsers: list[ResultsParser] = []
    interpreted_query_parsers: list[InterpretedQueryParser] = []
    for service in services:
        result_parsers += service.results_parsers
        interpreted_query_parsers += service.interpreted_query_parsers
    parser = ArchivedParsedSerpParser(
        result_parsers,
        interpreted_query_parsers,
    )

    archived_raw_serp = _find_archived_raw_serp(wayback_raw_url)
    archived_parsed_serp = parser.parse_single(archived_raw_serp)

    try:
        _verify_archived_parsed_serp_results(
            archived_raw_serp,
            archived_parsed_serp,
            service_name,
        )
    except ApprovalException as e:
        open_new_tab(archived_raw_serp.raw_archive_url)
        raise e


def _find_archived_raw_serp(wayback_raw_url: str) -> ArchivedRawSerp:
    num_files = sum(1 for _ in _warc_dir.glob("*.warc.gz"))
    print(
        f"Searching for record with URL {wayback_raw_url} in {_warc_dir} "
        f"({num_files} files)"
    )
    records: Iterable[ArchivedRawSerp] = ArchivedRawSerps(path=Path(_warc_dir))
    # noinspection PyTypeChecker
    records = tqdm(
        records,
        desc="Find record for URL",
        unit="record",
    )
    record: ArchivedRawSerp
    for record in records:
        if record.raw_archive_url == wayback_raw_url:
            return record

    raise ValueError(
        f'Could not find record with URL {wayback_raw_url} in {_warc_dir}')


_schema = ArchivedParsedSerp.schema()


def _verify_archived_parsed_serp_results(
        archived_raw_serp: ArchivedRawSerp,
        archived_parsed_serp: ArchivedParsedSerp | None,
        service: str | None = None,
) -> None:
    if archived_parsed_serp is not None:
        actual = _schema.dump(archived_parsed_serp)
    else:
        actual = None
    query = archived_raw_serp.query
    query = slugify(query)
    query = query[:100]
    name = f"{query}-{archived_raw_serp.timestamp}"
    if service is not None:
        name = f"{service}-{name}"
    name = slugify(name)
    verify_as_json(
        actual,
        options=Options().with_namer(
            CliNamer(f"{_expected_dir}/{name}")
        )
    )
