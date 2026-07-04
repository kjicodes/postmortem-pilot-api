import pytest
import uuid
from unittest.mock import patch
from django.urls import reverse
from . conftest import api_client, load_fixture_file
from incidents.models import Document

#recall - decorator stacking from bottom up
@pytest.mark.django_db
@patch("incidents.views.boto3.client")
@patch("incidents.views.process_document.delay")
def test_create_document_returns_202(mock_task, mock_boto_client, api_client):
    mock_s3 = mock_boto_client.return_value
    url = reverse("document-list")
    fake_file = load_fixture_file("test-incident-report-pdf.pdf", "application/pdf")
    response = api_client.post(url, {"file": fake_file}, format="multipart")
    assert response.status_code == 202

@pytest.mark.django_db
def test_list_all_documents_returns_200(api_client):
    url = reverse("document-list")
    response = api_client.get(url)
    assert response.status_code == 200

