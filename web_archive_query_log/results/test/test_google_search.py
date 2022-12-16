from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import IO

from pytest import raises, mark

from web_archive_query_log.cli.make import archived_urls_command, \
    archived_query_urls_command


# Needed because dataclasses-json uses deprecated features of marshmallow.
@mark.filterwarnings("ignore:The 'default' argument to fields is deprecated")
def test_archived_urls_chatnoir():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        assert temp_path.exists()
        assert temp_path.is_dir()
        # The CLI should exit with status code 0.
        with raises(SystemExit, match="0"):
            archived_urls_command([
                "chatnoir",
                "-d", str(temp_path),
            ])
        jsonl_path = temp_path / "archived-urls" / \
                     "chatnoir" / "chatnoir.eu" / "0000000000.jsonl.gz"
        assert jsonl_path.exists()
        assert jsonl_path.is_file()
        with GzipFile(jsonl_path, "r") as file:
            file: IO[bytes]
            with TextIOWrapper(file, "utf8") as lines:
                # Only lines with a specific timestamp.
                # Otherwise, the test might break once new snapshots are added.
                lines = (
                    line for line in lines
                    if "1653041046" in line
                )
                lines = list(lines)
        assert len(lines) == 20
        assert all('"url": ' in line for line in lines)
        assert all('"timestamp": ' in line for line in lines)
        assert all("chatnoir.eu" in line for line in lines)
        assert any("Monkeypox" in line for line in lines)


# Needed because dataclasses-json uses deprecated features of marshmallow.
@mark.filterwarnings("ignore:The 'default' argument to fields is deprecated")
def test_archived_query_urls_chatnoir():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        assert temp_path.exists()
        assert temp_path.is_dir()
        # The CLI should exit with status code 0.
        with raises(SystemExit, match="0"):
            archived_urls_command([
                "chatnoir",
                "-d", str(temp_path),
            ])
        # The CLI should exit with status code 0.
        with raises(SystemExit, match="0"):
            archived_query_urls_command([
                "chatnoir",
                "-d", str(temp_path),
            ])
        jsonl_path = temp_path / "archived-query-urls" / \
                     "chatnoir" / "chatnoir.eu" / "0000000000.jsonl.gz"
        assert jsonl_path.exists()
        assert jsonl_path.is_file()
        with GzipFile(jsonl_path, "r") as file:
            file: IO[bytes]
            with TextIOWrapper(file, "utf8") as lines:
                # Only lines with a specific timestamp.
                # Otherwise, the test might break once new snapshots are added.
                lines = (
                    line for line in lines
                    if "1653041046" in line
                )
                lines = list(lines)
        assert len(lines) == 7
        assert all('"url": ' in line for line in lines)
        assert all('"timestamp": ' in line for line in lines)
        assert all("chatnoir.eu" in line for line in lines)
        assert all('"query": ' in line for line in lines)
        assert all('"page": ' in line for line in lines)
        assert all('"offset": ' in line for line in lines)
        assert any("Monkeypox" in line for line in lines)
