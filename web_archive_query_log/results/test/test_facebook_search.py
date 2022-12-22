from unittest import TestCase
from web_archive_query_log.results.test.test_utils import verify_serp_parsing


class TestGoogleSearch(TestCase):
    def test_bla(self):
        verify_serp_parsing(
            'https://web.archive.org/web/20140917041101id_/https://www.facebook.com/search.php?q=%22Jam+of+the+Day&init=quick&tas=0.8517628074453497&search_first_focus=1302687872720'
        )