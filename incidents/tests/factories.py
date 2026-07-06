import factory
from incidents.models import Incident, Document, PatternReport

class IncidentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Incident

    raw_input = factory.Faker("paragraph")
    title = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("paragraph")
    severity = Incident.Severity.NORMAL
    affected_systems = factory.LazyFunction(lambda: ["checkout-service"])
    timeline = factory.Faker("paragraph")
    root_cause = factory.Faker("paragraph")
    resolution = factory.Faker("paragraph")
    prevention = factory.Faker("paragraph")
    notes = ""
    vector = factory.LazyFunction(lambda: [0.1] * 1536)
    status = Incident.Status.COMPLETED


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    filename = "test-report.pdf"
    file_type = Document.FileType.PDF
    s3_key = factory.Sequence(lambda n: f"documents/test-uuid-{n}/test-report.pdf")
    extracted_text = ""
    vector = None
    status = Document.Status.PENDING