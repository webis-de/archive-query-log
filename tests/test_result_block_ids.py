"""
Guards that derived result-block IDs are reproducible across processes.

The IDs were previously derived via the builtin `hash()`, which is salted per
interpreter, so the same input produced different IDs in every run. A
same-process assertion cannot catch that -- `hash()` is stable *within* one
interpreter -- so the expected values below are deliberately hard-coded.
Run the suite under two different `PYTHONHASHSEED` values to prove stability.
"""

from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from re import compile as re_compile
from typing import Iterator
from uuid import UUID, uuid5

from pydantic import HttpUrl
from pytest import MonkeyPatch
from warcio import ArchiveIterator
from warcio.recordloader import ArcWarcRecord
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter

from archive_query_log.namespaces import NAMESPACE_WEB_SEARCH_RESULT_BLOCK
from archive_query_log.orm import (
    InnerArchive,
    InnerCapture,
    InnerProvider,
    Serp,
    WarcLocation,
    WebSearchResultBlock,
)
from archive_query_log.parsers import warc_web_search_result_blocks as module
from archive_query_log.parsers.utils import content_digest
from archive_query_log.parsers.warc_web_search_result_blocks import (
    XpathWarcWebSearchResultBlocksParser,
    parse_serp_warc_web_search_result_blocks_action,
)
from archive_query_log.utils.warc import WarcStore


_TIMESTAMP = datetime(2020, 6, 1, 12, 0, 0, tzinfo=UTC)
_SERP_URL = "https://example.com/search?q=test"
_INDEX = "web_search_result_blocks"

_HTML = (
    b"<html><body><div id='search'><div id='rso'>"
    b"<div class='g'><h3><a href='https://example.org/a'>Title A</a></h3>"
    b"<span class='st'>Snippet A</span></div>"
    b"<div class='g'><h3><a href='https://example.org/b'>Title B</a></h3>"
    b"<span class='st'>Snippet B</span></div>"
    b"</div></div></body></html>"
)

# Hard-coded so that a change of the ID derivation must be a deliberate edit.
_EXPECTED_DIGEST = "aca4bd1f7c671d07b0e27f8e3dcc2c96"
_EXPECTED_BLOCK_IDS = [
    UUID("060408b2-6e23-5806-b6ff-5110e63a1aba"),
    UUID("b93ab366-5d80-5785-acd0-7f27e798ae08"),
]


class _InlineWarcStore(WarcStore):
    """A WARC store serving one in-memory record, so the test needs no fixture."""

    def __init__(self, payload: bytes, url: str) -> None:
        buffer = BytesIO()
        writer = WARCWriter(buffer, gzip=False)
        writer.write_record(
            writer.create_warc_record(
                url,
                "response",
                payload=BytesIO(payload),
                http_headers=StatusAndHeaders(
                    "200 OK",
                    [("Content-Type", "text/html; charset=utf-8")],
                    protocol="HTTP/1.1",
                ),
            )
        )
        self._buffer = buffer

    @contextmanager
    def read(self, location: WarcLocation) -> Iterator[ArcWarcRecord]:
        self._buffer.seek(0)
        yield next(ArchiveIterator(self._buffer))


def _serp() -> Serp:
    return Serp(
        index="serps",
        id=UUID(int=7),
        last_modified=_TIMESTAMP,
        archive=InnerArchive(
            id=UUID(int=2),
            cdx_api_url=HttpUrl("https://web.archive.org/cdx/search/cdx"),
            memento_api_url=HttpUrl("https://web.archive.org/web"),
        ),
        provider=InnerProvider(
            id=UUID(int=3),
            domain="example.com",
            url_path_prefix="/search",
        ),
        capture=InnerCapture(
            id=UUID(int=0),
            url=HttpUrl(_SERP_URL),
            timestamp=_TIMESTAMP,
            digest="3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ",
        ),
        url_query="test",
        warc_location=WarcLocation(file="test.warc", offset=0, length=1),
    )


def _parser() -> XpathWarcWebSearchResultBlocksParser:
    return XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID(int=3),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath=(
            "//div[@id='search']//div[@id='rso']"
            "//div[contains(concat(' ',normalize-space(@class),' '),' g ')]"
        ),
        url_xpath="h3//a/@href",
        title_xpath="h3//text()",
        text_xpath="span[@class='st']//text()",
    )


def test_content_digest_is_stable_across_processes() -> None:
    assert content_digest("<div>Test</div>") == _EXPECTED_DIGEST


def test_content_digest_distinguishes_content() -> None:
    assert content_digest("<div>A</div>") != content_digest("<div>B</div>")


def test_block_id_derivation_is_reproducible() -> None:
    """
    Compose an ID exactly as the parser does and pin the result.
    """
    serp = _serp()
    parser = _parser()
    components = (
        str(serp.id),
        str(parser.id),
        content_digest("<div>Test</div>"),
        "0",
    )
    block_id = uuid5(NAMESPACE_WEB_SEARCH_RESULT_BLOCK, ":".join(components))
    assert block_id == UUID("327bc95f-2f20-59be-99ec-0592e8b15bf4")


def test_parsed_block_ids_are_reproducible(monkeypatch: MonkeyPatch) -> None:
    """
    End-to-end over the real parse path: the IDs of the emitted block documents
    must match hard-coded values, in this process and any other.
    """
    parser = _parser()
    monkeypatch.setattr(
        module,
        "WARC_WEB_SEARCH_RESULT_BLOCKS_PARSERS",
        (parser,),
    )

    actions = list(
        parse_serp_warc_web_search_result_blocks_action(
            serp=_serp(),
            warc_store=_InlineWarcStore(_HTML, _SERP_URL),
            index_web_search_result_blocks=_INDEX,
        )
    )

    creates = [action for action in actions if action["_op_type"] == "create"]
    assert [UUID(action["_id"]) for action in creates] == _EXPECTED_BLOCK_IDS

    # The SERP's block-ID list must reference exactly the created blocks,
    # otherwise `GET /serps/compare` resolves IDs that do not exist.
    updates = [action for action in actions if action["_op_type"] == "update"]
    assert len(updates) == 1
    referenced = [
        UUID(block["id"])
        for block in updates[0]["doc"]["warc_web_search_result_blocks"]
    ]
    assert referenced == _EXPECTED_BLOCK_IDS


def test_parsed_blocks_are_writable(monkeypatch: MonkeyPatch) -> None:
    """
    The block documents must carry every field the ORM requires, and name the
    index to write to. Both were missing, so the parse stage could not run.
    """
    monkeypatch.setattr(
        module,
        "WARC_WEB_SEARCH_RESULT_BLOCKS_PARSERS",
        (_parser(),),
    )

    actions = list(
        parse_serp_warc_web_search_result_blocks_action(
            serp=_serp(),
            warc_store=_InlineWarcStore(_HTML, _SERP_URL),
            index_web_search_result_blocks=_INDEX,
        )
    )
    creates = [action for action in actions if action["_op_type"] == "create"]
    assert len(creates) == 2

    for action in creates:
        assert action["_index"] == _INDEX
        assert action["mimetype"] == "text/html"
        # `path` records the selector that matched the block.
        assert action["path"] == _parser().xpath
        for field, info in WebSearchResultBlock.model_fields.items():
            if info.is_required():
                assert field in action or field == "id", (
                    f"required field {field!r} missing from create action"
                )
