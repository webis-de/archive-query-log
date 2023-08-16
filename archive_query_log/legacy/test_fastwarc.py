def test_fastwarc_installed():
    import fastwarc
    assert fastwarc

    from fastwarc import GZipStream
    assert GZipStream

    from fastwarc import FileStream
    assert FileStream

    from fastwarc import ArchiveIterator
    assert ArchiveIterator

    from fastwarc import WarcRecordType
    assert WarcRecordType

    from fastwarc import WarcRecord
    assert WarcRecord

    # pylint: disable=no-name-in-module
    from fastwarc.stream_io import PythonIOStreamAdapter
    assert PythonIOStreamAdapter
