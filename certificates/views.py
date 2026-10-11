import io
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination

from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus
from certificates.serializers import (
    BulkJobCreateSerializer,
    CertificateJobListSerializer,
    CertificateJobDetailSerializer,
    RecipientCertificateSerializer,
    CertificateVerificationSerializer,
)
from certificates.services.processor import trigger_job_processing


def generate_unique_certificate_code() -> str:
    """Generates an authentic alphanumeric certificate code, e.g., AER-2026-X8K9L2"""
    year = datetime.now().year
    code = uuid.uuid4().hex[:8].upper()
    return f"AER-{year}-{code}"


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class JobCreateListView(APIView):
    """
    POST /api/jobs/ - Create and trigger a bulk certificate generation job
    GET  /api/jobs/ - List recent certificate jobs with pagination and stats
    """

    def get(self, request):
        queryset = CertificateJob.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = CertificateJobListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = BulkJobCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": "Validation failed",
                    "details": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        event_name = data['event_name']
        event_date = data.get('event_date')
        issuer_name = data.get('issuer_name') or "Aereo Certification Authority"
        issuer_title = data.get('issuer_title') or "Authorized Signatory"
        recipients_data = data['recipients']

        is_sync = request.query_params.get('sync', 'false').lower() in ['true', '1', 'yes']

        with transaction.atomic():
            job = CertificateJob.objects.create(
                event_name=event_name,
                event_date=event_date,
                issuer_name=issuer_name,
                issuer_title=issuer_title,
                total_count=len(recipients_data),
                processed_count=0,
                success_count=0,
                failed_count=0,
                status=JobStatus.PENDING,
            )

            recipients_to_create = []
            immediate_failed = 0

            for item in recipients_data:
                raw_name = item.get('recipient_name')
                raw_email = item.get('recipient_email')
                raw_custom = item.get('custom_attributes', {})

                # Validate recipient item
                item_errors = []
                if not raw_name or not str(raw_name).strip():
                    item_errors.append("recipient_name cannot be blank")

                if raw_email and str(raw_email).strip():
                    try:
                        validate_email(str(raw_email).strip())
                    except DjangoValidationError:
                        item_errors.append("recipient_email is not a valid email address")
                else:
                    roll = raw_custom.get('Roll No') or raw_custom.get('roll_no') if isinstance(raw_custom, dict) else ''
                    if roll:
                        raw_email = f"{re.sub(r'[^a-zA-Z0-9]', '', str(roll)).lower()}@student.edu"
                    elif raw_name and str(raw_name).strip():
                        safe_n = re.sub(r'[^a-zA-Z0-9]', '', str(raw_name).lower())
                        raw_email = f"{safe_n}@student.edu"
                    else:
                        raw_email = ""

                cert_code = generate_unique_certificate_code()

                if item_errors:
                    immediate_failed += 1
                    recipients_to_create.append(
                        RecipientCertificate(
                            job=job,
                            recipient_name=str(raw_name or 'Unknown').strip(),
                            recipient_email=str(raw_email or '').strip(),
                            certificate_code=cert_code,
                            custom_attributes=raw_custom if isinstance(raw_custom, dict) else {},
                            status=RecipientStatus.FAILED,
                            error_message="; ".join(item_errors),
                        )
                    )
                else:
                    recipients_to_create.append(
                        RecipientCertificate(
                            job=job,
                            recipient_name=str(raw_name).strip(),
                            recipient_email=str(raw_email).strip(),
                            certificate_code=cert_code,
                            custom_attributes=raw_custom if isinstance(raw_custom, dict) else {},
                            status=RecipientStatus.PENDING,
                        )
                    )

            RecipientCertificate.objects.bulk_create(recipients_to_create)

            if immediate_failed > 0:
                job.processed_count = immediate_failed
                job.failed_count = immediate_failed
                job.save(update_fields=['processed_count', 'failed_count', 'updated_at'])

        # Trigger generation processing
        request_host = request.build_absolute_uri('/')
        trigger_job_processing(job.id, request_host=request_host, sync=is_sync)

        job.refresh_from_db()
        detail_serializer = CertificateJobDetailSerializer(job, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_202_ACCEPTED)


