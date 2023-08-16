from flask import Flask

from archive_query_log import __name__ as app_name
from archive_query_log.new.config import Config
from archive_query_log.new.web.home import home


def flask_app(config: Config) -> Flask:
    flask = Flask(app_name)
    flask.add_url_rule("/", "home", lambda: home(config))
    return flask
