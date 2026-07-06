import pytest
import uuid
import numpy as np
from unittest.mock import patch, MagicMock
from django.urls import reverse
from incidents.models import Document
from incidents.tasks import process_document
from . conftest import api_client, load_fixture_file
from . factories import DocumentFactory

#test create document - success
@pytest.mark.django_db
@patch("incidents.views.boto3.client")
@patch("incidents.views.process_document.delay")
def test_create_document_returns_202(mock_task, mock_boto_client, api_client):
    mock_s3 = mock_boto_client.return_value
    url = reverse("document-list")
    fake_file = load_fixture_file("test-incident-report-pdf.pdf", "application/pdf")
    response = api_client.post(url, {"file": fake_file}, format="multipart")
    assert response.status_code == 202

#test list all documents - success
@pytest.mark.django_db
def test_list_all_documents_returns_200(api_client):
    url = reverse("document-list")
    response = api_client.get(url)
    assert response.status_code == 200

#test delete document - success
@pytest.mark.django_db
def test_delete_document_returns_200(api_client):
    test_document = DocumentFactory()
    url = reverse("document-detail", kwargs={"uuid": test_document.uuid})
    response = api_client.delete(url)
    assert response.status_code == 200

#test process_document task values - success
@pytest.mark.django_db
@patch("incidents.tasks.generate_embedding")
@patch("incidents.tasks.extract_document_text")
@patch("incidents.tasks.boto3.client")
def test_process_document_completes(mock_boto_client, mock_extract_document_text, mock_generate_embedding):
    test_document = DocumentFactory(status=Document.Status.PENDING, vector=None)

    mock_s3 = mock_boto_client.return_value
    mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"fake file bytes")}
    mock_extract_document_text.return_value = "extracted text"
    mock_generate_embedding.return_value = [0.3] * 1536

    process_document(str(test_document.uuid))
    test_document.refresh_from_db()
    assert test_document.status == Document.Status.COMPLETED
    assert test_document.extracted_text == "extracted text"
    assert np.allclose(test_document.vector, [0.3] * 1536)

#test s3 connection failure
@pytest.mark.django_db
@patch("incidents.tasks.boto3.client")
def test_process_document_failed_on_error(mock_boto_client):
    test_document = DocumentFactory(status=Document.Status.PENDING, vector=None)

    mock_boto_client.side_effect = Exception("S3 connection failed")

    process_document(str(test_document.uuid))
    test_document.refresh_from_db()
    assert test_document.status == Document.Status.FAILED