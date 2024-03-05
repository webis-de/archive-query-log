from bleach import clean
from bs4 import Tag

_HIGHLIGHT_TAGS = ["em", "strong", "mark", "b", "i", "u"]


def clean_html(html: str | Tag) -> str:
    if isinstance(html, Tag):
        html = html.decode_contents()
    html = clean(
        html,
        tags=_HIGHLIGHT_TAGS,
        attributes=[],
        protocols=[],
        strip=True,
        strip_comments=True,
    )
    for tag in _HIGHLIGHT_TAGS:
        html = html.replace(f"<{tag}>", "<em>")
        html = html.replace(f"</{tag}>", "</em>")
    html = html.strip()
    return html
