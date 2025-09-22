from typing import Annotated

from cyclopts import App, Parameter
from cyclopts.types import Port
from pydantic import IPvAnyInterface

from archive_query_log.cli.util import Domain
from archive_query_log.config import Config


api = App(
    name="api",
    help="Manage HTTP API and monitoring.",
)


@api.command()
def run(
    *,
    host: Annotated[Domain | IPvAnyInterface, Parameter(alias="-h")] = "127.0.0.1",
    port: Annotated[Port, Parameter(alias="-p")] = 5000,
) -> None:
    """
    Run the monitoring server.

    :param host: The host interface to bind the server to.
    :param port: The port to bind the server to.
    """

    from uvicorn import run

    run(
        "archive_query_log.api.__init__:app",
        host=str(host),
        port=port,
        log_level="info",
        reload=True,
    )
