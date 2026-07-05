import pytest
import uuid
from unittest.mock import patch
from django.urls import reverse
from incidents.models import Incident
from . conftest import api_client

def make_incident(**kwargs):
    defaults = {
        "raw_input": "Error: database connection timeout",
        "title": "DB Timeout",
        "status": Incident.Status.COMPLETED,
    }
    defaults.update(kwargs)
    return Incident.objects.create(**defaults)

#success test cases
@pytest.mark.django_db
@patch("incidents.views.process_incident.delay")
def test_create_incident_returns_202(mock_task, api_client):
    url = reverse("incident-list")
    body = {
        "raw_input": "Error",
        "title": "test",
        "description": "test",
        "severity": "NORMAL",
        "affected_systems": ["test"],
        "timeline": "test",
        "root_cause": "test",
        "resolution": "test",
        "prevention": "test",
    }
    response = api_client.post(url, body, format="json")
    assert response.status_code == 202

@pytest.mark.django_db
def test_list_all_incidents_returns_200(api_client):
    make_incident()                         #seeds db with test incident 1
    make_incident(title="Second incident")  #test incident 2
    url = reverse("incident-list")
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.data["count"] == len(response.data["results"])

@pytest.mark.django_db
def test_get_incident_returns_200(api_client):
    test_incident = make_incident()
    url = reverse("incident-detail", kwargs={"uuid": test_incident.uuid})
    response = api_client.get(url, format="json")
    assert response.status_code == 200
    assert response.data["uuid"] == str(test_incident.uuid)

@pytest.mark.django_db
def test_update_incident_returns_200(api_client):
    test_incident = make_incident()
    url = reverse("incident-detail", kwargs={"uuid": test_incident.uuid})
    response = api_client.patch(url, {"title": "Updating first incident"}, format="json")
    assert response.status_code == 200
    assert response.data["title"] == "Updating first incident"

@pytest.mark.django_db
def test_delete_incident_returns_200(api_client):
    test_incident = make_incident()
    url = reverse("incident-detail", kwargs={"uuid": test_incident.uuid})
    response = api_client.delete(url, format="json")
    assert response.status_code == 200
    assert not Incident.objects.filter(uuid=test_incident.uuid).exists()

@pytest.mark.django_db
def test_list_similar_incidents_returns_200(api_client):
    test_incident = make_incident(vector=[0.1] * 1536)   #add test vector
    url = reverse("incident-get-similar-incidents", kwargs={"uuid": test_incident.uuid})
    response = api_client.get(url)
    # print(reverse("incident-get-similar-incidents", kwargs={"uuid": "00000000-0000-0000-0000-000000000000"}))
    assert response.status_code == 200


#error test cases
@pytest.mark.django_db
@patch("incidents.views.process_incident.delay")
def test_create_incident_missing_raw_input_returns_400(mock_task, api_client):
    url = reverse("incident-list")
    response = api_client.post(url, {"raw_input": ""}, format="json")
    assert response.status_code == 400

@pytest.mark.django_db
def test_get_incident_returns_404(api_client):
    test_incident = make_incident()
    url = reverse("incident-detail", kwargs={"uuid": "123456"})
    response = api_client.get(url, format="json")
    assert response.status_code == 404

@pytest.mark.django_db
def test_list_similar_incidents_returns_400_when_no_vector(api_client):
    test_incident = make_incident()   #add test vector
    url = reverse("incident-get-similar-incidents", kwargs={"uuid": test_incident.uuid})
    response = api_client.get(url)
    assert response.status_code == 400

@pytest.mark.django_db
def test_list_similar_incidents_returns_404_for_unknown_uuid(api_client):
    test_incident = make_incident(vector=[0.1] * 1536)   #add test vector
    url = reverse("incident-get-similar-incidents", kwargs={"uuid": "00000000-0000-0000-0000-000000000000"})
    response = api_client.get(url)
    assert response.status_code == 404

