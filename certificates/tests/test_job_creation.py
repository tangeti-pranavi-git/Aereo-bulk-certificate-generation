import time
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus


class JobCreationTests(APITransactionTestCase):
    def setUp(self):
        self.url = reverse('job-list-create')
        self.valid_payload = {
            "event_name": "Autonomous Drone Systems Engineering",
            "event_date": "2026-10-11",
            "issuer_name": "Aereo Academy",
            "issuer_title": "Head of Flight School",
            "recipients": [
                {
                    "recipient_name": "Aarav Sharma",
                    "recipient_email": "aarav@example.com",
                    "custom_attributes": {"score": "98%"}
                },
                {
                    "recipient_name": "Priya Nair",
                    "recipient_email": "priya@example.com",
                    "custom_attributes": {"score": "95%"}
                }
            ]
        }

    def test_create_bulk_job_synchronous(self):
        """Test creating a bulk job with sync=true processes immediately and finishes"""
        response = self.client.post(f"{self.url}?sync=true", data=self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['event_name'], self.valid_payload['event_name'])
        self.assertEqual(response.data['total_count'], 2)

        # Check job status in database
        job = CertificateJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.success_count, 2)
        self.assertEqual(job.failed_count, 0)
        self.assertEqual(job.processed_count, 2)
        self.assertIsNotNone(job.completed_at)

        # Ensure certificates were generated
        for recipient in job.recipients.all():
            self.assertEqual(recipient.status, RecipientStatus.COMPLETED)
            self.assertTrue(bool(recipient.file))
            self.assertTrue(recipient.file_size_bytes > 0)

    def test_create_bulk_job_background_thread(self):
        """Test default asynchronous job creation immediately returns HTTP 202 and completes via worker"""
        response = self.client.post(self.url, data=self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job_id = response.data['id']

        # Poll for background thread completion
        job = None
        for _ in range(25):
            job = CertificateJob.objects.get(id=job_id)
            if job.status == JobStatus.COMPLETED:
                break
            time.sleep(0.2)

        self.assertEqual(job.total_count, 2)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.success_count, 2)

    def test_list_jobs_with_pagination(self):
        """Test GET /api/jobs/ returns paginated list of created jobs"""
        # Create 2 jobs
        self.client.post(f"{self.url}?sync=true", data=self.valid_payload, format='json')
        self.valid_payload['event_name'] = "Second Event"
        self.client.post(f"{self.url}?sync=true", data=self.valid_payload, format='json')

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 2)

    def test_create_bulk_job_from_csv(self):
        """Test POST /api/jobs/upload-csv/ creates and generates certificates from CSV file"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        csv_content = (
            b"recipient_name,recipient_email,grade\n"
            b"Vikram Sethi,vikram@example.com,Distinction\n"
            b"Tara Verma,tara@example.com,Honors\n"
        )
        csv_file = SimpleUploadedFile("recipients.csv", csv_content, content_type="text/csv")
        csv_url = reverse('job-upload-csv')

        response = self.client.post(
            f"{csv_url}?sync=true",
            data={
                "event_name": "CSV Drone Operations Bootcamp",
                "csv_file": csv_file
            },
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job_id = response.data['id']
        job = CertificateJob.objects.get(id=job_id)
        self.assertEqual(job.total_count, 2)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.success_count, 2)

    def test_create_bulk_job_from_xlsx(self):
        """Test POST /api/jobs/upload-file/ creates and generates certificates from Excel .xlsx file"""
        import io
        import openpyxl
        from django.core.files.uploadedfile import SimpleUploadedFile

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["recipient_name", "recipient_email", "track"])
        ws.append(["Ananya Roy", "ananya@example.com", "Computer Vision"])
        ws.append(["Ishaan Gupta", "ishaan@example.com", "Drone Flight"])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        xlsx_file = SimpleUploadedFile(
            "students.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        upload_url = reverse('job-upload-file')

        response = self.client.post(
            f"{upload_url}?sync=true",
            data={
                "event_name": "Excel Autonomous Drone Bootcamp",
                "file": xlsx_file
            },
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job_id = response.data['id']
        job = CertificateJob.objects.get(id=job_id)
        self.assertEqual(job.total_count, 2)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.success_count, 2)
        self.assertEqual(job.recipients.filter(status=RecipientStatus.COMPLETED).count(), 2)


