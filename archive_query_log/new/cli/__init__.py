from typing import Any

from click import group, Context, Parameter, echo, option

from archive_query_log import __version__
from archive_query_log.new.cli.archive import archive
from archive_query_log.new.cli.provider import provider


def print_version(
        context: Context,
        _parameter: Parameter,
        value: Any,
) -> None:
    if not value or context.resilient_parsing:
        return
    echo(__version__)
    context.exit()


@group()
@option("-V", "--version", is_flag=True, callback=print_version,
        expose_value=False, is_eager=True)
def cli() -> None:
    pass


cli.add_command(archive)
cli.add_command(provider)
