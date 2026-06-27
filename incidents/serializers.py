from rest_framework import serializers
from incidents.models import Incident

class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = ['uuid', 'raw_input', 'title', 'description', 'root_cause', 'affected_systems', 'severity', 'timeline', 'suggested_fixes', 'prevention', 'status', 'created_at']


