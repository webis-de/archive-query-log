from io import BytesIO
from shutil import copyfileobj
from warnings import warn

from warcio.recordloader import ArcWarcRecord


def read_html_string(record: ArcWarcRecord) -> str | None:
    mime_type: str | None = record.http_headers.get_header("Content-Type")
    if mime_type is None:
        warn(UserWarning("No MIME type given."))
        return None
    mime_type = mime_type.split(";", maxsplit=1)[0]
    if mime_type != "text/xml":
        return None
    with BytesIO() as content_buffer:
        copyfileobj(record.content_stream(), content_buffer)
        return content_buffer.getvalue().decode("utf-8")
