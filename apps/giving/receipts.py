"""PDF receipts and yearly giving statements (ReportLab, no system libraries needed)."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .models import DonationSettings, money

BRAND_DARK = colors.HexColor("#0B2545")
LINE = colors.HexColor("#E3E7ED")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], textColor=BRAND_DARK, alignment=0, fontSize=20),
        "h": ParagraphStyle("h", parent=base["Heading3"], textColor=BRAND_DARK),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontSize=10, leading=14),
        "small": ParagraphStyle("s", parent=base["BodyText"], fontSize=8.5, leading=12, textColor=colors.HexColor("#5F6672")),
    }


def _org():
    from apps.core.models import OrganisationSettings

    return OrganisationSettings.load()


def _header(story, s, org, title):
    story.append(Paragraph(org.name, s["title"]))
    if org.hq_address:
        story.append(Paragraph(org.hq_address.replace("\n", "<br/>"), s["small"]))
    if org.tax_id:
        story.append(Paragraph(f"Tax ID: {org.tax_id}", s["small"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(title, s["h"]))


def _table(rows, widths):
    t = Table(rows, colWidths=widths)
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
                ("TEXTCOLOR", (0, 0), (0, -1), BRAND_DARK),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def receipt_pdf(donation):
    from .models import Receipt

    receipt = Receipt.for_donation(donation)
    org, ds, s = _org(), DonationSettings.load(), _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm)
    story = []
    _header(story, s, org, "Official donation receipt")
    paid = timezone.localtime(donation.paid_at or donation.created_at)
    rows = [
        ["Receipt number", receipt.display_number],
        ["Date received", paid.strftime("%d %B %Y")],
        ["Received from", f"{donation.donor_name}\n{donation.email}"],
        ["Amount", donation.display_amount],
        ["Gift type", "Monthly gift" if donation.frequency == "monthly" else "One-time gift"],
        ["Payment method", donation.get_provider_display()],
        ["Transaction reference", donation.reference],
    ]
    if donation.emergency_id:
        rows.append(["Designated to", donation.emergency.title])
    if donation.fundraiser_id:
        rows.append(["Fundraiser", donation.fundraiser.title])
    story.append(_table(rows, [55 * mm, 115 * mm]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Thank you for your generous gift.", s["p"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(ds.receipt_tax_text, s["p"]))
    if org.tax_status_text:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(org.tax_status_text, s["small"]))
    if ds.receipt_signatory:
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(f"{ds.receipt_signatory}<br/>{org.name}", s["p"]))
    doc.build(story)
    return buf.getvalue(), f"receipt-{receipt.display_number}.pdf"


def statement_pdf(user, year, donations):
    org, ds, s = _org(), DonationSettings.load(), _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm)
    story = []
    _header(story, s, org, f"Giving statement for {year}")
    story.append(Paragraph(f"Prepared for {user.get_full_name() or user.email} ({user.email})", s["p"]))
    story.append(Spacer(1, 5 * mm))
    rows = [["Date", "Reference", "Type", "Amount"]]
    totals = {}
    for d in donations:
        rows.append(
            [
                timezone.localtime(d.paid_at or d.created_at).strftime("%d %b %Y"),
                d.reference,
                "Monthly" if d.frequency == "monthly" else "One-time",
                d.display_amount,
            ]
        )
        totals[d.currency] = totals.get(d.currency, 0) + d.amount
    for cur, total in totals.items():
        rows.append(["", "", f"Total ({cur})", money(total, cur)])
    t = Table(rows, colWidths=[35 * mm, 50 * mm, 40 * mm, 45 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, 0), BRAND_DARK),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(ds.receipt_tax_text, s["p"]))
    doc.build(story)
    return buf.getvalue(), f"giving-statement-{year}.pdf"
