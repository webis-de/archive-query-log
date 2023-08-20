from click import group

from archive_query_log.legacy.cli.alexa import alexa
from archive_query_log.legacy.cli.corpus import corpus_command
from archive_query_log.legacy.cli.external import external
from archive_query_log.legacy.cli.index import index_command
from archive_query_log.legacy.cli.make import make_group


@group()
def main():
    pass


main.add_command(alexa)
main.add_command(corpus_command)
main.add_command(external)
main.add_command(index_command)
main.add_command(make_group)
