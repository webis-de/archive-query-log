from typing import Annotated

from cyclopts import App, Parameter
from cyclopts.types import Port

from archive_query_log.cli.util import Domain
from archive_query_log.config import Config


monitoring = App(
    name="monitoring",
    help="Manage monitoring tasks.",
)


@monitoring.command()
def run(
    *,
    host: Annotated[Domain, Parameter(alias="-h")] = "127.0.0.1",
    port: Annotated[Port, Parameter(alias="-p")] = 5000,
    config: Config,
) -> None:
    """
    Run the monitoring server.

    :param host: The host interface to bind the server to.
    :param port: The port to bind the server to.
    """

    from archive_query_log.monitoring import run_monitoring

    run_monitoring(config, host, port)
