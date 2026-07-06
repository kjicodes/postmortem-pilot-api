import pytest
import uuid
from unittest.mock import patch, MagicMock
from django.urls import reverse
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from django.core.cache import cache
from incidents.models import Incident, PatternReport
from incidents.tasks import generate_pattern_report, PATTERN_REPORT_CACHE_KEY
from . conftest import api_client
from . factories import IncidentFactory

#successfully create pattern report
@pytest.mark.django_db
@patch("incidents.views.generate_pattern_report.delay")
def test_list_pattern_report_returns_202(mock_task, api_client):
    IncidentFactory.create_batch(4)
    url = reverse("patternreport-list")
    response = api_client.get(url)
    assert response.status_code == 202

#not enough incidents to generate a report - test api call, error response
@pytest.mark.django_db
@patch("incidents.views.generate_pattern_report.delay")
def test_list_pattern_report_returns_400(mock_task, api_client):
    IncidentFactory.create_batch(2)
    url = reverse("patternreport-list")
    response = api_client.get(url)
    assert response.status_code == 400
    assert response.data == {
                "message": "Not enough incidents yet to detect patterns. At least 3 completed incidents are required."}

#not enough incidents to generate a report - test values
@pytest.mark.django_db
def test_generate_pattern_report_does_nothing_with_too_few_incidents():
    IncidentFactory.create_batch(2)

    generate_pattern_report()

    assert PatternReport.objects.count() == 0
    assert cache.get(PATTERN_REPORT_CACHE_KEY) is None

#test llm task
@pytest.mark.django_db
@patch("incidents.tasks.ChatOpenAI")
def test_generate_pattern_report_creates_report_and_caches_it(mock_chat_openai):
    IncidentFactory.create_batch(3)

    mock_llm = MagicMock(spec=ChatOpenAI)
    mock_llm.invoke.return_value = AIMessage(content="fake pattern summary")
    mock_chat_openai.return_value = mock_llm

    generate_pattern_report()

    assert PatternReport.objects.count() == 1
    report = PatternReport.objects.first()
    assert "summary" in report.report
    assert "clusters" in report.report

    cached = cache.get(PATTERN_REPORT_CACHE_KEY)
    assert cached is not None
    assert cached["report"] == report.report
