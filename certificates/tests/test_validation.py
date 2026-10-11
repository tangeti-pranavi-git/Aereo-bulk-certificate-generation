from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from certificates.models import CertificateJob, RecipientCertificate, JobStatus, RecipientStatus


class JobValidationTests(APITestCase):
    def setUp(self):
        self.url = reverse('job-list-create')

    def test_empty_payload_rejected(self):
        """Submitting an empty payload returns HTTP 400 with validation details"""
        response = self.client.post(self.url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('event_name', response.data['details'])
        self.assertIn('recipients', response.data['details'])

    def test_missing_event_name_rejected(self):
        """Missing or blank event_name returns HTTP 400"""
        payload = {
            "event_name": "   ",
            "recipients": [
                {"recipient_name": "Alice", "recipient_email": "alice@example.com"}
            ]
        }
        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('event_name', response.data['details'])

    def test_empty_recipients_list_rejected(self):
        """Empty recipients list returns HTTP 400"""
        payload = {
            "event_name": "Autonomous Navigation Workshop",
            "recipients": []
        }
        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('recipients', response.data['details'])

    def test_resilient_handling_of_malformed_recipient_records(self):
        """
        Submitting mixed recipients: invalid entries (blank name, invalid email)
        are flagged as FAILED with specific error messages, while valid recipients
        are accepted and queued.
        """
        payload = {
            "event_name": "Aviation Regulations",
            "recipients": [
                {
                    "recipient_name": "Valid Recipient",
                    "recipient_email": "valid@example.com"
                },
                {
                    "recipient_name": "",  # Blank name
                    "recipient_email": "alice@example.com"
                },
                {
                    "recipient_name": "Bob Smith",
                    "recipient_email": "not-an-email"  # Invalid email
                }
            ]
        }

        response = self.client.post(f"{self.url}?sync=true", data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        job_id = response.data['id']
        job = CertificateJob.objects.get(id=job_id)
        self.assertEqual(job.total_count, 3)

        # Check recipients in database
        recipients = job.recipients.all()
        self.assertEqual(recipients.count(), 3)

        # Valid recipient succeeded
        valid_rec = recipients.filter(recipient_name="Valid Recipient").first()
        self.assertIsNotNone(valid_rec)
        self.assertEqual(valid_rec.status, RecipientStatus.COMPLETED)

        # Blank name recipient failed with error message
        blank_name_rec = recipients.filter(recipient_email="alice@example.com").first()
        self.assertIsNotNone(blank_name_rec)
        self.assertEqual(blank_name_rec.status, RecipientStatus.FAILED)
        self.assertIn("recipient_name cannot be blank", blank_name_rec.error_message)

        # Bad email recipient failed with error message
        bad_email_rec = recipients.filter(recipient_name="Bob Smith").first()
        self.assertIsNotNone(bad_email_rec)
        self.assertEqual(bad_email_rec.status, RecipientStatus.FAILED)
        self.assertIn("not a valid email address", bad_email_rec.error_message)
