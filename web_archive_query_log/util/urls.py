from urllib.parse import quote


def safe_quote_url(url: str) -> str:
    return quote(url, safe="")
