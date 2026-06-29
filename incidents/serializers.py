from rest_framework import serializers
from incidents.models import Incident, Document

class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = ['uuid', 'raw_input', 'title', 'description', 'root_cause', 'affected_systems', 'severity', 'timeline', 'suggested_fixes', 'prevention', 'status', 'created_at']

class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = ['uuid', 'filename', 'file_type', 'file', 'status', 'extracted_text', 'created_at']

    def create(self, validated_data):
        validated_data.pop('file', None)
        return super().create(validated_data)


