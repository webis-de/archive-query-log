def test_fastwarc_installed():
    import fastwarc
    assert fastwarc is not None

    from fastwarc import GZipStream
    assert GZipStream is not None

    from fastwarc import FileStream
    assert FileStream is not None

    from fastwarc import ArchiveIterator
    assert ArchiveIterator is not None

    from fastwarc import WarcRecordType
    assert WarcRecordType is not None

    from fastwarc import WarcRecord
    assert WarcRecord is not None

    # pylint: disable=no-name-in-module
    from fastwarc.stream_io import PythonIOStreamAdapter
    assert PythonIOStreamAdapter is not None
