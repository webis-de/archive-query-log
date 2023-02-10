from pathlib import Path

from approvaltests import verify_as_json
from approvaltests.core.options import Options
from approvaltests.namer.cli_namer import CliNamer
from slugify import slugify

from web_archive_query_log import PROJECT_DIRECTORY_PATH
from web_archive_query_log.config import SERVICES
from web_archive_query_log.download.iterable import ArchivedRawSerps
from web_archive_query_log.model import ArchivedParsedSerp, ArchivedRawSerp
from web_archive_query_log.results.parse import ArchivedParsedSerpParser

_expected_dir = PROJECT_DIRECTORY_PATH / \
                "data/manual-annotations/" \
                "archived-raw-serps/expected_serp_results/"
_warc_dir = PROJECT_DIRECTORY_PATH / \
            "data/manual-annotations/" \
            "archived-raw-serps/warcs/"


def verify_serp_parsing(
        wayback_raw_url: str,
        service: str | None = None,
) -> None:
    if service is None:
        services = SERVICES.values()
    else:
        services = [SERVICES[service]]

    result_parsers = []
    interpreted_query_parsers = []
    for service in services:
        result_parsers += service.results_parsers
        interpreted_query_parsers += service.interpreted_query_parsers
    parser = ArchivedParsedSerpParser(
        result_parsers,
        interpreted_query_parsers,
    )

    archived_raw_serp = _find_archived_raw_serp(wayback_raw_url)
    archived_parsed_serp = parser.parse_single(archived_raw_serp)

    if archived_parsed_serp is None:
        return

    _verify_archived_parsed_serp_results(
        archived_raw_serp,
        archived_parsed_serp,
    )


def _find_archived_raw_serp(wayback_raw_url: str) -> ArchivedRawSerp:
    for record in ArchivedRawSerps(path=Path(_warc_dir)):
        if record.raw_archive_url == wayback_raw_url:
            return record

    raise ValueError(
        f'Could not find record with URL {wayback_raw_url} in {_warc_dir}')


_schema = ArchivedParsedSerp.schema()


def _verify_archived_parsed_serp_results(
        archived_raw_serp: ArchivedRawSerp,
        archived_parsed_serp: ArchivedParsedSerp,
) -> None:
    actual = _schema.dump(archived_parsed_serp)
    verify_as_json(
        actual,
        options=Options().with_namer(
            CliNamer(
                f"{_expected_dir}/"
                f"{slugify(archived_raw_serp.raw_archive_url)}"
            )
        )
    )
