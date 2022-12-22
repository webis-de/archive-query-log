from approvaltests import verify_as_json
from approvaltests.namer.cli_namer import CliNamer
from approvaltests.core.options import Options
from os.path import exists
from slugify import slugify
from web_archive_query_log.download.iterable import ArchivedRawSerps
from pathlib import Path

def verify_serp_parsing(archived_url: str):
    __get_record_with_id(archived_url)

    actual = {'asdasd': 'asdassds'}

    __verify_serp_parse_as_json(actual, archived_url)


def __get_record_with_id(archived_url: str):
    warc_directory = f'data/archived-raw-serps/warcs/'

    if not exists(warc_directory):
        warc_directory = f'../../{warc_directory}'

    for record in ArchivedRawSerps(path=Path(warc_directory)):
        if record.url == archived_url or record.url == ('http' + archived_url.split('_/http')[-1]):
            return record

    raise ValueError(f'Could not find record with url {archived_url} in {warc_directory}')


def __verify_serp_parse_as_json(actual, archived_url):
    test_dir = f'data/archived-raw-serps/expected_serp_results'

    if not exists(test_dir):
        test_dir = f'../../{test_dir}'

    verify_as_json(
        actual,
        options=Options().with_namer(CliNamer(f'{test_dir}/{slugify(archived_url)}'))
    )