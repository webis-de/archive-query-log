from typing import Any


def unfurl(url: str) -> dict[str, Any]:
    from urllib.parse import urlparse, parse_qs, unquote
    import tldextract

    parsed = urlparse(url)

    domain_info = tldextract.extract(url)

    path_segments = [segment for segment in parsed.path.split("/") if segment]

    query_params = parse_qs(parsed.query, keep_blank_values=True)

    decoded_params = {
        key: unquote(values[0]) if len(values) == 1 else [unquote(v) for v in values]
        for key, values in query_params.items()
    }

    return {
        "scheme": parsed.scheme,
        "netloc": parsed.netloc,
        "port": parsed.port,
        "domain_parts": {
            "subdomain": domain_info.subdomain if domain_info.subdomain else None,
            "domain": domain_info.domain,
            "suffix": domain_info.suffix,
            "registered_domain": domain_info.top_domain_under_public_suffix,
        },
        "path": parsed.path,
        "path_segments": path_segments,
        "query_parameters": decoded_params,
        "fragment": parsed.fragment if parsed.fragment else None,
    }
