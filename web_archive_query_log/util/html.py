from bleach import clean
from bs4 import Tag


def clean_html(html: str | Tag, highlight: str | None = None) -> str:
    if isinstance(html, Tag):
        html = html.decode_contents()
    html = clean(
        html,
        tags=[highlight] if highlight is not None else [],
        attributes=[],
        protocols=[],
        strip=True,
        strip_comments=True,
    )
    if highlight != "em":
        html = html.replace(f"<{highlight}>", "<em>")
        html = html.replace(f"</{highlight}>", "</em>")
    html = html.strip()
    return html
