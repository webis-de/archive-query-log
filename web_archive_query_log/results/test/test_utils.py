from approvaltests import verify_as_json
from approvaltests.namer.cli_namer import CliNamer
from approvaltests.core.options import Options
from os.path import exists
from slugify import slugify
from web_archive_query_log.download.iterable import ArchivedRawSerps
from pathlib import Path

from web_archive_query_log.config import SERVICES
from web_archive_query_log.results.parse import ArchivedParsedSerpParser

from copy import deepcopy

def verify_serp_parsing(archived_url: str, service: str):
    result_parsers = []
    interpreted_query_parsers = []
    services = SERVICES.values()
    if service and service in SERVICES:
        services = [SERVICES[service]]

    for service in services:
        if 'results_parsers' in dir(service) and service.results_parsers:
            result_parsers += service.results_parsers
        if 'interpreted_query_parsers' in dir(service) and service.interpreted_query_parsers:
            interpreted_query_parsers += service.interpreted_query_parsers

    parser = ArchivedParsedSerpParser(result_parsers, interpreted_query_parsers)
    archived_record = __get_record_with_id(archived_url)

    actual = parser.parse_single(archived_record)

    __verify_serp_parse_as_json(actual, archived_url)


def __get_record_with_id(archived_url: str):
    warc_directory = f'data/manual-annotations/archived-raw-serps/warcs/'

    if not exists(warc_directory):
        warc_directory = f'../../{warc_directory}'

    for record in ArchivedRawSerps(path=Path(warc_directory)):
        if record.url == archived_url or record.url == ('http' + archived_url.split('_/http')[-1]):
            return record

    raise ValueError(f'Could not find record with url {archived_url} in {warc_directory}')


def __verify_serp_parse_as_json(actual, archived_url):
    test_dir = f'data/manual-annotations/archived-raw-serps/expected_serp_results'

    if not exists(test_dir):
        test_dir = f'../../{test_dir}'

    if not exists(test_dir):
        raise ValueError('Could not handle')

    raw_actual = deepcopy(actual)
    if actual:
        actual = raw_actual.to_dict(encode_json=False)
        if raw_actual.results:
            actual['results'] = [i.to_dict(encode_json=False) for i in raw_actual.results]

    verify_as_json(
        actual,
        options=Options().with_namer(CliNamer(f'{test_dir}/{slugify(archived_url)}'))
    )