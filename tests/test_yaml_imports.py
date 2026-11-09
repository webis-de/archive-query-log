from pathlib import Path
from types import SimpleNamespace
from typing import Any

from diskcache_community import Cache, Disk
from pytest import MonkeyPatch

from archive_query_log.config import Config
from archive_query_log.imports import yaml

_planted_calls: list[str] = []


def _planted() -> str:
    _planted_calls.append("planted")
    return "Planted"


class _Planted:
    def __reduce__(self) -> tuple:
        return (_planted, ())


def test_import_providers_ignores_planted_cached_name(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    services_path = tmp_path / "services.yaml"
    services_path.write_text(
        "- domains: [example.org]\n"
        "  query_parsers: [{}]\n"
        "  focused_url_prefixes: [/search]\n"
    )
    cache_path = tmp_path / "provider-names"
    with Cache(str(cache_path), disk=Disk) as other_writer:
        other_writer.set("example.org", _Planted())
    names: list[str | None] = []

    def add_provider(**kwargs: Any) -> None:
        names.append(kwargs["name"])

    monkeypatch.setattr(yaml, "add_provider", add_provider)
    monkeypatch.setattr(yaml, "whois", lambda domain: SimpleNamespace(org=None))
    monkeypatch.setattr("builtins.input", lambda prompt: "Example")

    yaml.import_providers(
        config=Config(),
        services_path=services_path,
        cache_path=cache_path,
        review=None,
        no_merge=False,
        auto_merge=False,
    )

    assert names == ["Example"]
    assert _planted_calls == []
