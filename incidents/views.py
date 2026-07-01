from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from incidents.serializers import IncidentSerializer, DocumentSerializer, PatternReportSerializer
from incidents.utils import generate_embedding, extract_document_text
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_201_CREATED, HTTP_202_ACCEPTED, HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE
from incidents.models import Incident, Document, PatternReport
from incidents.tasks import process_incident, process_document, generate_pattern_report
from pgvector.django import CosineDistance
import boto3
import uuid as uuidlib

PATTERN_REPORT_TTL = timedelta(hours=1)


class IncidentViewSet(ModelViewSet):
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer
    lookup_field = 'uuid'

    def create(self, request, *args, **kwargs):
        serializer = IncidentSerializer(data=request.data)

        if serializer.is_valid():
            incident = serializer.save()
            #convert uuid to string first for Celery to serialize to json
            uuid = str(incident.uuid)

            #send data to llm to process - status should be set to 'pending' for now
            process_incident.delay(uuid)
            return Response(serializer.data, status=HTTP_202_ACCEPTED)
        else:
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return Response({ "message": "Incident successfully deleted."}, status=HTTP_200_OK)

    def _find_similar_incidents(self, vector, uuid_to_exclude=None):
        #search for similar incidents by vector
        #IF a uuid is present, then search req is an incident report from the db - therefore exclude that incident in the response
        #IF uuid is not present, then search req is a stack trace/error with no existing incident report
        incidents = Incident.objects.filter(vector__isnull=False)
        if uuid_to_exclude:
            incidents = incidents.exclude(uuid=uuid_to_exclude)
        result = incidents.annotate(distance=CosineDistance("vector", vector)).order_by("distance")[:5]
        return result

    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        raw_text = request.data.get("raw_text")
        file = request.FILES.get("file")

        if not raw_text and not file:
            return Response({"message": "Provide either text or a file."}, status=HTTP_400_BAD_REQUEST)

        if file:
            file_type = file.name.split(".")[-1]
            file_content = file.read()

            try:
                raw_text = extract_document_text(file_type, file_content)
            except ValueError:
                return Response({"message": "Failed to extract text from file."}, status=HTTP_400_BAD_REQUEST)

        try:
            vector = generate_embedding(raw_text)
        except Exception:
            return Response({"message": "Failed to generate embedding."}, status=HTTP_503_SERVICE_UNAVAILABLE)

        incidents = self._find_similar_incidents(vector)
        serializer = IncidentSerializer(incidents, many=True)
        return Response(serializer.data, status=HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="similar")
    def get_similar_incidents(self, request, uuid=None):
        try:
            incident = Incident.objects.get(uuid=uuid)
        except Incident.DoesNotExist:
            return Response({"message": "Incident not found."}, status=HTTP_404_NOT_FOUND)

        if incident.vector is None:
            return Response({"message": "Similarity search is unavailable - incident is still processing or failed."},
                            status=HTTP_400_BAD_REQUEST)

        similar_incidents = self._find_similar_incidents(incident.vector, uuid)
        serializer = IncidentSerializer(similar_incidents, many=True)
        return Response(serializer.data, status=HTTP_200_OK)


class DocumentViewSet(ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    lookup_field = 'uuid'

    def create(self, request, *args, **kwargs):
        serializer = DocumentSerializer(data=request.data)

        if serializer.is_valid():
            file = serializer.validated_data['file']
            filename = file.name
            file_type = filename.split('.')[-1].upper()
            print(filename)
            print(file_type)

            #initialize s3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            print("After initializing s3 client")
            #create random uuid string for s3 file path for storage purposes
            doc_uuid = str(uuidlib.uuid4())
            s3_key = f"documents/{doc_uuid}/{filename}"
            #upload to s3 bucket
            s3_client.upload_fileobj(file, settings.AWS_BUCKET_NAME, s3_key)
            print("Uploaded file to s3")
            document = serializer.save(
                filename=filename,
                file_type=file_type,
                s3_key=s3_key
            )
            print("Saved document info to postgresql db")

            #process doc
            uuid = str(document.uuid)
            print("Ready to process document...")
            process_document.delay(uuid)
            print("After processing....document processed or failed")
            return Response(serializer.data, status=HTTP_202_ACCEPTED)
        else:
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

class PatternReportViewSet(ReadOnlyModelViewSet):
    queryset = PatternReport.objects.all()
    serializer_class = PatternReportSerializer

    def list(self, request):
        #only 1 report will exist in the db at a time
        latest_report = PatternReport.objects.order_by('-generated_at').first()
        current_time = timezone.now()

        #IF the report was generated within the hour, it is fresh - return it
        if latest_report and latest_report.generated_at >= current_time - PATTERN_REPORT_TTL:
            serializer = PatternReportSerializer(latest_report)
            print(f"Latest report returned. {current_time}")
            return Response(serializer.data, status=HTTP_200_OK)

        #IF the report is stale (time delta > 1hr), generate a fresh one
        generate_pattern_report.delay()
        response = {
            "message": "Generating new pattern report.",
            "old_report_last_generated_at": latest_report.generated_at,
            "current_time": current_time
        }
        return Response(response, status=HTTP_202_ACCEPTED)
