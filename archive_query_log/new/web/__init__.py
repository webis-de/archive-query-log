from flask import Flask

from archive_query_log import __name__ as name

app = Flask(name)


@app.route("/")
def hello():
    return "Hello, World!"
