from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

from pydantic import HttpUrl
from pytest import mark
from warcio.recordloader import ArcWarcRecord
from warcio.statusandheaders import StatusAndHeaders

from archive_query_log.captures import _organic_result_capture_update_action
from archive_query_log.downloaders.warc import (
    _PseudoOrganicResult,
    _WrapperWarcRecord,
    _organic_result_warc_update_action,
)
from archive_query_log.orm import (
    InnerArchive,
    InnerCapture,
    InnerParser,
    InnerProvider,
    InnerSerp,
    WarcLocation,
    OrganicResult,
)


_SERP_TIMESTAMP = datetime(2020, 6, 1, 12, 0, 0, tzinfo=UTC)
_LANDING_PAGE_URL = "https://example.org/landing-page"
_EMPTY_DIGEST = "3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ"


def _inner_capture(timestamp: datetime) -> InnerCapture:
    return InnerCapture(
        id=UUID(int=0),
        url=HttpUrl(_LANDING_PAGE_URL),
        timestamp=timestamp,
        status_code=200,
        digest=_EMPTY_DIGEST,
        mimetype="text/html",
    )


def _warc_location() -> WarcLocation:
    return WarcLocation(file="test.warc.gz", offset=0, length=100)


def _dummy_warc_record() -> ArcWarcRecord:
    return ArcWarcRecord(
        "warc", "resource", StatusAndHeaders("", []), BytesIO(b""), None, None, 0
    )


def _organic_result(
    capture_before_serp: InnerCapture | None = None,
    capture_after_serp: InnerCapture | None = None,
    warc_location_before_serp: WarcLocation | None = None,
    warc_location_after_serp: WarcLocation | None = None,
) -> OrganicResult:
    return OrganicResult(
        id=UUID(int=1),
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
        serp_capture=_inner_capture(_SERP_TIMESTAMP),
        serp=InnerSerp(id=UUID(int=4)),
        content="<div>Test</div>",
        parser=InnerParser(
            id=UUID(int=5),
            should_parse=False,
            last_parsed=_SERP_TIMESTAMP,
        ),
        rank=0,
        url=HttpUrl(_LANDING_PAGE_URL),
        capture_before_serp=capture_before_serp,
        capture_after_serp=capture_after_serp,
        warc_location_before_serp=warc_location_before_serp,
        warc_location_after_serp=warc_location_after_serp,
    )


@mark.parametrize("before_serp", [True, False])
def test_warc_update_action_updates_declared_fields(before_serp: bool) -> None:
    """
    The downloader must mark exactly the fields that its selection query filters
    on, otherwise downloaded blocks are never marked as downloaded.
    """
    action = _organic_result_warc_update_action(
        result_block=_organic_result(),
        location=_warc_location(),
        downloader_id=UUID(int=6),
        before_serp=before_serp,
    )

    assert set(action["doc"]) <= set(OrganicResult.model_fields)

    suffix = "before_serp" if before_serp else "after_serp"
    other_suffix = "after_serp" if before_serp else "before_serp"
    assert action["doc"][f"warc_location_{suffix}"] is not None
    assert action["doc"][f"warc_downloader_{suffix}"]["should_download"] is False
    # The other side of the SERP is downloaded separately and must be untouched.
    assert f"warc_location_{other_suffix}" not in action["doc"]
    assert f"warc_downloader_{other_suffix}" not in action["doc"]


def test_capture_update_action_marks_captures_as_fetched() -> None:
    action = _organic_result_capture_update_action(
        result_block=_organic_result(),
        capture_before_serp=_inner_capture(_SERP_TIMESTAMP),
        capture_after_serp=_inner_capture(_SERP_TIMESTAMP),
    )

    assert set(action["doc"]) <= set(OrganicResult.model_fields)
    assert action["doc"]["should_fetch_captures"] is False
    assert action["doc"]["last_fetched_captures"] is not None


