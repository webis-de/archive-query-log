from unittest import TestCase
from web_archive_query_log.services import read_services
from web_archive_query_log.config import _SERVICES_PATH

class TestAllServicesCanBeParsed(TestCase):
    def test_services_can_be_parsed(self):
        self.assertIsNotNone(read_services(_SERVICES_PATH, ignore_parsing_errors=False))
