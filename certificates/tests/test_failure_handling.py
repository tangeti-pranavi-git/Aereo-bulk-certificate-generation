from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus


class FailureHandlingTests(APITestCase):
    def setUp(self):
        self.create_url = reverse('job-list-create')

    def test_single_recipient_failure_does_not_block_others(self):
        """
        Critical Requirement Test:
        A failure during certificate generation of one recipient must NOT prevent
        other valid certificates in the same batch from completing successfully.
        """
        payload = {
            "event_name": "Drone Aerodynamics",
            "recipients": [
                {
                    "recipient_name": "First Valid Student",
                    "recipient_email": "first@example.com"
                },
                {
                    "recipient_name": "Faulty Student",
                    "recipient_email": "faulty@example.com",
                    # Triggers isolated simulated generator error in processor
                    "custom_attributes": {"simulate_failure": True}
                },
                {
                    "recipient_name": "Third Valid Student",
                    "recipient_email": "third@example.com"
                }
            ]
        }

        response = self.client.post(f"{self.create_url}?sync=true", data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        job_id = response.data['id']
        job = CertificateJob.objects.get(id=job_id)

        # Overall job state
        self.assertEqual(job.status, JobStatus.PARTIALLY_COMPLETED)
        self.assertEqual(job.total_count, 3)
        self.assertEqual(job.processed_count, 3)
        self.assertEqual(job.success_count, 2)
        self.assertEqual(job.failed_count, 1)

        # Check First Recipient: Succeeded
        first_rec = job.recipients.get(recipient_name="First Valid Student")
        self.assertEqual(first_rec.status, RecipientStatus.COMPLETED)
        self.assertTrue(bool(first_rec.file))
        self.assertIsNone(first_rec.error_message)

        # Check Faulty Recipient: Failed, error captured
        faulty_rec = job.recipients.get(recipient_name="Faulty Student")
        self.assertEqual(faulty_rec.status, RecipientStatus.FAILED)
        self.assertFalse(bool(faulty_rec.file))
        self.assertIn("Simulated certificate generation failure", faulty_rec.error_message)

        # Check Third Recipient: Succeeded despite previous failure!
        third_rec = job.recipients.get(recipient_name="Third Valid Student")
        self.assertEqual(third_rec.status, RecipientStatus.COMPLETED)
        self.assertTrue(bool(third_rec.file))
        self.assertIsNone(third_rec.error_message)

    def test_all_recipients_failed_job_status(self):
        """When every recipient fails, job status is FAILED"""
        payload = {
            "event_name": "Simulated All Failure Event",
            "recipients": [
                {
                    "recipient_name": "Student A",
                    "recipient_email": "a@example.com",
                    "custom_attributes": {"simulate_failure": True}
                },
                {
                    "recipient_name": "Student B",
                    "recipient_email": "b@example.com",
                    "custom_attributes": {"simulate_failure": True}
                }
            ]
        }

        response = self.client.post(f"{self.create_url}?sync=true", data=payload, format='json')
        job = CertificateJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.failed_count, 2)
        self.assertEqual(job.success_count, 0)
