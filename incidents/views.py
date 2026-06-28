from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from incidents.serializers import IncidentSerializer
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_201_CREATED, HTTP_202_ACCEPTED, HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE
from incidents.models import Incident
from incidents.tasks import process_incident


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
        return Response({ "message": "Incident successfully deleted."}, status=HTTP_200_OK)
