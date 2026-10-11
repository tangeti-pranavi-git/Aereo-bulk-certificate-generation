import os
import threading
import logging
from typing import Optional
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from django.db import close_old_connections, transaction

from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus
from certificates.services.generator import CertificateGenerator

logger = logging.getLogger(__name__)


def process_job_sync(job_id: str, request_host: Optional[str] = None):
    """
    Synchronously process all recipients in a certificate generation job.
    Optimized for high-volume bulk execution (100s/1000s of recipients)
    with throttled progress commits and isolated per-recipient error handling.
    """
    close_old_connections()
    try:
        job = CertificateJob.objects.get(id=job_id)
    except CertificateJob.DoesNotExist:
        logger.error(f"CertificateJob with id {job_id} not found.")
        return

    # Set status to PROCESSING
    job.status = JobStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    recipients = list(job.recipients.all())
    media_dir = Path(settings.MEDIA_ROOT) / 'certificates' / str(job.id)
    media_dir.mkdir(parents=True, exist_ok=True)

    # Progress interval: commit progress to DB every N items (smooth UI updates while fast)
    total_count = len(recipients)
    if total_count <= 10:
        progress_interval = 1
    elif total_count <= 100:
        progress_interval = 5
    else:
        progress_interval = 10

    current_processed = job.processed_count
    current_success = job.success_count
    current_failed = job.failed_count
    step_count = 0

    for recipient in recipients:
        # If already marked as FAILED (e.g. during initial recipient payload validation)
        if recipient.status == RecipientStatus.FAILED:
            continue

        try:
            # Verification URL
            if request_host:
                verification_url = f"{request_host.rstrip('/')}/api/verify/{recipient.certificate_code}/"
            else:
                verification_url = f"http://localhost:8000/api/verify/{recipient.certificate_code}/"

            # Check for simulated test failure trigger in custom_attributes or recipient name
            if recipient.custom_attributes.get("simulate_failure") is True:
                raise RuntimeError("Simulated certificate generation failure for testing resilience")

            # Validate recipient name isn't blank or corrupt
            if not recipient.recipient_name or not recipient.recipient_name.strip():
                raise ValueError("Recipient name cannot be empty")

            rel_file_path = f"certificates/{job.id}/{recipient.certificate_code}.pdf"
            abs_file_path = media_dir / f"{recipient.certificate_code}.pdf"

            generator = CertificateGenerator(
                recipient_name=recipient.recipient_name,
                event_name=job.event_name,
                certificate_code=recipient.certificate_code,
                issue_date=job.event_date,
                issuer_name=job.issuer_name,
                issuer_title=job.issuer_title,
                verification_url=verification_url,
                custom_attributes=recipient.custom_attributes
            )

            pdf_bytes = generator.generate(output_path=abs_file_path)

            recipient.file.name = rel_file_path
            recipient.file_size_bytes = len(pdf_bytes)
            recipient.status = RecipientStatus.COMPLETED
            recipient.error_message = None
            recipient.save(update_fields=['file', 'file_size_bytes', 'status', 'error_message', 'updated_at'])

            current_processed += 1
            current_success += 1

        except Exception as exc:
            logger.exception(f"Error generating certificate for recipient {recipient.id}: {exc}")
            recipient.status = RecipientStatus.FAILED
            recipient.error_message = str(exc)
            recipient.save(update_fields=['status', 'error_message', 'updated_at'])

            current_processed += 1
            current_failed += 1

        step_count += 1
        if step_count % progress_interval == 0:
            with transaction.atomic():
                job.processed_count = current_processed
                job.success_count = current_success
                job.failed_count = current_failed
                job.save(update_fields=['processed_count', 'success_count', 'failed_count', 'updated_at'])

    # Finalize job status and counts atomically
    with transaction.atomic():
        job.processed_count = current_processed
        job.success_count = current_success
        job.failed_count = current_failed

        if job.total_count == 0 or job.success_count == 0:
            job.status = JobStatus.FAILED if job.failed_count > 0 else JobStatus.COMPLETED
        elif job.failed_count > 0:
            job.status = JobStatus.PARTIALLY_COMPLETED
        else:
            job.status = JobStatus.COMPLETED

        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'processed_count', 'success_count', 'failed_count', 'completed_at', 'updated_at'])

    close_old_connections()


def trigger_job_processing(job_id: str, request_host: Optional[str] = None, sync: bool = False):
    """
    Triggers job processing either in a background daemon thread or synchronously.
    """
    if sync:
        process_job_sync(job_id, request_host)
    else:
        def _target():
            try:
                process_job_sync(job_id, request_host)
            except Exception as e:
                logger.exception(f"Unhandled thread error during job {job_id}: {e}")
            finally:
                close_old_connections()

        thread = threading.Thread(target=_target, daemon=True, name=f"JobWorker-{job_id}")
        thread.start()
        return thread
