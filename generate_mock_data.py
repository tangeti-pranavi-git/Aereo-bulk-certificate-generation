"""
Utility script to generate realistic bulk recipient datasets for testing.
Generates 50, 100, 500, or custom N recipients with realistic names,
emails, course tracks, and distinction honors. Also supports exporting to CSV and JSON.
"""

import json
import csv
import random
import argparse
from pathlib import Path

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Shaurya", "Atharva", "Advik", "Pranav", "Kabir", "Aryan", "Dhruv", "Rudra", "Om", "Samarth",
    "Ananya", "Diya", "Gauri", "Pari", "Saanvi", "Aanya", "Aadhya", "Myra", "Aarohi", "Navya",
    "Rhea", "Ira", "Sara", "Tara", "Tanvi", "Avani", "Kavya", "Meera", "Pooja", "Simran",
    "Alexander", "Charlotte", "Daniel", "Emma", "Felix", "Grace", "Henry", "Isabella", "James", "Liam",
    "Maya", "Noah", "Olivia", "Paul", "Quinn", "Rachel", "Sophia", "Thomas", "Uma", "William"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Nair", "Reddy", "Iyer", "Rao", "Gupta", "Malhotra",
    "Bhat", "Chopra", "Deshmukh", "Joshi", "Kulkarni", "Menon", "Pillai", "Sengupta", "Trivedi", "Venkatesh",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Anderson", "Taylor"
]

TRACKS = [
    "Autonomous Flight Control",
    "LiDAR & Photogrammetry",
    "Drone Sensor Fusion",
    "Computer Vision & Obstacle Avoidance",
    "Geospatial Remote Sensing",
    "Edge AI Navigation",
    "Thermal Imaging & Inspection",
    "Battery Dynamics & Telemetry"
]

GRADES = [
    "Distinction (98%)",
    "Distinction (95%)",
    "Honors (92%)",
    "Honors (90%)",
    "Merit (88%)",
    "Merit (85%)",
    "Certified (82%)"
]


def generate_recipients(count: int, include_failures: bool = False):
    recipients = []
    used_emails = set()

    for i in range(count):
        # Optionally inject a small percentage of invalid records to demonstrate error isolation
        if include_failures and (i == 5 or i == 25 or i == 75):
            if i == 5:
                # Blank name
                recipients.append({
                    "recipient_name": "",
                    "recipient_email": f"unnamed.student{i}@example.com",
                    "custom_attributes": {"notes": "Intentionally blank name to test error handling"}
                })
                continue
            elif i == 25:
                # Invalid email format
                recipients.append({
                    "recipient_name": "Devin CorruptEmail",
                    "recipient_email": "not-a-valid-email-format",
                    "custom_attributes": {"notes": "Intentionally invalid email"}
                })
                continue
            elif i == 75:
                # Simulated generator runtime failure
                recipients.append({
                    "recipient_name": "Marcus FaultyRender",
                    "recipient_email": "marcus.faulty@example.com",
                    "custom_attributes": {"simulate_failure": True, "notes": "Simulated isolated error"}
                })
                continue

        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{i+1}@aereo-academy.org"

        track = random.choice(TRACKS)
        grade = random.choice(GRADES)

        recipients.append({
            "recipient_name": name,
            "recipient_email": email,
            "custom_attributes": {
                "track": track,
                "grade": grade,
                "cohort": "2026-Batch-Alpha"
            }
        })

    return recipients


def generate_bulk_files():
    base_dir = Path(__file__).resolve().parent

    # 1. 100 Students JSON (Standard Bulk)
    recipients_100 = generate_recipients(100, include_failures=True)
    payload_100 = {
        "event_name": "Commercial Drone Flight & Navigation Engineering Masterclass",
        "event_date": "2026-10-15",
        "issuer_name": "Aereo Certification Authority",
        "issuer_title": "Director of Technical Education",
        "recipients": recipients_100
    }
    with open(base_dir / "sample_bulk_100.json", "w", encoding="utf-8") as f:
        json.dump(payload_100, f, indent=2)
    print(f"Generated sample_bulk_100.json with 100 recipients.")

    # 2. 500 Students JSON (High Volume Mass Bulk)
    recipients_500 = generate_recipients(500, include_failures=True)
    payload_500 = {
        "event_name": "National Drone Operator Certification & Geospatial Systems",
        "event_date": "2026-10-20",
        "issuer_name": "Aereo Certification Authority",
        "issuer_title": "Chief Certification Officer",
        "recipients": recipients_500
    }
    with open(base_dir / "sample_bulk_500.json", "w", encoding="utf-8") as f:
        json.dump(payload_500, f, indent=2)
    print(f"Generated sample_bulk_500.json with 500 recipients.")

    # 3. 100 Students CSV
    with open(base_dir / "sample_recipients_100.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["recipient_name", "recipient_email", "track", "grade"])
        for r in recipients_100:
            writer.writerow([
                r["recipient_name"],
                r["recipient_email"],
                r["custom_attributes"].get("track", ""),
                r["custom_attributes"].get("grade", "")
            ])
    print(f"Generated sample_recipients_100.csv with 100 recipients.")

    # 4. 100 Students Excel .xlsx
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Recipients"

        # Headers
        headers = ["recipient_name", "recipient_email", "track", "grade"]
        ws.append(headers)

        # Style Header Row
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for r in recipients_100:
            ws.append([
                r["recipient_name"],
                r["recipient_email"],
                r["custom_attributes"].get("track", ""),
                r["custom_attributes"].get("grade", "")
            ])

        # Auto column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        xlsx_path = base_dir / "sample_recipients_100.xlsx"
        wb.save(xlsx_path)
        print(f"Generated sample_recipients_100.xlsx with 100 recipients.")
    except Exception as e:
        print(f"Could not generate Excel file: {e}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mock bulk recipient datasets")
    parser.add_argument("--count", type=int, default=100, help="Number of recipients to generate")
    parser.add_argument("--out", type=str, default=None, help="Output JSON filename")
    args = parser.parse_args()

    if args.out:
        recipients = generate_recipients(args.count, include_failures=False)
        payload = {
            "event_name": f"Aereo Technical Certification ({args.count} Attendees)",
            "event_date": "2026-10-15",
            "issuer_name": "Aereo Certification Authority",
            "issuer_title": "Director of Technical Education",
            "recipients": recipients
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Successfully generated {args.count} recipients to {args.out}")
    else:
        generate_bulk_files()
