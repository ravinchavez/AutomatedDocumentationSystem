# clients/pdf_client.py
import io
from datetime import date, datetime

import requests
from fpdf import FPDF
from PIL import Image

PAGE_W, PAGE_H = 210, 297
MARGIN = 15
CONTENT_W = PAGE_W - 2 * MARGIN


class LiquidationPDF(FPDF):
    def __init__(self, title: str, user_email: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report_title = title
        self.user_email = user_email
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(MARGIN, MARGIN, MARGIN)

    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, self.report_title, align="L")
        self.cell(0, 6, self.user_email, align="R")
        self.ln(8)
        self.set_draw_color(200, 200, 200)
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def _fmt_money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _fetch_image(url: str) -> bytes | None:
    """Download a presigned URL's bytes. Returns None on failure."""
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception:
        return None
    return None


def _try_add_image(pdf: FPDF, image_bytes: bytes, max_w: float, max_h: float) -> bool:
    """
    Insert an image scaled to fit (max_w, max_h) mm, preserving aspect ratio.
    Supports JPEG / PNG / GIF / BMP / WEBP via Pillow for other formats.
    Returns True on success.
    """
    try:
        # Normalize via Pillow → always hand a JPEG/PNG to fpdf
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        w_px, h_px = img.size
        aspect = h_px / w_px

        w_mm = max_w
        h_mm = w_mm * aspect
        if h_mm > max_h:
            h_mm = max_h
            w_mm = h_mm / aspect

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        buf.seek(0)
        pdf.image(buf, w=w_mm, h=h_mm)
        return True
    except Exception:
        return False


def build_liquidation_pdf(
    receipts: list[dict],
    user_email: str,
    image_url_resolver,          # callable(b2_key) -> presigned URL str
    title: str = "Liquidation Report",
    include_images: bool = True,
    notes: str = "",
) -> bytes:
    """
    Build a liquidation PDF and return it as bytes.

    receipts:  list of dicts (from list_receipts)
    image_url_resolver: usually `presigned_url` from b2_client
    """
    pdf = LiquidationPDF(title=title, user_email=user_email)
    pdf.add_page()

    # ---------- Title block ----------
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 12, "Liquidation Report", ln=True, align="C")

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Generated on {datetime.now():%B %d, %Y %H:%M}", ln=True, align="C")
    pdf.ln(4)

    if notes:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(CONTENT_W, 5, notes)
        pdf.ln(3)

    # ---------- Summary ----------
    if not receipts:
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, "No receipts to report.", ln=True)
        return bytes(pdf.output())

    total = sum(float(r.get("total_amount") or 0) for r in receipts)
    currencies = sorted({(r.get("currency") or "").upper() for r in receipts if r.get("currency")})
    dominant_ccy = currencies[0] if len(currencies) == 1 else "MIXED"

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"Total receipts: {len(receipts)}", ln=True)
    pdf.cell(0, 6, f"Total amount: {_fmt_money(total, dominant_ccy)}", ln=True)
    if len(currencies) > 1:
        pdf.cell(0, 6, f"Currencies present: {', '.join(currencies)}", ln=True)
    pdf.ln(4)

    # ---------- Category breakdown ----------
    by_cat: dict[str, float] = {}
    count_by_cat: dict[str, int] = {}
    for r in receipts:
        cat = r.get("category") or "Uncategorized"
        by_cat[cat] = by_cat.get(cat, 0.0) + float(r.get("total_amount") or 0)
        count_by_cat[cat] = count_by_cat.get(cat, 0) + 1

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Breakdown by category", ln=True)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(235, 235, 235)
    col_w = [CONTENT_W * 0.5, CONTENT_W * 0.15, CONTENT_W * 0.35]
    pdf.cell(col_w[0], 7, "Category", border=1, fill=True)
    pdf.cell(col_w[1], 7, "Count", border=1, fill=True, align="C")
    pdf.cell(col_w[2], 7, "Amount", border=1, fill=True, align="R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    for cat, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
        pdf.cell(col_w[0], 6, cat, border=1)
        pdf.cell(col_w[1], 6, str(count_by_cat[cat]), border=1, align="C")
        pdf.cell(col_w[2], 6, _fmt_money(amt, dominant_ccy), border=1, align="R")
        pdf.ln()

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(col_w[0], 7, "TOTAL", border=1)
    pdf.cell(col_w[1], 7, str(len(receipts)), border=1, align="C")
    pdf.cell(col_w[2], 7, _fmt_money(total, dominant_ccy), border=1, align="R")
    pdf.ln(8)

    # ---------- Details, one block per receipt ----------
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Receipt details", ln=True)
    pdf.ln(2)

    for i, r in enumerate(receipts, start=1):
        # Card border
        card_top = pdf.get_y()
        card_height_estimate = 90 if include_images else 40
        if card_top + card_height_estimate > PAGE_H - 25:
            pdf.add_page()
            card_top = pdf.get_y()

        pdf.set_draw_color(210, 210, 210)
        pdf.set_fill_color(250, 250, 250)
        pdf.rect(MARGIN, card_top, CONTENT_W, card_height_estimate, style="DF")

        pdf.set_xy(MARGIN + 4, card_top + 4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(0, 0, 0)
        merchant = r.get("merchant") or "Unknown merchant"
        pdf.cell(0, 6, f"{i}. {merchant}", ln=True)

        # Left: meta. Right: image
        img_w = 65 if include_images else 0
        meta_w = CONTENT_W - 8 - (img_w + 4 if include_images else 0)

        meta_x = MARGIN + 4
        meta_y = pdf.get_y() + 1
        pdf.set_xy(meta_x, meta_y)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)

        fields = [
            ("Date",          r.get("transaction_date") or "—"),
            ("Documented",    r.get("documentation_date") or "—"),
            ("OR / Invoice",  r.get("or_number") or "—"),
            ("Category",      r.get("category") or "—"),
            ("Currency",      r.get("currency") or "—"),
            ("Total",         _fmt_money(float(r.get("total_amount") or 0),
                                          r.get("currency") or dominant_ccy)),
            ("PHP Total",     _fmt_money(float(r.get("php_total_amount") or 0), "PHP")),
        ]
        for label, value in fields:
            pdf.set_x(meta_x)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(28, 5, f"{label}:", border=0)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(meta_w - 28, 5, str(value), border=0)

        desc = (r.get("description") or "").strip()
        if desc:
            pdf.set_x(meta_x)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(28, 5, "Description:", border=0)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(meta_w - 28, 5, desc)

        img_ctx = (r.get("image_context") or "").strip()
        if img_ctx:
            pdf.set_x(meta_x)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(28, 5, "Context:", border=0)
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(meta_w - 28, 5, img_ctx[:300])

        # Right-side image
        if include_images and r.get("backblaze_image"):
            try:
                url = image_url_resolver(r["backblaze_image"])
                img_bytes = _fetch_image(url)
                if img_bytes:
                    pdf.set_xy(MARGIN + CONTENT_W - img_w - 4, card_top + 6)
                    _try_add_image(pdf, img_bytes, max_w=img_w, max_h=76)
                else:
                    pdf.set_xy(MARGIN + CONTENT_W - img_w - 4, card_top + 6)
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(150, 150, 150)
                    pdf.cell(img_w, 6, "[image unavailable]", align="C")
            except Exception:
                pass

        # Move cursor past the card
        pdf.set_xy(MARGIN, card_top + card_height_estimate + 4)
        pdf.set_text_color(0, 0, 0)

    return bytes(pdf.output())