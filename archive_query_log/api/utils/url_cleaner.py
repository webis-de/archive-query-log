from urllib.parse import urlencode, urlunsplit

from pydantic import HttpUrl


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


def remove_tracking_parameters(url: HttpUrl) -> HttpUrl:
    """
    Remove common tracking parameters from URL.
    """
    # Filter out tracking parameters.
    cleaned_params = {
        key: value for key, value in url.query_params() if key not in TRACKING_PARAMS
    }

    # Rebuild query string.
    cleaned_query = urlencode(cleaned_params, doseq=True)

    # Rebuild URL
    cleaned_url = urlunsplit(
        (
            url.scheme,
            url.host,
            url.path,
            cleaned_query,
            url.fragment,
        )
    )
    return HttpUrl(cleaned_url)
