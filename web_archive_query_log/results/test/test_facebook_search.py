from unittest import TestCase
from web_archive_query_log.results.test.test_utils import verify_serp_parsing


class TestFacebookSearch(TestCase):
    def test_jam_of_the_day_search(self):
        verify_serp_parsing(
            'https://web.archive.org/web/20140917041101id_/https://www.facebook.com/search.php?q=%22Jam+of+the+Day&init=quick&tas=0.8517628074453497&search_first_focus=1302687872720',
            'facebook'
        )

    def test_victoria_pynchon_search(self):
        verify_serp_parsing(
            'https://web.archive.org/web/20110110162620id_/http://www.facebook.com/search.php?q=%22Victoria+Pynchon%22&init=q',
            'facebook'
        )
