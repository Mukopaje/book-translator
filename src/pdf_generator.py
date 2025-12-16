from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pathlib import Path
from typing import List, Dict
from PIL import Image


def assemble_book(pages: List[Dict], out_path: str, metadata: Dict = None, glossary: Dict = None):
    """
    Assemble a book PDF from image pages.

    pages: list of dicts {'path': ..., 'role': 'page'|'cover'|'back'}
    out_path: output PDF path
    metadata: {'title':..., 'author':...}
    glossary: dict of term->translation
    """
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4

    # Order pages: cover first (role=='cover'), then normal pages, then back
    cover = [p for p in pages if p.get('role') == 'cover']
    back = [p for p in pages if p.get('role') == 'back']
    normals = [p for p in pages if p.get('role') == 'page']
    ordered = cover + normals + back

    # Add metadata page
    if metadata:
        c.setFont('Helvetica-Bold', 20)
        c.drawCentredString(width/2, height - 100, metadata.get('title', ''))
        c.setFont('Helvetica', 12)
        c.drawCentredString(width/2, height - 130, f"Author: {metadata.get('author','')}")
        c.showPage()

    # Add each image as a full page (fit preserving aspect)
    for p in ordered:
        try:
            img = Image.open(p['path'])
            iw, ih = img.size
            aspect = iw / ih
            page_aspect = width / height
            if aspect > page_aspect:
                # image wider
                draw_w = width
                draw_h = width / aspect
            else:
                draw_h = height
                draw_w = height * aspect

            x = (width - draw_w) / 2
            y = (height - draw_h) / 2
            c.drawImage(ImageReader(img), x, y, draw_w, draw_h)
            c.showPage()
        except Exception:
            continue

    # Glossary page(s)
    if glossary:
        c.setFont('Helvetica-Bold', 16)
        c.drawString(40, height - 60, 'Glossary')
        c.setFont('Helvetica', 10)
        y = height - 90
        for term, trans in glossary.items():
            c.drawString(40, y, f"{term} — {trans}")
            y -= 14
            if y < 50:
                c.showPage()
                y = height - 50
        c.showPage()

    c.save()
    return out_path
