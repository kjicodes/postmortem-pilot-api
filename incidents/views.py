from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django.conf import settings
from incidents.serializers import IncidentSerializer, DocumentSerializer
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_201_CREATED, HTTP_202_ACCEPTED, HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE
from incidents.models import Incident, Document
from incidents.tasks import process_incident, process_document
from pgvector.django import CosineDistance
import boto3
import uuid as uuidlib


class IncidentViewSet(ModelViewSet):
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer
    lookup_field = 'uuid'

    @action(detail=True, methods=["get"], url_path="similar")
    def get_similar_incidents(self, request, uuid=None):
        try:
            incident = Incident.objects.get(uuid=uuid)
        except Incident.DoesNotExist:
            return Response({"message": "Incident not found."}, status=HTTP_404_NOT_FOUND)

        if incident.vector is None:
            return Response({"message": "Similarity search is unavailable - incident is still processing or failed."},
                            status=HTTP_400_BAD_REQUEST)

        similar_incidents = (
            Incident.objects
            .exclude(uuid=uuid)  # exclude the incident used in the search query
            .filter(vector__isnull=False)  # only consider incidents fully processed (vector != null)
            .annotate(distance=CosineDistance("vector",
                                              incident.vector))  # computes distance between each incident's vector and the current one
            .order_by("distance")[:5]  # return the 5 closest matches
        )

        serializer = IncidentSerializer(similar_incidents, many=True)
        return Response(serializer.data, status=HTTP_200_OK)

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






