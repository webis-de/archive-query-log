from unittest import TestCase
from web_archive_query_log.results.test.test_utils import verify_serp_parsing


class TestYoutubeSearch(TestCase):
    def test_chaoz_time_search(self):
        verify_serp_parsing(
           'https://web.archive.org/web/20220510060811id_/https://www.youtube.com/results?search_query=%21%21%21Chaoz+time%21%21%21',
           'youtube'
        )
