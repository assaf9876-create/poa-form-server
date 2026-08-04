import io
import os
import base64
import zipfile
from datetime import date

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = FastAPI()

# ---- הגדרות קבועות ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

FONT_PATH = os.path.join(ASSETS_DIR, "DejaVuSans.ttf")
FORM_PRIMARY = os.path.join(ASSETS_DIR, "ראשי_ידני_לקלאוד.pdf")
FORM_ADDITIONAL = os.path.join(ASSETS_DIR, "נוסף_ידני_לקלאוד.pdf")
SIG_IMG = os.path.join(ASSETS_DIR, "קשקוש.png")
STAMP_IMG = os.path.join(ASSETS_DIR, "סמי_ביטון.png")

IMG_W, IMG_H = 924, 1316
S = 118
CN_SHIFT = 103
OFFICE = 'סמי ביטון, רו"ח'


class CompanyData(BaseModel):
    company_name: str
    company_number: str
    company_addr: str = ""
    date_str: str = ""


def make_transparent(inp, out, thr=200):
    img = Image.open(inp).convert("RGBA")
    d = np.array(img)
    mask = (d[:, :, 0] > thr) & (d[:, :, 1] > thr) & (d[:, :, 2] > thr)
    d[mask, 3] = 0
    Image.fromarray(d, "RGBA").save(out)


def extract_jpeg(zip_pdf_path):
    with zipfile.ZipFile(zip_pdf_path, "r") as z:
        for name in z.namelist():
            if name.lower().endswith((".jpeg", ".jpg")):
                return io.BytesIO(z.read(name))
    raise FileNotFoundError("No JPEG in zip")


def fill_form(zip_pdf_path, company_name, company_number, company_addr="", date_str=None):
    if not date_str:
        date_str = date.today().strftime("%d/%m/%Y")

    pdfmetrics.registerFont(TTFont("Heb", FONT_PATH))

    tmp_sig = "/tmp/sig_t.png"
    tmp_stamp = "/tmp/stamp_t.png"
    make_transparent(SIG_IMG, tmp_sig)
    make_transparent(STAMP_IMG, tmp_stamp)

    jpeg_bytes = extract_jpeg(zip_pdf_path)
    img_obj = Image.open(jpeg_bytes)
    base_pdf = io.BytesIO()
    img_obj.save(base_pdf, format="PDF", resolution=150)
    base_pdf.seek(0)

    r0 = PdfReader(base_pdf)
    W = float(r0.pages[0].mediabox.width)
    H = float(r0.pages[0].mediabox.height)
    base_pdf.seek(0)

    def itp(ix, iy):
        return ix * (W / IMG_W), H - iy * (H / IMG_H)

    def irtp(x0, y0, x1, y1):
        return x0 * (W / IMG_W), H - y1 * (H / IMG_H), x1 * (W / IMG_W), H - y0 * (H / IMG_H)

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(W, H))

    # === סקשיין א ===
    x, y = itp(620 - CN_SHIFT, 335)
    c.setFont("Heb", 7); c.drawString(x, y, company_name[::-1])

    x, y = itp(252, 336)
    c.setFont("Heb", 9); c.drawString(x, y, company_number)

    if company_addr:
        x, y = itp(618, 390)
        c.setFont("Heb", 9); c.drawString(x, y, company_addr[::-1])

    x, y = itp(760 - S, 770)
    c.setFont("Heb", 9); c.drawString(x, y, date_str)

    x, y = itp(420 - CN_SHIFT, 758)
    c.setFont("Heb", 7); c.drawString(x, y, company_name[::-1])

    x, y = itp(420, 772)
    c.setFont("Heb", 9); c.drawString(x, y, company_number)

    sx0, syb, sx1, syt = irtp(340 - S, 740, 680 - S, 808)
    c.drawImage(tmp_sig, sx0, syb, width=sx1 - sx0, height=syt - syb,
                preserveAspectRatio=True, mask="auto")

    # === סקשיין ב ===
    for iy in [868, 913, 955]:
        x, y = itp(698 - CN_SHIFT, iy)
        c.setFont("Heb", 7); c.drawString(x, y, company_name[::-1])
        x, y = itp(476, iy)
        c.setFont("Heb", 9); c.drawString(x, y, company_number)

    x, y = itp(760 - S, 1078)
    c.setFont("Heb", 9); c.drawString(x, y, date_str)

    x, y = itp(540 - S, 1078)
    c.setFont("Heb", 9); c.drawString(x, y, OFFICE[::-1])

    stx0, styb, stx1, styt = irtp(15 - S, 1020, 320 - S, 1100)
    stx0 = max(stx0, 0)
    c.drawImage(tmp_stamp, stx0, styb, width=stx1 - stx0, height=styt - styb,
                preserveAspectRatio=True, mask="auto")

    c.save(); packet.seek(0)

    reader = PdfReader(base_pdf)
    overlay = PdfReader(packet)
    writer = PdfWriter()
    page = reader.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    out_buf = io.BytesIO()
    writer.write(out_buf)
    out_buf.seek(0)
    return out_buf.read()


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/fill-poa")
def fill_poa(data: CompanyData):
    """
    מקבל שם חברה / ח"פ / כתובת ומחזיר שני קבצי PDF ממולאים (base64):
    - primary_pdf_base64: ייצוג ראשי (2279/5א)
    - additional_pdf_base64: ייצוג נוסף (2279/6א)
    """
    try:
        primary_bytes = fill_form(
            FORM_PRIMARY, data.company_name, data.company_number,
            data.company_addr, data.date_str or None,
        )
        additional_bytes = fill_form(
            FORM_ADDITIONAL, data.company_name, data.company_number,
            data.company_addr, data.date_str or None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "primary_filename": f"ייצוג_ראשי_{data.company_name}.pdf",
        "primary_pdf_base64": base64.b64encode(primary_bytes).decode(),
        "additional_filename": f"ייצוג_נוסף_{data.company_name}.pdf",
        "additional_pdf_base64": base64.b64encode(additional_bytes).decode(),
    }
