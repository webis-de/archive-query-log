from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


# TODO: Replace with dfir-unfurl.

TRACKING_PARAMS = {
    # Google Analytics
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    # Facebook
    "fbclid",
    # Google Ads
    "gclid",
    "gclsrc",
    # Microsoft
    "msclkid",
    # Mailchimp
    "mc_cid",
    "mc_eid",
    # Others
    "ref",
    "_ga",
    "campaign_id",
}


def remove_tracking_parameters(url: str) -> str:
    """Remove common tracking parameters from URL."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Filter out tracking parameters
    cleaned_params = {
        key: value for key, value in query_params.items() if key not in TRACKING_PARAMS
    }

    # Rebuild query string
    cleaned_query = urlencode(cleaned_params, doseq=True)

    # Rebuild URL
    cleaned_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            cleaned_query,
            parsed.fragment,
        )
    )

    return cleaned_url
