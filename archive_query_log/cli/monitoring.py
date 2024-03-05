from click import group, option

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config


@group()
def monitoring() -> None:
    pass


@monitoring.command()
@option("-h", "--host", type=str, default="127.0.0.1",
        help="The interface to bind to.")
@option("-p", "--port", type=int, default=5000,
        help="The port to bind to.")
@pass_config
def run(
        config: Config,
        host: str,
        port: int,
) -> None:
    from archive_query_log.monitoring import run_monitoring
    run_monitoring(config, host, port)
