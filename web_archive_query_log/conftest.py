from approvaltests import set_default_reporter, DiffReporter
from pytest import fixture


def configure_approvaltests():
    set_default_reporter(DiffReporter())


@fixture(scope="session", autouse=True)
def set_default_reporter_for_all_tests():
    configure_approvaltests()