class JobDetailView(APIView):
    """
    GET /api/jobs/<job_id>/ - Poll status and progress of a certificate generation job
    """

    def get(self, request, job_id):
        job = get_object_or_404(CertificateJob, id=job_id)
        serializer = CertificateJobDetailSerializer(job, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CertificateDownloadView(APIView):
    """
    GET /api/certificates/<id>/download/ - Download a single generated PDF certificate
    Use ?preview=true to view inline in the browser instead of downloading as an attachment.
    """

    def get(self, request, certificate_id):
        cert = get_object_or_404(RecipientCertificate, id=certificate_id)

        if cert.status != RecipientStatus.COMPLETED or not cert.file:
            return Response(
                {
                    "error": "Certificate is not available for download",
                    "status": cert.status,
                    "error_message": cert.error_message
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        file_path = Path(settings.MEDIA_ROOT) / cert.file.name
        if not file_path.exists():
            return Response(
                {"error": "Certificate file not found on disk"},
                status=status.HTTP_404_NOT_FOUND
            )

        preview = request.query_params.get('preview', 'false').lower() in ['true', '1', 'yes']
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', cert.recipient_name)
        filename = f"{safe_name}_{cert.certificate_code}.pdf"

        response = FileResponse(
            open(file_path, 'rb'),
            content_type='application/pdf',
            as_attachment=not preview,
            filename=filename
        )
        return response


class JobDownloadAllZipView(APIView):
    """
    GET /api/jobs/<job_id>/download-all/ - Download all completed certificates for a job as a single ZIP archive
    """

    def get(self, request, job_id):
        job = get_object_or_404(CertificateJob, id=job_id)
        completed_certs = job.recipients.filter(status=RecipientStatus.COMPLETED).exclude(file='')

        if not completed_certs.exists():
            return Response(
                {"error": "No completed certificates available to download for this job."},
                status=status.HTTP_400_BAD_REQUEST
            )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for cert in completed_certs:
                file_path = Path(settings.MEDIA_ROOT) / cert.file.name
                if file_path.exists():
                    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', cert.recipient_name)
                    arcname = f"{safe_name}_{cert.certificate_code}.pdf"
                    zf.write(file_path, arcname=arcname)

        zip_buffer.seek(0)
        safe_event_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', job.event_name)
        zip_filename = f"{safe_event_name}_Certificates.zip"

        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
        return response


class CertificateVerifyView(APIView):
    """
    GET /api/verify/<certificate_code>/ - Public verification endpoint
    """

    def get(self, request, certificate_code):
        try:
            cert = RecipientCertificate.objects.select_related('job').get(certificate_code=certificate_code)
        except RecipientCertificate.DoesNotExist:
            return Response(
                {
                    "valid": False,
                    "error": "Certificate not found. The provided verification code is invalid."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if cert.status != RecipientStatus.COMPLETED:
            return Response(
                {
                    "valid": False,
                    "status": cert.status,
                    "error": "This certificate is not in a completed status."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        download_url = request.build_absolute_uri(f"/api/certificates/{cert.id}/download/")

        data = {
            "valid": True,
            "certificate_code": cert.certificate_code,
            "recipient_name": cert.recipient_name,
            "event_name": cert.job.event_name,
            "event_date": cert.job.event_date,
            "issuer_name": cert.job.issuer_name,
            "issuer_title": cert.job.issuer_title,
            "issued_at": cert.updated_at,
            "download_url": download_url,
        }
        return Response(data, status=status.HTTP_200_OK)


def analyze_spreadsheet_headers(headers: list) -> dict:
    """
    Intelligently identifies Name, Roll Number/ID, and Email columns from arbitrary headers,
    handling typos (e.g. 'stsudent', 'studnt'), varied capitalization, and formats.
    """
    name_col = None
    email_col = None
    roll_col = None

    for h in headers:
        if not h:
            continue
        h_str = str(h).strip()
        norm = re.sub(r'[^a-z0-9]', '', h_str.lower())

        # Email detection
        if any(k in norm for k in ['email', 'mail']):
            if not email_col:
                email_col = h_str
        # Name detection (matches: 'Name of the stsudent', 'Name of student', 'Student Name', 'Candidate Name', etc.)
        elif 'name' in norm or any(k in norm for k in ['stsudent', 'student', 'participant', 'candidate', 'attendee']):
            if not name_col:
                name_col = h_str
        # Roll / Registration / ID detection (matches: 'Roll No', 'Roll Number', 'HT No', 'Hall Ticket', 'Reg No', 'ID')
        elif any(k in norm for k in ['roll', 'hallticket', 'htno', 'regno', 'reg_no', 'usn', 'urn', 'prn', 'id', 'enrollment']):
            if not roll_col:
                roll_col = h_str

    # If still no name_col, fallback: choose the first non-numeric header that is not S.No or Roll
    if not name_col:
        for h in headers:
            if not h:
                continue
            h_str = str(h).strip()
            norm = re.sub(r'[^a-z0-9]', '', h_str.lower())
            if norm not in ['sno', 'slno', 'serial', 'srno', 'sr'] and h_str != roll_col and h_str != email_col:
                name_col = h_str
                break

    return {'name': name_col, 'email': email_col, 'roll': roll_col}


class JobUploadSpreadsheetView(APIView):
    """
    POST /api/jobs/upload-file/ (or /api/jobs/upload-csv/ / /api/jobs/upload-xlsx/)
    Upload an Excel (.xlsx) or CSV (.csv) file of recipients for bulk certificate generation.
    Features smart fuzzy column detection (matches 'Name of the stsudent', 'Roll No', etc.)
    and handles files without an email column.
    """

    def post(self, request):
        uploaded_file = (
            request.FILES.get('file') or
            request.FILES.get('csv_file') or
            request.FILES.get('xlsx_file')
        )
        if not uploaded_file:
            return Response(
                {"error": "No file provided. Please attach a .xlsx or .csv file in 'file' or 'csv_file'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        event_name = request.data.get('event_name', '').strip()
        if not event_name:
            return Response(
                {"error": "Field 'event_name' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        event_date = request.data.get('event_date') or None
        issuer_name = request.data.get('issuer_name') or "Aereo Certification Authority"
        issuer_title = request.data.get('issuer_title') or "Authorized Signatory"
        is_sync = request.query_params.get('sync', 'false').lower() in ['true', '1', 'yes']

        filename = uploaded_file.name.lower()
        recipients_data = []

        try:
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                import openpyxl
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                sheet = wb.active

                rows_iter = sheet.iter_rows(values_only=True)
                header_row = next(rows_iter, None)
                if not header_row:
                    return Response(
                        {"error": "The Excel file is empty."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                headers = [str(c).strip() if c is not None else '' for c in header_row]
                cols = analyze_spreadsheet_headers(headers)

                for row in rows_iter:
                    if not any(row):
                        continue  # Skip empty rows
                    row_dict = {}
                    for col_idx, cell_value in enumerate(row):
                        if col_idx < len(headers) and headers[col_idx]:
                            row_dict[headers[col_idx]] = str(cell_value).strip() if cell_value is not None else ''

                    name = row_dict.get(cols['name'], '') if cols['name'] else ''
                    roll = row_dict.get(cols['roll'], '') if cols['roll'] else ''
                    email = row_dict.get(cols['email'], '') if cols['email'] else ''

                    custom_attr = {}
                    if roll:
                        custom_attr['Roll No'] = roll

                    for k, v in row_dict.items():
                        if k not in [cols['name'], cols['email'], cols['roll']] and v:
                            norm_k = re.sub(r'[^a-z0-9]', '', k.lower())
                            if norm_k not in ['sno', 'slno', 'srno', 'sr', 'serial']:
                                custom_attr[k] = v

                    if not email:
                        if roll:
                            safe_roll = re.sub(r'[^a-zA-Z0-9]', '', roll).lower()
                            email = f"{safe_roll}@student.edu"
                        elif name:
                            safe_name = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
                            email = f"{safe_name or 'student'}@student.edu"
                        else:
                            email = "student@certificate.local"

                    recipients_data.append({
                        "recipient_name": name,
                        "recipient_email": email,
                        "custom_attributes": custom_attr
                    })

            else:
                # CSV parsing
                decoded_file = uploaded_file.read().decode('utf-8-sig').splitlines()
                import csv as csv_module
                reader = csv_module.DictReader(decoded_file)
                headers = reader.fieldnames or []
                cols = analyze_spreadsheet_headers(headers)

                for row in reader:
                    name = row.get(cols['name'], '') if cols['name'] else ''
                    roll = row.get(cols['roll'], '') if cols['roll'] else ''
                    email = row.get(cols['email'], '') if cols['email'] else ''

                    custom_attr = {}
                    if roll:
                        custom_attr['Roll No'] = roll

                    for k, v in row.items():
                        if k not in [cols['name'], cols['email'], cols['roll']] and v:
                            norm_k = re.sub(r'[^a-z0-9]', '', str(k).lower())
                            if norm_k not in ['sno', 'slno', 'srno', 'sr', 'serial']:
                                custom_attr[str(k).strip()] = str(v).strip()

                    if not email:
                        if roll:
                            safe_roll = re.sub(r'[^a-zA-Z0-9]', '', roll).lower()
                            email = f"{safe_roll}@student.edu"
                        elif name:
                            safe_name = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
                            email = f"{safe_name or 'student'}@student.edu"
                        else:
                            email = "student@certificate.local"

                    recipients_data.append({
                        "recipient_name": name,
                        "recipient_email": email,
                        "custom_attributes": custom_attr
                    })

        except Exception as e:
            return Response(
                {"error": f"Failed to parse spreadsheet file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not recipients_data:
            return Response(
                {"error": "Spreadsheet file does not contain any recipient rows."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delegate to the same creation workflow
        with transaction.atomic():
            job = CertificateJob.objects.create(
                event_name=event_name,
                event_date=event_date,
                issuer_name=issuer_name,
                issuer_title=issuer_title,
                total_count=len(recipients_data),
                processed_count=0,
                success_count=0,
                failed_count=0,
                status=JobStatus.PENDING,
            )

            recipients_to_create = []
            immediate_failed = 0

            for item in recipients_data:
                raw_name = item['recipient_name']
                raw_email = item['recipient_email']
                raw_custom = item['custom_attributes']

                item_errors = []
                if not raw_name:
                    item_errors.append("recipient_name cannot be blank")
                if not raw_email:
                    item_errors.append("recipient_email cannot be blank")
                else:
                    try:
                        validate_email(raw_email)
                    except DjangoValidationError:
                        item_errors.append("recipient_email is not a valid email address")

                cert_code = generate_unique_certificate_code()

                if item_errors:
                    immediate_failed += 1
                    recipients_to_create.append(
                        RecipientCertificate(
                            job=job,
                            recipient_name=raw_name or 'Unknown',
                            recipient_email=raw_email,
                            certificate_code=cert_code,
                            custom_attributes=raw_custom,
                            status=RecipientStatus.FAILED,
                            error_message="; ".join(item_errors),
                        )
                    )
                else:
                    recipients_to_create.append(
                        RecipientCertificate(
                            job=job,
                            recipient_name=raw_name,
                            recipient_email=raw_email,
                            certificate_code=cert_code,
                            custom_attributes=raw_custom,
                            status=RecipientStatus.PENDING,
                        )
                    )

            RecipientCertificate.objects.bulk_create(recipients_to_create)

            if immediate_failed > 0:
                job.processed_count = immediate_failed
                job.failed_count = immediate_failed
                job.save(update_fields=['processed_count', 'failed_count', 'updated_at'])

        request_host = request.build_absolute_uri('/')
        trigger_job_processing(job.id, request_host=request_host, sync=is_sync)

        job.refresh_from_db()
        detail_serializer = CertificateJobDetailSerializer(job, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_202_ACCEPTED)


# Backwards compatibility alias
JobUploadCSVView = JobUploadSpreadsheetView


def dashboard_view(request):
    """Interactive Web Dashboard for testing and demonstrating the Certificate Generator"""
    return render(request, 'dashboard.html')

