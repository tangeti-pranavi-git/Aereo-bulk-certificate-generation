import uuid
from django.db import models
from django.utils import timezone


class JobStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    COMPLETED = 'COMPLETED', 'Completed'
    PARTIALLY_COMPLETED = 'PARTIALLY_COMPLETED', 'Partially Completed'
    FAILED = 'FAILED', 'Failed'


class RecipientStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'


class CertificateJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_name = models.CharField(max_length=255, help_text="Title of course, event, or workshop")
    event_date = models.DateField(null=True, blank=True, help_text="Date of course completion or event")
    issuer_name = models.CharField(
        max_length=255,
        default="Aereo Certification Authority",
        help_text="Name of issuing institution or authority"
    )
    issuer_title = models.CharField(
        max_length=255,
        default="Authorized Signatory",
        help_text="Title or designation of the signatory"
    )
    template_name = models.CharField(
        max_length=100,
        default="standard_gold",
        help_text="Predefined template design identifier"
    )
    status = models.CharField(
        max_length=30,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        db_index=True
    )
    total_count = models.PositiveIntegerField(default=0)
    processed_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Job {self.id} - {self.event_name} ({self.status})"

    @property
    def progress_percentage(self) -> int:
        if self.total_count == 0:
            return 0
        return int((self.processed_count / self.total_count) * 100)

    @property
    def is_finished(self) -> bool:
        return self.status in [
            JobStatus.COMPLETED,
            JobStatus.PARTIALLY_COMPLETED,
            JobStatus.FAILED
        ]


class RecipientCertificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        CertificateJob,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.CharField(max_length=255, blank=True, default='')
    certificate_code = models.CharField(max_length=64, unique=True, db_index=True)
    custom_attributes = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30,
        choices=RecipientStatus.choices,
        default=RecipientStatus.PENDING,
        db_index=True
    )
    error_message = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='certificates/%Y/%m/', blank=True, null=True)
    file_size_bytes = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['certificate_code']),
            models.Index(fields=['job', 'status']),
        ]

    def __str__(self):
        return f"{self.recipient_name} ({self.certificate_code}) - {self.status}"
