from pathlib import Path

from click import group, option
from werkzeug import run_simple

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.web import flask_app


@group()
def monitoring():
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
):
    app = flask_app(config)
    template_dir_path = Path(app.root_path) / app.template_folder
    template_file_paths = [
        template_dir_path / template
        for template in app.jinja_env.list_templates()
    ]
    template_file_names = [str(template) for template in template_file_paths]
    run_simple(
        hostname=host,
        port=port,
        application=app,
        use_reloader=True,
        use_debugger=True,
        extra_files=template_file_names,
    )
