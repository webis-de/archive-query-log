from click import group, option
from werkzeug import run_simple

from archive_query_log.new.web import app


@group()
def monitoring():
    pass


@monitoring.command()
@option("-h", "--host", type=str, default="127.0.0.1",
        help="The interface to bind to.")
@option("-p", "--port", type=int, default=5000,
        help="The port to bind to.")
def run(host, port):
    run_simple(host, port, app)
