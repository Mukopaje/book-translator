# CRM & Financial Operations Implementation Plan

## 1. Goal: Professional Billing & Document Lifecycle
To build a modern CRM around the translation engine that handles Invoicing, Quotations, and Receipts with high-end PDF generation.

---

## 2. New Data Models (Backend)

### A. Document Table (`billing_documents`)
*   `id`: UUID
*   `type`: ENUM (QUOTATION, INVOICE, RECEIPT)
*   `user_id`: FK(users.id)
*   `status`: ENUM (DRAFT, SENT, PAID, VOID)
*   `amount`: DECIMAL
*   `currency`: String (default: USD)
*   `items`: JSONB (List of items: {description, quantity, price})
*   `stripe_invoice_id`: String (optional)
*   `pdf_gcs_path`: String (Path to the generated professional PDF)

---

## 3. Modular CRM Features

### A. Quotation Engine (Lead Conversion)
*   **Feature**: Admin can generate a formal quotation for a bulk translation project (e.g., "1,000 page fleet manual").
*   **Workflow**: Admin creates quote → System generates professional PDF → Send unique link to user → User clicks "Accept & Pay" → Converts to Invoice + Stripe Checkout.

### B. Automated Receipting
*   **Feature**: Every successful Stripe transaction automatically triggers a "Receipt Generation" task.
*   **Design**: Clean, minimalist layout with high-end typography, including the "Technical Book Translator" logo and specialized tax details if needed.

### C. Invoicing for B2B
*   **Feature**: Net-30 payment support for corporate clients.
*   **Status Tracking**: Dashboard for Admin to track outstanding "Overdue" invoices.

---

## 4. Document Generation Tech Stack
*   **Engine**: `ReportLab` or `WeasyPrint` for pixel-perfect PDF layouts.
*   **Templates**: Professional HTML/CSS templates styled with the **Dark Technical** brand for consistency.

---

## 5. Revenue Generation Strategies (The "Upsell")

1.  **Priority "Human-in-the-Loop" Review**:
    *   An option in the CRM/Checkout for a professional human editor to verify the diagram labels (High-margin upsell).
2.  **Archival Preservation Add-on**:
    *   Charge a small yearly fee to keep high-res originals and translations in the "Secure Vault" with 99.999% durability (GCS Nearline).
3.  **API White-labeling**:
    *   Allow engineering firms to use your engine via the CRM as a "Service Portal" for their own internal documents.

---

## 6. Implementation Phases

### Phase 1: Billing Infrastructure (FastAPI)
- [ ] Create `billing_documents` table.
- [ ] Implement `PDFGeneratorService` for professional receipts.
- [ ] Add `GET /billing/{doc_id}` public link for secure downloading.

### Phase 2: Admin CRM Module (Streamlit)
- [ ] Add **"💼 CRM & Billing"** tab to Admin Dashboard.
- [ ] Build "Quick Invoice" form.
- [ ] Add "Transaction Log" table showing cash flow.

### Phase 3: User Billing Center
- [ ] Add **"💳 Billing History"** section to User Dashboard.
- [ ] Allow users to download past Receipts and Invoices.

---

## 7. Hosting & Managed Systems
*   **Managed PDF Generation**: Use a serverless function (AWS Lambda or Railway) for document rendering to keep the main worker focused on translation.
*   **Stripe Tax**: Enable Stripe Tax within the CRM to handle global VAT/Sales tax automatically.
