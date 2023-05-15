from pyarrow import field, schema, string, timestamp, uint16, uint8, \
    dictionary, int8, list_, struct, uint32
from pyarrow.dataset import partitioning

SERP_SCHEMA = schema(
    fields=[
        field(
            "serp_id",
            string(),
            False,
            metadata={
                "description":
                    "Unique SERP ID (based on a hash of the URL and timestamp "
                    "of the SERP).",
            },
        ),
        field(
            "serp_url",
            string(),
            False,
            metadata={
                "description": "Full URL of the SERP.",
            },
        ),
        field(
            "serp_domain",
            string(),
            False,
            metadata={
                "description": "Domain of the SERP URL.",
            },
        ),
        field(
            "serp_domain_public_suffix",
            string(),
            False,
            metadata={
                "description":
                    "Public suffix (https://publicsuffix.org/) of the SERP "
                    "domain.",
            },
        ),
        field(
            "serp_timestamp",
            timestamp("s"),
            False,
            metadata={
                "description":
                    "Timestamp of the archived snapshot in the Wayback "
                    "Machine.",
            },
        ),
        field(
            "serp_year",
            uint16(),
            False,
            metadata={
                "description":
                    "Year of the archived snapshot in the Wayback Machine.",
            },
        ),
        field(
            "serp_month",
            uint8(),
            False,
            metadata={
                "description":
                    "Month of the archived snapshot in the Wayback Machine.",
            },
        ),
        field(
            "serp_wayback_url",
            string(),
            False,
            metadata={
                "description":
                    "URL of the archived snapshot's contents in the Wayback "
                    "Machine.",
            },
        ),
        field(
            "serp_wayback_raw_url",
            string(),
            False,
            metadata={
                "description":
                    "URL of the archived snapshot's raw contents in the "
                    "Wayback Machine.",
            },
        ),
        field(
            "serp_page",
            uint8(),
            True,
            metadata={
                "description":
                    "SERP page number as parsed from the URL, e.g., 1, 2, "
                    "3 (zero-indexed).",
            },
        ),
        field(
            "serp_offset",
            uint16(),
            True,
            metadata={
                "description":
                    "SERP results offset (start position) as parsed from the "
                    "URL, e.g., 10, 20 (zero-indexed).",
            },
        ),
        field(
            "serp_query_text_url",
            string(),
            True,
            metadata={
                "description": "The SERP's query as parsed from the URL.",
            },
        ),
        field(
            "serp_query_text_url_language",
            dictionary(int8(), string()),
            True,
            metadata={
                "description":
                    "Language identified in the query as parsed from the URL. "
                    "(Google's cld3; min threshold for 'hr' or 'bs': 0.5, for "
                    "others: 0.7.)",
            },
        ),
        field(
            "serp_query_text_html",
            string(),
            True,
            metadata={
                "description":
                    "The SERP's query as parsed from the HTML contents. "
                    "(Can be different from the query parsed from the URL due "
                    "to spelling correction etc.)",
            },
        ),
        field(
            "serp_warc_relative_path",
            string(),
            True,
            metadata={
                "description":
                    "Path of the SERP's WARC file relative to the corpus root "
                    "path.",
            },
        ),
        field(
            "serp_warc_byte_offset",
            uint32(),
            True,
            metadata={
                "description":
                    "Position of the SERP's WARC record's first byte in the "
                    "compressed WARC file.",
            },
        ),
        field(
            "serp_results",
            list_(struct([
                field(
                    "result_id",
                    string(),
                    False,
                    metadata={
                        "description":
                            "Unique document ID (based on a hash of the URL "
                            "and timestamp of the SERP and the result snippet "
                            "rank).",
                    },
                ),
                field(
                    "result_url",
                    string(),
                    False,
                    metadata={
                        "description": "Full URL of the document.",
                    },
                ),
                field(
                    "result_domain",
                    string(),
                    False,
                    metadata={
                        "description": "Domain of the document URL.",
                    },
                ),
                field(
                    "result_domain_public_suffix",
                    string(),
                    False,
                    metadata={
                        "description":
                            "Public suffix (https://publicsuffix.org/) of the "
                            "document domain.",
                    },
                ),
                field(
                    "result_wayback_url",
                    string(),
                    False,
                    metadata={
                        "description":
                            "URL of the document's nearest archived "
                            "snapshot's contents in the Wayback Machine. "
                            "Note that there might not be a snapshot for the "
                            "exact timestamp, but the Wayback Machine instead "
                            "redirects to the nearest available snapshot.",
                    },
                ),
                field(
                    "result_wayback_raw_url",
                    string(),
                    False,
                    metadata={
                        "description":
                            "URL of the document's nearest archived "
                            "snapshot's raw contents in the Wayback Machine. "
                            "Note that there might not be a snapshot for the "
                            "exact timestamp, but the Wayback Machine instead "
                            "redirects to the nearest available snapshot.",
                    },
                ),
                field(
                    "result_snippet_rank",
                    uint8(),
                    False,
                    metadata={
                        "description":
                            "Rank of the document's snippet on the SERP.",
                    },
                ),
                field(
                    "result_snippet_title",
                    string(),
                    False,
                    metadata={
                        "description":
                            "Snippet title of the search result with optional "
                            "highlighting (normalized to ``<em>`` tags, other "
                            "tags removed).",
                    },
                ),
                field(
                    "result_snippet_text",
                    string(),
                    True,
                    metadata={
                        "description":
                            "Snippet text of the search result with optional "
                            "highlighting (normalized to ``<em>`` tags, other "
                            "tags removed).",
                    },
                ),
                field(
                    "result_warc_relative_path",
                    string(),
                    True,
                    metadata={
                        "description":
                            "Path of the SERP's WARC file relative to the "
                            "corpus root path.",
                    },
                ),
                field(
                    "result_warc_byte_offset",
                    uint32(),
                    True,
                    metadata={
                        "description":
                            "Position of the SERP's WARC record's first byte "
                            "in the compressed WARC file.",
                    },
                ),
            ])),
            True,
            metadata={
                "description":
                    "Retrieved results from the SERP in the same order as "
                    "they appear.",
            },
        ),
        field(
            "search_provider_name",
            string(),
            False,
            metadata={
                "description":
                    "Search provider name (domain without the Public Suffix).",
            },
        ),
        field(
            "search_provider_alexa_domain",
            string(),
            False,
            metadata={
                "description":
                    "Main domain of the search provider as it appears in "
                    "Alexa top-1M ranks.",
            },
        ),
        field(
            "search_provider_alexa_domain_public_suffix",
            string(),
            False,
            metadata={
                "description":
                    "Public Suffix (https://publicsuffix.org/) of the search "
                    "provider's main domain.",
            },
        ),
        field(
            "search_provider_alexa_rank",
            uint32(),
            True,
            metadata={
                "description":
                    "Rank of the search provider's main domain in fused Alexa "
                    "top-1M rankings.",
            },
        ),
        field(
            "search_provider_category",
            dictionary(uint8(), string()),
            True,
            metadata={
                "description":
                    "Category of the search provider (manual annotation).",
            },
        ),
    ],
    metadata={
        "description": "A single search engine result page.",
    },
)

