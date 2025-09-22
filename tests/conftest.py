from approvaltests import set_default_reporter, DiffReporter
from pytest import fixture


@fixture(scope="session", autouse=True)
def set_default_reporter_for_all_tests() -> None:
    set_default_reporter(DiffReporter())
