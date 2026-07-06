import pytest
import uuid
from unittest.mock import patch, MagicMock
from django.urls import reverse
from incidents.models import Incident
from incidents.tasks import process_incident, IncidentReport
from . conftest import api_client
from . factories import IncidentFactory
import numpy as np

#test create incident - success
@pytest.mark.django_db
@patch("incidents.views.process_incident.delay")
def test_create_incident_returns_202(mock_task, api_client):
    body = {
        "raw_input": "error",
        "title": "test",
        "description": "test",
        "severity": Incident.Severity.NORMAL,
        "timeline": "test",
        "affected_systems": ["test"],
        "root_cause": "test",
        "resolution": "test",
        "prevention": "test"
    }
    url = reverse("incident-list")
    response = api_client.post(url, body, format="json")
    assert response.status_code == 202

#test list all incidents - success
@pytest.mark.django_db
def test_list_all_incidents_returns_200(api_client):
    IncidentFactory.create_batch(2)
    url = reverse("incident-list")
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == len(response.data["results"])

#test retrieve one incident - success
@pytest.mark.django_db
def test_get_incident_returns_200(api_client):
    test_incident = IncidentFactory()
    url = reverse("incident-detail", kwargs={"uuid": test_incident.uuid})
    response = api_client.get(url, format="json")
    assert response.status_code == 200
    assert response.data["uuid"] == str(test_incident.uuid)

#test update incident - success
@pytest.mark.django_db
def test_update_incident_returns_200(api_client):
    test_incident = IncidentFactory(severity=Incident.Severity.NORMAL)
    url = reverse("incident-detail", kwargs={"uuid": test_incident.uuid})
    response = api_client.patch(url, {"severity": Incident.Severity.HIGH}, format="json")
    assert response.status_code == 200
    assert response.data["severity"] == Incident.Severity.HIGH

#test delete incident - success
@pytest.mark.django_db
def test_delete_incident_returns_200(api_client):
    test_incident = IncidentFactory()
    url = reverse("incident-detail", kwargs={"uuid": test_incident.uuid})
    response = api_client.delete(url, format="json")
    assert response.status_code == 200
    assert not Incident.objects.filter(uuid=test_incident.uuid).exists()

#test missing non-null fields - error
@pytest.mark.django_db
@patch("incidents.views.process_incident.delay")
def test_create_incident_missing_raw_input_returns_400(mock_task, api_client):
    test_incident = IncidentFactory(raw_input="")
    url = reverse("incident-list")
    response = api_client.post(url, format="json")
    assert response.status_code == 400

#test uuid does not exist - error
@pytest.mark.django_db
def test_get_incident_returns_404(api_client):
    url = reverse("incident-detail", kwargs={"uuid": "123456"})
    response = api_client.get(url, format="json")
    assert response.status_code == 404

#test querying similar incidents when incident has no vector - error
@pytest.mark.django_db
def test_list_similar_incidents_returns_400_when_no_vector(api_client):
    test_incident = IncidentFactory(vector=None)
    url = reverse("incident-get-similar-incidents", kwargs={"uuid": test_incident.uuid})
    response = api_client.get(url)
    assert response.status_code == 400

#test non-existent uuid - error
@pytest.mark.django_db
def test_list_similar_incidents_returns_404_for_unknown_uuid(api_client):
    IncidentFactory()
    url = reverse("incident-get-similar-incidents", kwargs={"uuid": "00000000-0000-0000-0000-000000000000"})
    response = api_client.get(url)
    assert response.status_code == 404

#test process_incident task - success
@pytest.mark.django_db
@patch("incidents.tasks.generate_embedding")
@patch("incidents.tasks.ChatPromptTemplate")
@patch("incidents.tasks.ChatOpenAI")
def test_process_incident_completes_and_rewords(mock_chat_openai, mock_chat_prompt_template, mock_generate_embedding):
    test_incident = IncidentFactory(
        status=Incident.Status.PENDING,
        vector=None,
        title="test",
        severity=Incident.Severity.HIGH,
    )
    mock_chat_openai.return_value = MagicMock()
    test_report = IncidentReport(
        title="reworded",
        description="reworded",
        timeline="reworded",
        affected_systems=["checkout-service"],
        root_cause="reworded",
        resolution="reworded",
        prevention="reworded",
    )
    mock_pipeline = MagicMock()
    mock_pipeline.invoke.return_value = test_report
    mock_prompt_template = MagicMock()
    mock_prompt_template.__or__.return_value = mock_pipeline
    mock_chat_prompt_template.from_template.return_value = mock_prompt_template
    mock_generate_embedding.return_value = [0.2] * 1536

    process_incident(str(test_incident.uuid))
    test_incident.refresh_from_db()
    assert test_incident.status == Incident.Status.COMPLETED
    assert test_incident.title == "reworded"
    assert test_incident.description == "reworded"
    assert np.allclose(test_incident.vector, [0.2] * 1536)
    assert test_incident.severity == Incident.Severity.HIGH  # untouched, LLM never sees this field

#test process_incident task - error
@pytest.mark.django_db
@patch("incidents.tasks.ChatPromptTemplate")
@patch("incidents.tasks.ChatOpenAI")
def test_process_incident_marks_failed_on_error(mock_chat_openai, mock_chat_prompt_template):
    test_incident = IncidentFactory(status=Incident.Status.PENDING, vector=None)

    mock_chat_openai.return_value = MagicMock()
    mock_pipeline = MagicMock()
    mock_pipeline.invoke.side_effect = Exception("LLM call failed")
    mock_prompt_template = MagicMock()
    mock_prompt_template.__or__.return_value = mock_pipeline
    mock_chat_prompt_template.from_template.return_value = mock_prompt_template

    process_incident(str(test_incident.uuid))
    test_incident.refresh_from_db()
    assert test_incident.status == Incident.Status.FAILED