from uuid import uuid5, NAMESPACE_URL

NAMESPACE_AQL = uuid5(NAMESPACE_URL, "aql")
NAMESPACE_SOURCE = uuid5(NAMESPACE_AQL, "filter")
NAMESPACE_CAPTURE = uuid5(NAMESPACE_AQL, "capture")
NAMESPACE_SERP = uuid5(NAMESPACE_AQL, "serp")
NAMESPACE_WEB_SEARCH_RESULT_BLOCK = uuid5(NAMESPACE_AQL, "web_search_result_block")
NAMESPACE_SPECIAL_CONTENTS_RESULT_BLOCK = uuid5(NAMESPACE_AQL, "special_contents_result_block")
NAMESPACE_URL_QUERY_PARSER = uuid5(NAMESPACE_AQL, "url_query_parser")
NAMESPACE_URL_PAGE_PARSER = uuid5(NAMESPACE_AQL, "url_page_parser")
NAMESPACE_URL_OFFSET_PARSER = uuid5(NAMESPACE_AQL, "url_offset_parser")
NAMESPACE_URL_LANGUAGE_PARSER = uuid5(
    NAMESPACE_AQL, "url_language_parser")
NAMESPACE_WARC_QUERY_PARSER = uuid5(NAMESPACE_AQL, "warc_query_parser")
NAMESPACE_WARC_WEB_SEARCH_RESULT_BLOCKS_PARSER = uuid5(
    NAMESPACE_AQL, "warc_web_search_result_blocks_parser")
NAMESPACE_WARC_SPECIAL_CONTENTS_RESULT_BLOCKS_PARSER = uuid5(
    NAMESPACE_AQL, "warc_special_contents_result_blocks_parser")
NAMESPACE_WARC_MAIN_CONTENT_PARSER = uuid5(
    NAMESPACE_AQL, "warc_main_content_parser")
NAMESPACE_WARC_DOWNLOADER = uuid5(NAMESPACE_AQL, "warc_downloader")
