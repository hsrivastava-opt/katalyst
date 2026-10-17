import pytest


@pytest.fixture(autouse=True)
def isolated_local_backend(monkeypatch, tmp_path):
    monkeypatch.setenv('KATALYST_AUTH_MODE', 'demo')
    monkeypatch.setenv('KATALYST_STORE', 'sqlite')
    monkeypatch.setenv('KATALYST_DB', str(tmp_path / 'projects.sqlite'))
