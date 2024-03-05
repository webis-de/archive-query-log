from archive_query_log.legacy.config import SERVICES

if __name__ == '__main__':
    num_url_prefixes = sum(
        len(service.focused_url_prefixes)
        for service in SERVICES.values()
    )
    print(f"Number of URL prefixes: {num_url_prefixes}")
    num_query_parsers = sum(
        len(service.query_parsers)
        for service in SERVICES.values()
    )
    print(f"Number of query parsers: {num_query_parsers}")
    num_page_parsers = sum(
        len(service.page_parsers)
        for service in SERVICES.values()
    )
    print(f"Number of page parsers: {num_page_parsers}")
    num_offset_parsers = sum(
        len(service.offset_parsers)
        for service in SERVICES.values()
    )
    print(f"Number of offset parsers: {num_offset_parsers}")
    num_interpreted_query_parsers = sum(
        len(service.interpreted_query_parsers)
        for service in SERVICES.values()
    )
    print(
        f"Number of interpreted query parsers: {num_interpreted_query_parsers}"
    )
    num_results_parsers = sum(
        len(service.results_parsers)
        for service in SERVICES.values()
    )
    print(f"Number of results parsers: {num_results_parsers}")
