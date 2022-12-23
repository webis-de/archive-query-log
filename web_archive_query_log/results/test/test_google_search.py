from unittest import TestCase
from web_archive_query_log.results.test.test_utils import verify_serp_parsing


class TestGoogleSearch(TestCase):
    def test_bla(self):
        verify_serp_parsing(
            'https://web.archive.org/web/20130630095955id_/https://www.google.com/reader/directory/search?q=je%20te%C5%BEka&start=330',
            'google'
        )
