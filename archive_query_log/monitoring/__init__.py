from pathlib import Path

from flask import Flask
from werkzeug import run_simple

from archive_query_log import __name__ as app_name
from archive_query_log.config import Config
from archive_query_log.monitoring.home import home


def monitoring_app(config: Config) -> Flask:
    app = Flask(app_name)
    app.add_url_rule("/", "home", lambda: home(config))
    return app


def run_monitoring(config: Config, host: str, port: int) -> None:
    app = monitoring_app(config)
    if app.template_folder is None:
        template_file_names = []
    else:
        template_dir_path: Path = Path(app.root_path) / app.template_folder
        template_file_paths = [
            template_dir_path / template
            for template in app.jinja_env.list_templates()
        ]
        template_file_names = [
            str(template) for template in template_file_paths
        ]
    run_simple(
        hostname=host,
        port=port,
        application=app,
        use_reloader=True,
        use_debugger=True,
        extra_files=template_file_names,
    )
