from unittest import TestCase
from .test_utils import verify_serp_parse_as_json


class TestGoogleSearch(TestCase):
    def test_bla(self):
        verify_serp_parse_as_json(
            'google-sample-first-2mb-of-0000000000.warc.gz',
            '<urn:uuid:da4d63d6-cf81-4f8b-a112-ac3ecf48e123>'
        )
