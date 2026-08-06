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
FORM_PRIMARY = os.path.join(ASSETS_DIR, "form_primary.pdf")
FORM_ADDITIONAL = os.path.join(ASSETS_DIR, "form_additional.pdf")
SIG_IMG = os.path.join(ASSETS_DIR, "signature.png")
STAMP_IMG = os.path.join(ASSETS_DIR, "stamp.png")

IMG_W, IMG_H = 924, 1316
S = 118
CN_SHIFT_A = 75
CN_SHIFT_B = 130
OFFICE = 'סמי ביטון, רו"ח'


class CompanyData(BaseModel):
    company_name: str
    company_number: str
    company_addr: str = ""
    date_str: str = ""
    phone: str = ""
    email: str = ""


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


def fill_form(zip_pdf_path, company_name, company_number, company_addr="", date_str=None, phone="", email=""):
    if not date_str:
        date_str = date.today().strftime("%d/%m/%Y")

    pdfmetrics.registerFont(TTFont("Heb", FONT_PATH))

    tmp_sig = "/tmp/sig_t.png"
    tmp_stamp = "/tmp/stamp_t.png"
    make_transparent(SIG_IMG, tmp_sig)
    make_transparent(STAMP_IMG, tmp_stamp)

    with open(zip_pdf_path, "rb") as f:
        base_pdf = io.BytesIO(f.read())
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
    x, y = itp(620 - CN_SHIFT_A, 335)
    c.setFont("Heb", 7); c.drawString(x, y, company_name[::-1])

    x, y = itp(252, 336)
    c.setFont("Heb", 9); c.drawString(x, y, company_number)

    if company_addr:
        x, y = itp(618, 390)
        c.setFont("Heb", 9); c.drawString(x, y, company_addr[::-1])


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
            data.company_addr, data.date_str or None, data.phone, data.email,
        )
        additional_bytes = fill_form(
            FORM_ADDITIONAL, data.company_name, data.company_number,
            data.company_addr, data.date_str or None, data.phone, data.email,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "primary_filename": f"ייצוג_ראשי_{data.company_name}.pdf",
        "primary_pdf_base64": base64.b64encode(primary_bytes).decode(),
        "additional_filename": f"ייצוג_נוסף_{data.company_name}.pdf",
        "additional_pdf_base64": base64.b64encode(additional_bytes).decode(),
    }