RESULT_SCHEMA = schema(
    fields=[
        field(
            "result_id",
            string(),
            False,
            metadata={
                "description":
                    "Unique document ID (based on a hash of the URL and "
                    "timestamp of the SERP and the result snippet rank).",
            },
        ),
        field(
            "result_url",
            string(),
            False,
            metadata={
                "description": "Full URL of the document.",
            },
        ),
        field(
            "result_domain",
            string(),
            False,
            metadata={
                "description": "Domain of the document URL.",
            },
        ),
        field(
            "result_domain_public_suffix",
            string(),
            False,
            metadata={
                "description":
                    "Public suffix (https://publicsuffix.org/) of the "
                    "document domain.",
            },
        ),
        field(
            "result_wayback_url",
            string(),
            False,
            metadata={
                "description":
                    "URL of the document's nearest archived snapshot's "
                    "contents in the Wayback Machine. Note that there might "
                    "not be a snapshot for the exact timestamp, but the "
                    "Wayback Machine instead redirects to the nearest "
                    "available snapshot.",
            },
        ),
        field(
            "result_wayback_raw_url",
            string(),
            False,
            metadata={
                "description":
                    "URL of the document's nearest archived snapshot's raw "
                    "contents in the Wayback Machine. Note that there might "
                    "not be a snapshot for the exact timestamp, but the "
                    "Wayback Machine instead redirects to the nearest "
                    "available snapshot.",
            },
        ),
        field(
            "result_snippet_rank",
            uint8(),
            False,
            metadata={
                "description": "Rank of the document's snippet on the SERP.",
            },
        ),
        field(
            "result_snippet_title",
            string(),
            False,
            metadata={
                "description":
                    "Snippet title of the search result with optional "
                    "highlighting (normalized to ``<em>`` tags, other tags "
                    "removed).",
            },
        ),
        field(
            "result_snippet_text",
            string(),
            True,
            metadata={
                "description":
                    "Snippet text of the search result with optional "
                    "highlighting (normalized to ``<em>`` tags, other tags "
                    "removed).",
            },
        ),
        field(
            "result_warc_relative_path",
            string(),
            True,
            metadata={
                "description":
                    "Path of the SERP's WARC file relative to the corpus root "
                    "path.",
            },
        ),
        field(
            "result_warc_byte_offset",
            uint32(),
            True,
            metadata={
                "description":
                    "Position of the SERP's WARC record's first byte in the "
                    "compressed WARC file.",
            },
        ),
        field(
            "serp_id",
            string(),
            False,
            metadata={
                "description":
                    "Unique SERP ID (based on a hash of the URL and timestamp "
                    "of the SERP).",
            },
        ),
        field(
            "serp_url",
            string(),
            False,
            metadata={
                "description": "Full URL of the SERP.",
            },
        ),
        field(
            "serp_domain",
            string(),
            False,
            metadata={
                "description": "Domain of the SERP URL.",
            },
        ),
        field(
            "serp_domain_public_suffix",
            string(),
            False,
            metadata={
                "description":
                    "Public suffix (https://publicsuffix.org/) of the SERP "
                    "domain.",
            },
        ),
        field(
            "serp_timestamp",
            timestamp("s"),
            False,
            metadata={
                "description":
                    "Timestamp of the archived snapshot in the Wayback "
                    "Machine.",
            },
        ),
        field(
            "serp_year",
            uint16(),
            False,
            metadata={
                "description":
                    "Year of the archived snapshot in the Wayback Machine.",
            },
        ),
        field(
            "serp_month",
            uint8(),
            False,
            metadata={
                "description":
                    "Month of the archived snapshot in the Wayback Machine.",
            },
        ),
        field(
            "serp_wayback_url",
            string(),
            False,
            metadata={
                "description":
                    "URL of the archived snapshot's contents in the Wayback "
                    "Machine.",
            },
        ),
        field(
            "serp_wayback_raw_url",
            string(),
            False,
            metadata={
                "description":
                    "URL of the archived snapshot's raw contents in the "
                    "Wayback Machine.",
            },
        ),
        field(
            "serp_page",
            uint8(),
            True,
            metadata={
                "description":
                    "SERP page number as parsed from the URL, e.g., 1, 2, "
                    "3 (zero-indexed).",
            },
        ),
        field(
            "serp_offset",
            uint16(),
            True,
            metadata={
                "description":
                    "SERP results offset (start position) as parsed from the "
                    "URL, e.g., 10, 20 (zero-indexed).",
            },
        ),
        field(
            "serp_query_text_url",
            string(),
            True,
            metadata={
                "description": "The SERP's query as parsed from the URL.",
            },
        ),
        field(
            "serp_query_text_url_language",
            dictionary(int8(), string()),
            True,
            metadata={
                "description":
                    "Language identified in the query as parsed from the URL. "
                    "(Google's cld3; min threshold for 'hr' or 'bs': 0.5, for "
                    "others: 0.7.)",
            },
        ),
        field(
            "serp_query_text_html",
            string(),
            True,
            metadata={
                "description":
                    "The SERP's query as parsed from the HTML contents.",
            },
        ),
        field(
            "serp_warc_relative_path",
            string(),
            True,
            metadata={
                "description":
                    "Path of the SERP's WARC file relative to the corpus root "
                    "path.",
            },
        ),
        field(
            "serp_warc_byte_offset",
            uint32(),
            True,
            metadata={
                "description":
                    "Position of the SERP's WARC record's first byte in the "
                    "compressed WARC file.",
            },
        ),
        field(
            "search_provider_name",
            string(),
            False,
            metadata={
                "description":
                    "Search provider name (domain without the Public Suffix).",
            },
        ),
        field(
            "search_provider_alexa_domain",
            string(),
            False,
            metadata={
                "description":
                    "Main domain of the search provider as it appears in "
                    "Alexa top-1M ranks.",
            },
        ),
        field(
            "search_provider_alexa_domain_public_suffix",
            string(),
            False,
            metadata={
                "description":
                    "Public Suffix (https://publicsuffix.org/) of the search "
                    "provider's main domain.",
            },
        ),
        field(
            "search_provider_alexa_rank",
            uint32(),
            True,
            metadata={
                "description":
                    "Rank of the search provider's main domain in fused Alexa "
                    "top-1M rankings.",
            },
        ),
        field(
            "search_provider_category",
            dictionary(uint8(), string()),
            True,
            metadata={
                "description":
                    "Category of the search provider (manual annotation).",
            },
        ),
    ],
    metadata={
        "description": "A single result from a SERP.",
    },
)

SERP_PARTITIONING = partitioning(
    schema=schema(
        fields=[
            field(
                "serp_domain_public_suffix",
                string(),
                False,
                metadata={
                    "description":
                        "Public suffix (https://publicsuffix.org/) of the "
                        "SERP domain.",
                },
            ),
            field(
                "serp_domain",
                string(),
                False,
                metadata={
                    "description": "Domain of the SERP URL.",
                },
            ),
            field(
                "serp_year",
                uint16(),
                False,
                metadata={
                    "description":
                        "Year of the archived snapshot in the Wayback "
                        "Machine.",
                },
            ),
            field(
                "serp_month",
                uint8(),
                False,
                metadata={
                    "description":
                        "Month of the archived snapshot in the Wayback "
                        "Machine.",
                },
            ),
        ],
    ),
    flavor="hive",
)

RESULT_PARTITIONING = SERP_PARTITIONING
