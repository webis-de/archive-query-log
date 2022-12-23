from web_archive_query_log.config import SERVICES_PATH
from web_archive_query_log.services import read_services


def test_services_can_be_parsed():
    assert read_services(
        SERVICES_PATH,
        ignore_parsing_errors=False
    ) is not None
