import pytest
import mimetypes
from pathlib import Path
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

#simulates uploading test files for test cases
def load_fixture_file(filename, content_type=None):
    path = Path(__file__).parent/"fixtures"/filename
    if content_type is None:
        content_type, _ = mimetypes.guess_type(filename)
    return SimpleUploadedFile(filename, path.read_bytes(), content_type=content_type)