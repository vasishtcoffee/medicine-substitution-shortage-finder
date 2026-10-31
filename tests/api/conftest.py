import pytest

from api_support import make_client


@pytest.fixture
def anon():
    return make_client()


@pytest.fixture
def admin():
    return make_client("admin")


@pytest.fixture
def ph1():
    return make_client("pharmacist1")


@pytest.fixture
def ph2():
    return make_client("pharmacist2")


@pytest.fixture
def pat1():
    return make_client("patient1")


@pytest.fixture
def pat2():
    return make_client("patient2")
