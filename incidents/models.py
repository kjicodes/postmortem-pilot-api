import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from pgvector.django import VectorField


class Incident(models.Model):

    class Severity(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        CRITICAL = "CRITICAL", "Critical"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"


    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    vector = VectorField(dimensions=1536, null=True, blank=True)
    raw_input = models.TextField(blank=True)
    title = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    affected_systems = ArrayField(models.CharField(max_length=50), size=10, blank=True, default=list)
    severity = models.CharField(max_length=10, choices=Severity.choices, blank=True)
    timeline = models.TextField(blank=True)
    suggested_fixes = models.TextField(blank=True)
    prevention = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)


class Document(models.Model):

    class FileType(models.TextChoices):
        PDF = "PDF", "PDF"
        DOCX = "DOCX", "DOCX"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=4, choices=FileType.choices)
    s3_key = models.CharField(max_length=500)           #s3 object path
    extracted_text = models.TextField(blank=True)       #raw text after parsing - can reprocess if needed incase of parsing failures
    vector = VectorField(dimensions=1536, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

# cache model
class PatternReport(models.Model):
    report = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)

