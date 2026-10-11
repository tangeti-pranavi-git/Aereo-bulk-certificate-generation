import io
import math
from pathlib import Path
from datetime import date, datetime
from typing import Optional, Dict, Any, Union

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF


class CertificateGenerator:
    """
    High-quality vector PDF certificate generator using ReportLab.
    Produces print-ready certificates with dual ornamental borders,
    gold seal, signature block, and tamper-evident QR code verification.
    """

    # Color palette
    COLOR_PRIMARY = colors.HexColor('#0F172A')     # Deep Navy Slate
    COLOR_SECONDARY = colors.HexColor('#1E293B')   # Muted Navy
    COLOR_GOLD = colors.HexColor('#D97706')        # Rich Amber Gold
    COLOR_GOLD_LIGHT = colors.HexColor('#FDE68A')  # Champagne Gold
    COLOR_GOLD_DARK = colors.HexColor('#B45309')   # Bronze Gold
    COLOR_TEXT_MUTED = colors.HexColor('#475569')  # Slate Grey
    COLOR_BG = colors.HexColor('#FAFAF9')          # Warm Off-White / Ivory
    COLOR_BORDER_OUTER = colors.HexColor('#0F172A')

    def __init__(
        self,
        recipient_name: str,
        event_name: str,
        certificate_code: str,
        issue_date: Optional[Union[str, date, datetime]] = None,
        issuer_name: str = "Aereo Certification Authority",
        issuer_title: str = "Authorized Signatory",
        verification_url: Optional[str] = None,
        custom_attributes: Optional[Dict[str, Any]] = None,
    ):
        self.recipient_name = recipient_name.strip()
        self.event_name = event_name.strip()
        self.certificate_code = certificate_code.strip()
        
        if issue_date is None:
            self.issue_date_str = date.today().strftime("%B %d, %Y")
        elif isinstance(issue_date, (date, datetime)):
            self.issue_date_str = issue_date.strftime("%B %d, %Y")
        else:
            self.issue_date_str = str(issue_date)

        self.issuer_name = issuer_name.strip()
        self.issuer_title = issuer_title.strip()
        self.verification_url = verification_url or f"http://localhost:8000/api/verify/{self.certificate_code}/"
        self.custom_attributes = custom_attributes or {}

    def generate(self, output_path: Optional[Union[str, Path]] = None) -> bytes:
        """
        Generates the PDF bytes and optionally saves to output_path.
        """
        buffer = io.BytesIO()
        width, height = landscape(letter)  # 792 x 612 pt

        c = canvas.Canvas(buffer, pagesize=(width, height))
        c.setTitle(f"Certificate - {self.recipient_name}")
        c.setAuthor(self.issuer_name)
        c.setSubject(self.event_name)

        # 1. Background fill
        c.setFillColor(self.COLOR_BG)
        c.rect(0, 0, width, height, fill=1, stroke=0)

        # 2. Outer and Inner Decorative Borders
        self._draw_borders(c, width, height)

        # 3. Top Organization Header & Insignia
        self._draw_header(c, width, height)

        # 4. Certificate Title
        self._draw_title(c, width, height)

        # 5. Recipient Details & Golden Flourish
        self._draw_recipient(c, width, height)

        # 6. Event Name & Honors/Details
        self._draw_course_info(c, width, height)

        # 7. Bottom Section: Date, Gold Seal, Signature, and QR Code
        self._draw_footer(c, width, height)

        c.showPage()
        c.save()

        pdf_bytes = buffer.getvalue()
        buffer.close()

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def _draw_borders(self, c: canvas.Canvas, width: float, height: float):
        margin_outer = 18
        margin_inner = 26

        # Outer thick border
        c.setStrokeColor(self.COLOR_BORDER_OUTER)
        c.setLineWidth(3.5)
        c.rect(margin_outer, margin_outer, width - 2 * margin_outer, height - 2 * margin_outer)

        # Inner fine gold border
        c.setStrokeColor(self.COLOR_GOLD)
        c.setLineWidth(1.2)
        c.rect(margin_inner, margin_inner, width - 2 * margin_inner, height - 2 * margin_inner)

        # Corner ornamental diamonds
        for cx, cy in [
            (margin_inner, margin_inner),
            (width - margin_inner, margin_inner),
            (margin_inner, height - margin_inner),
            (width - margin_inner, height - margin_inner),
        ]:
            self._draw_diamond(c, cx, cy, size=6, color=self.COLOR_GOLD)

    def _draw_diamond(self, c: canvas.Canvas, cx: float, cy: float, size: float, color):
        c.saveState()
        c.setFillColor(color)
        c.setStrokeColor(color)
        p = c.beginPath()
        p.moveTo(cx, cy + size)
        p.lineTo(cx + size, cy)
        p.lineTo(cx, cy - size)
        p.lineTo(cx - size, cy)
        p.close()
        c.drawPath(p, fill=1, stroke=1)
        c.restoreState()

    def _draw_header(self, c: canvas.Canvas, width: float, height: float):
        center_x = width / 2.0
        top_y = height - 60

        # Crest emblem
        c.saveState()
        c.setFillColor(self.COLOR_GOLD)
        c.circle(center_x, top_y + 10, 8, fill=1, stroke=0)
        c.setFillColor(colors.white)
        # Mini star inside circle
        c.circle(center_x, top_y + 10, 3, fill=1, stroke=0)
        c.restoreState()

        # Issuing Institution Subheader
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(self.COLOR_GOLD_DARK)
        c.drawCentredString(center_x, top_y - 8, self.issuer_name.upper())

    def _draw_title(self, c: canvas.Canvas, width: float, height: float):
        center_x = width / 2.0
        title_y = height - 120

        # Main Title
        c.setFont("Helvetica-Bold", 30)
        c.setFillColor(self.COLOR_PRIMARY)
        c.drawCentredString(center_x, title_y, "CERTIFICATE OF ACHIEVEMENT")

        # Subtitle
        c.setFont("Helvetica", 11)
        c.setFillColor(self.COLOR_TEXT_MUTED)
        c.drawCentredString(center_x, title_y - 28, "THIS CREDENTIAL IS PROUDLY PRESENTED TO")

    def _draw_recipient(self, c: canvas.Canvas, width: float, height: float):
        center_x = width / 2.0
        name_y = height - 200

        # Recipient Name in large bold
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(self.COLOR_PRIMARY)
        c.drawCentredString(center_x, name_y, self.recipient_name)

        # Gold decorative divider line under name
        name_width = min(max(c.stringWidth(self.recipient_name, "Helvetica-Bold", 28) + 60, 240), width - 160)
        line_start = center_x - (name_width / 2.0)
        line_end = center_x + (name_width / 2.0)
        line_y = name_y - 12

        c.setStrokeColor(self.COLOR_GOLD)
        c.setLineWidth(1.5)
        c.line(line_start, line_y, line_end, line_y)

        # Center diamond pip on underline
        self._draw_diamond(c, center_x, line_y, size=4, color=self.COLOR_GOLD)

        # Roll Number / Student ID subtitle if available
        roll_no = (
            self.custom_attributes.get("Roll No") or
            self.custom_attributes.get("roll_no") or
            self.custom_attributes.get("Roll") or
            self.custom_attributes.get("roll")
        )
        if roll_no:
            c.setFont("Helvetica-Bold", 10.5)
            c.setFillColor(self.COLOR_GOLD_DARK)
            c.drawCentredString(center_x, line_y - 14, f"ROLL NO: {roll_no}")

    def _draw_course_info(self, c: canvas.Canvas, width: float, height: float):
        center_x = width / 2.0
        has_roll = any(k in self.custom_attributes for k in ["Roll No", "roll_no", "Roll", "roll"])
        text_y = height - 255 if has_roll else height - 245

        c.setFont("Helvetica", 11)
        c.setFillColor(self.COLOR_TEXT_MUTED)
        c.drawCentredString(
            center_x,
            text_y,
            "for successfully fulfilling all requirements and demonstrating excellence in"
        )

        # Event / Course Name
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(self.COLOR_PRIMARY)
        c.drawCentredString(center_x, text_y - 28, self.event_name)

        # Optional Custom Attribute / Grade (excluding roll no and s.no)
        if self.custom_attributes:
            attr_strings = [
                f"{k}: {v}" for k, v in self.custom_attributes.items()
                if v and str(k).lower() not in ["roll no", "roll_no", "roll", "s.no", "sno", "simulate_failure"]
            ]
            if attr_strings:
                attr_text = " • ".join(attr_strings)
                c.setFont("Helvetica-Bold", 10)
                c.setFillColor(self.COLOR_GOLD_DARK)
                c.drawCentredString(center_x, text_y - 48, attr_text)

    def _draw_footer(self, c: canvas.Canvas, width: float, height: float):
        footer_y = 115

        # 1. Left side: Issue Date & Certificate ID
        c.setFont("Helvetica", 10)
        c.setFillColor(self.COLOR_TEXT_MUTED)
        c.drawString(65, footer_y + 15, "DATE OF ISSUANCE")
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(self.COLOR_PRIMARY)
        c.drawString(65, footer_y, self.issue_date_str)

        c.setFont("Helvetica", 9)
        c.setFillColor(self.COLOR_TEXT_MUTED)
        c.drawString(65, footer_y - 20, f"CERTIFICATE ID: {self.certificate_code}")

        # 2. Center: Gold Foil Seal Rosette
        seal_x = width / 2.0
        seal_y = footer_y + 5
        self._draw_gold_seal(c, seal_x, seal_y)

        # 3. Right side: Signature Block
        sig_x = width - 230
        c.setStrokeColor(self.COLOR_TEXT_MUTED)
        c.setLineWidth(1)
        c.line(sig_x, footer_y + 12, sig_x + 165, footer_y + 12)

        # Stylized faux cursive signature stroke
        self._draw_signature_flourish(c, sig_x + 15, footer_y + 20)

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(self.COLOR_PRIMARY)
        c.drawString(sig_x, footer_y - 3, self.issuer_name)

        c.setFont("Helvetica", 9)
        c.setFillColor(self.COLOR_TEXT_MUTED)
        c.drawString(sig_x, footer_y - 18, self.issuer_title)

        # 4. QR Code in bottom-left corner with text
        self._draw_qr_code(c, x=65, y=36, size=48)

    def _draw_signature_flourish(self, c: canvas.Canvas, start_x: float, start_y: float):
        """Draws an elegant stylized vector signature"""
        c.saveState()
        c.setStrokeColor(self.COLOR_PRIMARY)
        c.setLineWidth(1.4)
        p = c.beginPath()
        p.moveTo(start_x, start_y)
        p.curveTo(start_x + 20, start_y + 18, start_x + 40, start_y - 10, start_x + 60, start_y + 15)
        p.curveTo(start_x + 75, start_y + 5, start_x + 95, start_y + 25, start_x + 120, start_y + 8)
        p.curveTo(start_x + 130, start_y + 3, start_x + 135, start_y + 12, start_x + 145, start_y + 10)
        c.drawPath(p, stroke=1, fill=0)
        c.restoreState()

    def _draw_gold_seal(self, c: canvas.Canvas, cx: float, cy: float):
        """Draws a vector rosette golden seal"""
        c.saveState()

        # Ribbon tails hanging below
        c.setFillColor(self.COLOR_GOLD_DARK)
        p_ribbon1 = c.beginPath()
        p_ribbon1.moveTo(cx - 15, cy - 20)
        p_ribbon1.lineTo(cx - 28, cy - 50)
        p_ribbon1.lineTo(cx - 15, cy - 42)
        p_ribbon1.lineTo(cx - 2, cy - 50)
        p_ribbon1.lineTo(cx - 4, cy - 20)
        p_ribbon1.close()
        c.drawPath(p_ribbon1, fill=1, stroke=0)

        p_ribbon2 = c.beginPath()
        p_ribbon2.moveTo(cx + 4, cy - 20)
        p_ribbon2.lineTo(cx + 2, cy - 50)
        p_ribbon2.lineTo(cx + 15, cy - 42)
        p_ribbon2.lineTo(cx + 28, cy - 50)
        p_ribbon2.lineTo(cx + 15, cy - 20)
        p_ribbon2.close()
        c.drawPath(p_ribbon2, fill=1, stroke=0)

        # Outer rosette scalloped edges
        c.setFillColor(self.COLOR_GOLD)
        num_points = 24
        outer_r = 34
        inner_r = 29
        points = []
        for i in range(num_points * 2):
            r = outer_r if i % 2 == 0 else inner_r
            angle = i * math.pi / num_points
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            points.append((px, py))

        p_star = c.beginPath()
        p_star.moveTo(points[0][0], points[0][1])
        for pt in points[1:]:
            p_star.lineTo(pt[0], pt[1])
        p_star.close()
        c.drawPath(p_star, fill=1, stroke=0)

        # Inner gold ring
        c.setFillColor(self.COLOR_GOLD_LIGHT)
        c.circle(cx, cy, 24, fill=1, stroke=0)

        # Seal center core
        c.setFillColor(self.COLOR_GOLD)
        c.circle(cx, cy, 18, fill=1, stroke=0)

        # Star in center
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(cx, cy - 4, "★")

        c.restoreState()

    def _draw_qr_code(self, c: canvas.Canvas, x: float, y: float, size: float):
        """Draws a vector QR code with label"""
        try:
            qr_widget = QrCodeWidget(self.verification_url)
            bounds = qr_widget.getBounds()
            w = bounds[2] - bounds[0]
            h = bounds[3] - bounds[1]
            scale_x = size / w
            scale_y = size / h

            d = Drawing(size, size, transform=[scale_x, 0, 0, scale_y, 0, 0])
            d.add(qr_widget)
            renderPDF.draw(d, c, x, y)

            # Label next to QR code
            c.setFont("Helvetica", 7.5)
            c.setFillColor(self.COLOR_TEXT_MUTED)
            c.drawString(x + size + 8, y + (size / 2) + 2, "Scan to verify certificate")
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(self.COLOR_GOLD_DARK)
            c.drawString(x + size + 8, y + (size / 2) - 9, "SECURE VERIFIED RECORD")
        except Exception:
            # Fallback if QR fails
            c.setFont("Helvetica", 8)
            c.setFillColor(self.COLOR_TEXT_MUTED)
            c.drawString(x, y + 10, f"Verify: {self.verification_url}")
