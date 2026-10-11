import os
from pathlib import Path
from datetime import date
from django.test import SimpleTestCase
from django.conf import settings
from certificates.services.generator import CertificateGenerator


class CertificateGeneratorTests(SimpleTestCase):
    def setUp(self):
        self.output_dir = Path(settings.MEDIA_ROOT) / 'test_certs'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Clean up test output
        for file in self.output_dir.glob('*.pdf'):
            try:
                os.remove(file)
            except OSError:
                pass

    def test_pdf_generation_bytes(self):
        """Test generator returns valid PDF bytes starting with %PDF"""
        generator = CertificateGenerator(
            recipient_name="John Doe",
            event_name="Drone Piloting 101",
            certificate_code="AER-2026-TEST01",
            issue_date="2026-10-15",
            issuer_name="Aereo Academy",
            issuer_title="Chief Pilot",
            custom_attributes={"score": "95%", "rank": "Top 5%"}
        )
        pdf_bytes = generator.generate()

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'), "PDF content must start with '%PDF' header")

    def test_pdf_generation_to_file(self):
        """Test generator writes PDF directly to destination path"""
        target_file = self.output_dir / "john_doe.pdf"
        generator = CertificateGenerator(
            recipient_name="Jane Smith",
            event_name="Geospatial Mapping",
            certificate_code="AER-2026-TEST02",
            issue_date=date(2026, 10, 11)
        )
        pdf_bytes = generator.generate(output_path=target_file)

        self.assertTrue(target_file.exists(), "Target file must be created on disk")
        self.assertEqual(len(pdf_bytes), target_file.stat().st_size)
        self.assertTrue(target_file.stat().st_size > 1000)

    def test_generator_with_empty_custom_attributes_and_defaults(self):
        """Test generator works cleanly without optional parameters"""
        generator = CertificateGenerator(
            recipient_name="Alex Ray",
            event_name="Aviation Safety",
            certificate_code="AER-2026-TEST03"
        )
        pdf_bytes = generator.generate()
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
