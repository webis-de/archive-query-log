from uuid import uuid5, NAMESPACE_URL

NAMESPACE_AQL = uuid5(NAMESPACE_URL, "aql")
NAMESPACE_SOURCE = uuid5(NAMESPACE_AQL, "filter")
NAMESPACE_CAPTURE = uuid5(NAMESPACE_AQL, "capture")
NAMESPACE_SERP = uuid5(NAMESPACE_AQL, "serp")
NAMESPACE_RESULT = uuid5(NAMESPACE_AQL, "result")
NAMESPACE_url_query_parser = uuid5(NAMESPACE_AQL, "url_query_parser")
NAMESPACE_url_page_parser = uuid5(NAMESPACE_AQL, "url_page_parser")
NAMESPACE_url_offset_parser = uuid5(NAMESPACE_AQL, "url_offset_parser")
NAMESPACE_url_language_parser = uuid5(NAMESPACE_AQL, "url_language_parser")
NAMESPACE_serp_query_parser = uuid5(NAMESPACE_AQL, "serp_query_parser")
NAMESPACE_serp_snippets_parser = uuid5(NAMESPACE_AQL, "serp_snippets_parser")
NAMESPACE_serp_direct_answer_parser = uuid5(
    NAMESPACE_AQL, "serp_direct_answer_parser")
