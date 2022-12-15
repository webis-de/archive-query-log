from approvaltests import verify_as_json
from approvaltests.namer.cli_namer import CliNamer
from approvaltests.core.options import Options
from fastwarc.warc import ArchiveIterator
from os.path import exists
from slugify import slugify


def get_record_with_id(warc_file: str, warc_record_id: str):
    warc_file = f'data/serp-parsing/warcs/{warc_file}'

    if not exists(warc_file):
        warc_file = f'../../{warc_file}'

    for record in ArchiveIterator(open(warc_file, 'rb')):
        if record.record_id == warc_record_id:
            return record

    raise ValueError(f'Could not find record with id {warc_record_id} in {warc_file}')


def verify_serp_parse_as_json(actual, warc_record_id):
    verify_as_json(
        actual,
        options=Options().with_namer(CliNamer(slugify(warc_record_id)))
    )


def verify_serp_parsing(warc_file: str, warc_record_id: str):
    get_record_with_id(warc_file, warc_record_id)

    actual = {'asdasd': 'asdasd'}

    verify_serp_parse_as_json(actual, warc_record_id)
