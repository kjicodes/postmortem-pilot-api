from rest_framework import serializers
from incidents.models import Incident, Document, PatternReport

class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = ['uuid', 'raw_input', 'title', 'description', 'root_cause', 'affected_systems', 'severity', 'timeline', 'suggested_fixes', 'prevention', 'status', 'created_at']
        read_only_fields = ['status']

class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = ['uuid', 'filename', 'file_type', 'file', 'status', 'extracted_text', 'created_at']
        read_only_fields = ['status']

    def validate_file(self, value):
        ext = value.name.split('.')[-1]
        if ext not in Document.FileType.values:
            raise serializers.ValidationError(f"Unsupported file type '.{ext}'. Must be one of {', '.join(Document.FileType.values)}.")
        return value

    def create(self, validated_data):
        validated_data.pop('file', None)
        return super().create(validated_data)

class PatternReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatternReport
        fields = ['report', 'generated_at']

