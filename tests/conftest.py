"""Owned Windows fixture directories must satisfy the production ACL boundary."""
import os
import pytest

@pytest.fixture(autouse=True)
def private_windows_fixture_directory(request):
    if os.name == 'nt' and 'tmp_path' in request.fixturenames:
        from aletheia.storage.private_files import windows_private_directory
        windows_private_directory(request.getfixturevalue('tmp_path'))
