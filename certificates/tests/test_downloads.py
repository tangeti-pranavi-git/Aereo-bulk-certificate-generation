import io
import zipfile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus


class CertificateDownloadAndVerifyTests(APITestCase):
    def setUp(self):
        self.create_url = reverse('job-list-create')
        self.payload = {
            "event_name": "Aviation Engineering",
            "event_date": "2026-10-15",
            "recipients": [
                {"recipient_name": "Sarah Connor", "recipient_email": "sarah@example.com"},
                {"recipient_name": "Kyle Reese", "recipient_email": "kyle@example.com"}
            ]
        }
        res = self.client.post(f"{self.create_url}?sync=true", data=self.payload, format='json')
        self.job = CertificateJob.objects.get(id=res.data['id'])
        self.recipient_1 = self.job.recipients.filter(recipient_name="Sarah Connor").first()

    def test_download_individual_certificate_pdf(self):
        """Test GET /api/certificates/<id>/download/ streams valid PDF file attachment"""
        download_url = reverse('certificate-download', kwargs={'certificate_id': self.recipient_1.id})
        response = self.client.get(download_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])

        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b'%PDF'), "Downloaded content must be a valid PDF file")
        self.assertTrue(len(content) > 1000)

    def test_preview_individual_certificate_pdf(self):
        """Test ?preview=true sets Content-Disposition to inline for in-browser preview"""
        download_url = reverse('certificate-download', kwargs={'certificate_id': self.recipient_1.id})
        response = self.client.get(f"{download_url}?preview=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])

    def test_download_all_certificates_as_zip(self):
        """Test GET /api/jobs/<job_id>/download-all/ packages all certificates into a ZIP archive"""
        zip_url = reverse('job-download-all-zip', kwargs={'job_id': self.job.id})
        response = self.client.get(zip_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment;', response['Content-Disposition'])

        # Read zip content in memory
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 2)
            for filename in namelist:
                self.assertTrue(filename.endswith('.pdf'))
                # Verify zip entry is valid PDF
                file_bytes = zf.read(filename)
                self.assertTrue(file_bytes.startswith(b'%PDF'))

    def test_public_certificate_verification(self):
        """Test GET /api/verify/<certificate_code>/ validates issued certificate"""
        verify_url = reverse('certificate-verify', kwargs={'certificate_code': self.recipient_1.certificate_code})
        response = self.client.get(verify_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertTrue(data['valid'])
        self.assertEqual(data['certificate_code'], self.recipient_1.certificate_code)
        self.assertEqual(data['recipient_name'], "Sarah Connor")
        self.assertEqual(data['event_name'], self.job.event_name)

    def test_verify_nonexistent_certificate(self):
        """Test verifying invalid code returns HTTP 404"""
        verify_url = reverse('certificate-verify', kwargs={'certificate_code': 'AER-INVALID-CODE'})
        response = self.client.get(verify_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data['valid'])
