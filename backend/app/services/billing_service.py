"""
Professional PDF Document Generator for CRM (Invoices, Receipts, Quotations)
Uses ReportLab for pixel-perfect, branded documents with Watermark Stamps.
"""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from datetime import datetime
import json

class BillingPDFGenerator:
    """Generates professional branded PDFs for billing documents."""
    
    def __init__(self, output_dir="output/billing"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='BrandedTitle',
            fontSize=24,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=20,
            fontName='Helvetica-Bold'
        ))
        self.styles.add(ParagraphStyle(
            name='DocInfo',
            fontSize=10,
            textColor=colors.grey,
            alignment=2 # Right aligned
        ))
        self.styles.add(ParagraphStyle(
            name='ItemDesc',
            fontSize=9,
            textColor=colors.black,
            leading=12
        ))

    def _draw_watermark(self, c, doc, status):
        """Draw a professional diagonal status stamp."""
        c.saveState()
        c.setFont('Helvetica-Bold', 80)
        
        # Determine color based on status
        color_map = {
            "PAID": colors.Color(0, 0.5, 0, alpha=0.1),
            "DRAFT": colors.Color(0.5, 0.5, 0.5, alpha=0.1),
            "SENT": colors.Color(0, 0, 0.5, alpha=0.05),
            "VOID": colors.Color(0.7, 0, 0, alpha=0.1),
            "OVERDUE": colors.Color(0.8, 0, 0, alpha=0.1)
        }
        
        c.setFillGray(0.5, 0.1)
        if status in color_map:
            c.setFillColor(color_map[status])
            
        c.translate(3*inch, 5*inch)
        c.rotate(45)
        c.drawCentredString(0, 0, status.upper())
        c.restoreState()

    def generate_document(self, doc_id, doc_type, user_email, amount, items_json, status, 
                          currency="USD", tax_rate=0.0, discount_rate=0.0, notes=None, 
                          due_date=None, company_info=None):
        """Main entry point to generate a PDF document with dynamic pricing and watermarks."""
        filename = f"{doc_type.lower()}_{doc_id}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        # Use a custom PageTemplate to draw watermark on every page
        def on_page(canvas, doc):
            self._draw_watermark(canvas, doc, status)
            
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []
        
        # 1. Header (Logo & Document Info)
        company_name = (company_info or {}).get('company_name', "Technical Book Translator")
        header_data = [
            [Paragraph(company_name, self.styles['BrandedTitle']), 
             Paragraph(f"<b>{doc_type.upper()}</b><br/>ID: {doc_id[:8].upper()}<br/>Date: {datetime.now().strftime('%Y-%m-%d')}<br/>Due: {due_date or 'On Receipt'}", self.styles['DocInfo'])]
        ]
        header_table = Table(header_data, colWidths=[4*inch, 2*inch])
        elements.append(header_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # 2. Bill To
        elements.append(Paragraph(f"<b>BILL TO:</b><br/>{user_email}", self.styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # 3. Line Items Table
        items = json.loads(items_json) if isinstance(items_json, str) else items_json
        table_data = [["Service Description", "Qty", "Rate", "Total"]]
        
        subtotal = 0
        for item in items:
            line_total = item.get('quantity', 1) * item.get('price', 0)
            subtotal += line_total
            table_data.append([
                Paragraph(f"<b>{item.get('name', 'Service')}</b><br/>{item.get('description', '')}", self.styles['ItemDesc']),
                str(item.get('quantity', 1)),
                f"{currency} {item.get('price', 0):.2f}",
                f"{currency} {line_total:.2f}"
            ])
            
        # 4. Totals Block
        discount_val = subtotal * (discount_rate / 100.0)
        tax_val = (subtotal - discount_val) * (tax_rate / 100.0)
        grand_total = subtotal - discount_val + tax_val

        table_data.append(["", "", "Subtotal", f"{currency} {subtotal:.2f}"])
        if discount_rate > 0:
            table_data.append(["", "", f"Discount ({discount_rate}%)", f"-{currency} {discount_val:.2f}"])
        if tax_rate > 0:
            table_data.append(["", "", f"Tax ({tax_rate}%)", f"{currency} {tax_val:.2f}"])
        table_data.append(["", "", "<b>GRAND TOTAL</b>", f"<b>{currency} {grand_total:.2f}</b>"])
        
        items_table = Table(table_data, colWidths=[3.5*inch, 0.5*inch, 1*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -4), 0.5, colors.grey), # Grid for items only
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEABOVE', (2, -1), (3, -1), 1, colors.black), # Bold line for grand total
        ]))
        elements.append(items_table)
        
        # 5. Notes & Terms
        if notes or (company_info or {}).get('company_address'):
            elements.append(Spacer(1, 0.5*inch))
            if notes:
                elements.append(Paragraph("<b>Notes:</b>", self.styles['Normal']))
                elements.append(Paragraph(notes, self.styles['Normal']))
                elements.append(Spacer(1, 0.2*inch))
            
            if company_info.get('company_address'):
                elements.append(Paragraph(f"<font size=8 color='grey'>{company_info['company_address']}</font>", self.styles['Normal']))

        doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
        return filepath
