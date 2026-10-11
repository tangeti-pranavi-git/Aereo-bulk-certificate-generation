import uuid
from datetime import datetime
from rest_framework import serializers
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus


class RecipientInputSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        trim_whitespace=True
    )
    recipient_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        default=''
    )
    custom_attributes = serializers.DictField(
        required=False,
        default=dict
    )


class BulkJobCreateSerializer(serializers.Serializer):
    event_name = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        help_text="Name of the course, event, or webinar"
    )
    event_date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Date of completion (YYYY-MM-DD)"
    )
    issuer_name = serializers.CharField(
        max_length=255,
        required=False,
        default="Aereo Certification Authority",
        help_text="Name of the issuing organization"
    )
    issuer_title = serializers.CharField(
        max_length=255,
        required=False,
        default="Authorized Signatory",
        help_text="Title or designation of the signatory"
    )
    recipients = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        allow_empty=False,
        help_text="List of recipient objects containing recipient_name, recipient_email, and optional custom_attributes"
    )

    def validate_recipients(self, value):
        if not value:
            raise serializers.ValidationError("Recipients list cannot be empty.")
        if len(value) > 2000:
            raise serializers.ValidationError("Batch size cannot exceed 2000 recipients per request.")
        return value

    def validate_event_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Event name cannot be blank.")
        return value.strip()


class RecipientCertificateSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = RecipientCertificate
        fields = [
            'id',
            'recipient_name',
            'recipient_email',
            'certificate_code',
            'custom_attributes',
            'status',
            'error_message',
            'file_size_bytes',
            'download_url',
            'created_at',
            'updated_at',
        ]

    def get_download_url(self, obj) -> str | None:
        if obj.status == RecipientStatus.COMPLETED and obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f"/api/certificates/{obj.id}/download/")
            return f"/api/certificates/{obj.id}/download/"
        return None


class CertificateJobListSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.ReadOnlyField()

    class Meta:
        model = CertificateJob
        fields = [
            'id',
            'event_name',
            'event_date',
            'issuer_name',
            'issuer_title',
            'status',
            'progress_percentage',
            'total_count',
            'processed_count',
            'success_count',
            'failed_count',
            'created_at',
            'completed_at',
        ]


class CertificateJobDetailSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.ReadOnlyField()
    download_all_url = serializers.SerializerMethodField()
    recipients = RecipientCertificateSerializer(many=True, read_only=True)

    class Meta:
        model = CertificateJob
        fields = [
            'id',
            'event_name',
            'event_date',
            'issuer_name',
            'issuer_title',
            'template_name',
            'status',
            'progress_percentage',
            'total_count',
            'processed_count',
            'success_count',
            'failed_count',
            'error_summary',
            'created_at',
            'completed_at',
            'download_all_url',
            'recipients',
        ]

    def get_download_all_url(self, obj) -> str | None:
        if obj.success_count > 0:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f"/api/jobs/{obj.id}/download-all/")
            return f"/api/jobs/{obj.id}/download-all/"
        return None


class CertificateVerificationSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    certificate_code = serializers.CharField()
    recipient_name = serializers.CharField()
    event_name = serializers.CharField()
    event_date = serializers.DateField(allow_null=True)
    issuer_name = serializers.CharField()
    issuer_title = serializers.CharField()
    issued_at = serializers.DateTimeField()
    download_url = serializers.CharField(allow_null=True)