def test_capture_update_action_keeps_warcs_of_unchanged_captures() -> None:
    """
    Re-fetching captures must not discard already downloaded WARCs if the
    captures did not change, because they would have to be downloaded again.
    """
    capture = _inner_capture(_SERP_TIMESTAMP)
    result_block = _organic_result(
        capture_before_serp=capture,
        capture_after_serp=capture,
        warc_location_before_serp=_warc_location(),
        warc_location_after_serp=_warc_location(),
    )

    action = _organic_result_capture_update_action(
        result_block=result_block,
        # Equal to the stored captures, but not the same objects.
        capture_before_serp=_inner_capture(_SERP_TIMESTAMP),
        capture_after_serp=_inner_capture(_SERP_TIMESTAMP),
    )

    assert "warc_location_before_serp" not in action["doc"]
    assert "warc_downloader_before_serp" not in action["doc"]
    assert "warc_location_after_serp" not in action["doc"]
    assert "warc_downloader_after_serp" not in action["doc"]


def test_capture_update_action_resets_warcs_of_changed_captures() -> None:
    result_block = _organic_result(
        capture_before_serp=_inner_capture(_SERP_TIMESTAMP),
        warc_location_before_serp=_warc_location(),
    )

    action = _organic_result_capture_update_action(
        result_block=result_block,
        capture_before_serp=_inner_capture(datetime(2019, 1, 1, tzinfo=UTC)),
        capture_after_serp=None,
    )

    assert action["doc"]["warc_location_before_serp"] is None
    assert action["doc"]["warc_downloader_before_serp"] is None


def test_capture_update_action_resets_warcs_of_removed_captures() -> None:
    result_block = _organic_result(
        capture_before_serp=_inner_capture(_SERP_TIMESTAMP),
        warc_location_before_serp=_warc_location(),
    )

    action = _organic_result_capture_update_action(
        result_block=result_block,
        capture_before_serp=None,
        capture_after_serp=None,
    )

    assert action["doc"]["warc_location_before_serp"] is None
    assert action["doc"]["warc_downloader_before_serp"] is None


def test_capture_update_action_treats_sides_independently() -> None:
    """
    A change on one side of the SERP must not discard the other side's WARC.
    """
    capture_before_serp = _inner_capture(_SERP_TIMESTAMP)
    result_block = _organic_result(
        capture_before_serp=capture_before_serp,
        capture_after_serp=None,
        warc_location_before_serp=_warc_location(),
    )

    action = _organic_result_capture_update_action(
        result_block=result_block,
        capture_before_serp=_inner_capture(_SERP_TIMESTAMP),
        capture_after_serp=_inner_capture(datetime(2021, 1, 1, tzinfo=UTC)),
    )

    assert "warc_location_before_serp" not in action["doc"]
    assert "warc_downloader_before_serp" not in action["doc"]
    assert action["doc"]["warc_location_after_serp"] is None
    assert action["doc"]["warc_downloader_after_serp"] is None


@mark.parametrize("before_serp", [True, False])
def test_pseudo_organic_result_round_trips_through_wrapper(before_serp: bool) -> None:
    """
    The before/after-SERP side must survive being wrapped into the
    WARC-Wrapped header and read back, both immediately and after being
    re-wrapped by its type alone (as happens when re-reading from the WARC
    cache), since both before-SERP and after-SERP downloads share one cache.
    """
    pseudo_result = _PseudoOrganicResult(
        id=UUID(int=1),
        index="organic_results",
        seq_no=7,
        before_serp=before_serp,
    )

    # Simulates writing the record to the WARC cache.
    written: _WrapperWarcRecord[_PseudoOrganicResult] = _WrapperWarcRecord(
        _dummy_warc_record(), pseudo_result
    )
    assert written.wrapped == pseudo_result

    # Simulates re-reading the cached record later, when only the type
    # (not the original instance) is known.
    reread = _WrapperWarcRecord(written, _PseudoOrganicResult)

    assert reread.wrapped == pseudo_result
    assert reread.wrapped.before_serp is before_serp
