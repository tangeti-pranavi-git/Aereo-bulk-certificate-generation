from django.contrib import admin
from certificates.models import CertificateJob, RecipientCertificate


class RecipientCertificateInline(admin.TabularInline):
    model = RecipientCertificate
    extra = 0
    readonly_fields = ('certificate_code', 'status', 'error_message', 'file_size_bytes', 'created_at')
    fields = ('recipient_name', 'recipient_email', 'certificate_code', 'status', 'error_message', 'file')
    can_delete = False


@admin.register(CertificateJob)
class CertificateJobAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'event_name',
        'status',
        'total_count',
        'processed_count',
        'success_count',
        'failed_count',
        'created_at',
        'completed_at'
    )
    list_filter = ('status', 'created_at', 'event_name')
    search_fields = ('id', 'event_name', 'issuer_name')
    readonly_fields = (
        'id',
        'total_count',
        'processed_count',
        'success_count',
        'failed_count',
        'progress_percentage',
        'created_at',
        'updated_at',
        'completed_at'
    )
    inlines = [RecipientCertificateInline]


@admin.register(RecipientCertificate)
class RecipientCertificateAdmin(admin.ModelAdmin):
    list_display = (
        'certificate_code',
        'recipient_name',
        'recipient_email',
        'job',
        'status',
        'file_size_bytes',
        'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('certificate_code', 'recipient_name', 'recipient_email', 'job__event_name')
    readonly_fields = ('id', 'certificate_code', 'file_size_bytes', 'created_at', 'updated_at')
