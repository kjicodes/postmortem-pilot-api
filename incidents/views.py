from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from incidents.serializers import IncidentSerializer
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_201_CREATED, HTTP_202_ACCEPTED, HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE
from incidents.models import Incident
from incidents.tasks import process_incident
from pgvector.django import CosineDistance


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





