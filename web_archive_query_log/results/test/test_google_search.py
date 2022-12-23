from unittest import TestCase
from web_archive_query_log.results.test.test_utils import verify_serp_parsing


class TestGoogleSearch(TestCase):
    def test_bla(self):
        verify_serp_parsing(
            'https://web.archive.org/web/20210411035549id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&q=%22+9/11+revisited%22',
            'google'
        )
# https://web.archive.org/web/20210227012632id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&q=%22+Lenin%22
#https://web.archive.org/web/20210225074449id_/http://www.google.com/search?hl=en&q=%22%22+%22Agust&iacute;n
# https://web.archive.org/web/20210609042746id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&safe=off&q=++++%22+Cortisol+test%22
#https://web.archive.org/web/20210330143639id_/http://www.google.com/search?hl=en&ie=ISO-8859-1&q=%22+coxsackie+virus%22_
#https://web.archive.org/web/20210330143719id_/http://www.google.com/search?hl=en&source=hp&ie=ISO-8859-1&q=%22+homemade+l
#https://web.archive.org/web/20210330143611id_/http://www.google.com/search?hl=en&ie=ISO-8859-1&q=%22+dove%22+%22soap%22+%22
#https://web.archive.org/web/20210224224643id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&q=%22+dead+cock%22+mortuary