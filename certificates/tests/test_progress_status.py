from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus


class JobProgressStatusTests(APITestCase):
    def setUp(self):
        self.create_url = reverse('job-list-create')
        self.payload = {
            "event_name": "Drone Software Engineering",
            "event_date": "2026-10-15",
            "recipients": [
                {"recipient_name": "Rohan Patel", "recipient_email": "rohan@example.com"},
                {"recipient_name": "Ananya Roy", "recipient_email": "ananya@example.com"}
            ]
        }

    def test_job_progress_detail_endpoint(self):
        """Test GET /api/jobs/<job_id>/ provides accurate progress percentage and recipient status list"""
        # Create job synchronously so state is fully finalized
        create_res = self.client.post(f"{self.create_url}?sync=true", data=self.payload, format='json')
        job_id = create_res.data['id']

        detail_url = reverse('job-detail', kwargs={'job_id': job_id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(data['id'], job_id)
        self.assertEqual(data['status'], JobStatus.COMPLETED)
        self.assertEqual(data['progress_percentage'], 100)
        self.assertEqual(data['total_count'], 2)
        self.assertEqual(data['processed_count'], 2)
        self.assertEqual(data['success_count'], 2)
        self.assertEqual(data['failed_count'], 0)
        self.assertIsNotNone(data['completed_at'])

        # Check recipients array in detail serializer
        self.assertIn('recipients', data)
        self.assertEqual(len(data['recipients']), 2)

        for rec in data['recipients']:
            self.assertEqual(rec['status'], RecipientStatus.COMPLETED)
            self.assertIsNotNone(rec['certificate_code'])
            self.assertTrue(rec['certificate_code'].startswith('AER-'))
            self.assertIsNotNone(rec['download_url'])
            self.assertIn('/download/', rec['download_url'])

    def test_nonexistent_job_returns_404(self):
        """Test polling a non-existent job ID returns HTTP 404"""
        import uuid
        fake_id = uuid.uuid4()
        detail_url = reverse('job-detail', kwargs={'job_id': fake_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
