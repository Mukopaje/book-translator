# Advanced CRM & Financial Operations Strategy

Inspired by **HubSpot** (Relationship management) and **Xero** (Financial precision), our CRM will move from a "form" to a "workflow."

## 1. Professional Workflow: The "Consultative Sales" Flow

### Stage 1: Identification & Context (The Header)
*   **Client Selection**: Searchable dropdown of existing users or "Quick Add" for new leads.
*   **Terms & Metadata**: 
    *   **Currency**: Dynamic selection (USD, EUR, JPY, GBP).
    *   **Dates**: Automatic "Issue Date" and selectable "Expiry Date" (for Quotes) or "Due Date" (for Invoices).
    *   **Discounting**: Support for percentage (%) or flat amount ($) globally or per-line-item.
    *   **Tax Engine**: Selectable VAT/Sales Tax rates based on client region.

### Stage 2: Scope Definition (Dynamic Line Items)
*   **Dynamic Grid**: Ability to "Add Row" for multiple services (e.g., "Diagram Reconstruction," "Prose Translation," "API Integration").
*   **Rich Text Descriptions**: Support for long-form service descriptions (scope of work).
*   **Calculated Logic**: Real-time totaling of Subtotal → Discount → Tax → Grand Total.

### Stage 3: Professional Artifact (The PDF)
*   **Visual Stamps/Watermarks**: Large, diagonal background stamps:
    *   `DRAFT` (Grey)
    *   `SENT` (Blue)
    *   `PAID` (Green - with Receipt)
    *   `OVERDUE` (Red)
*   **Signature Lines**: Professional space for both parties.

---

## 2. Feature Roadmap

### A. Lifecycle Management
1.  **Quotation → Invoice Conversion**: One-click "Accept Quote" that clones the data into an Invoice and triggers a Stripe Checkout session.
2.  **Tracking**: See exactly when a user opened the link (future integration).
3.  **B2B Client Profiles**: Store company registration numbers, specific billing addresses, and default discount tiers.

### B. Technical Integration
*   **Backend**: 
    *   Extend `billing_documents` table with `due_date`, `expiry_date`, `discount_rate`, and `tax_rate`.
    *   Implement `StripeWebhook` to auto-convert Invoices to Receipts and apply the **"PAID" stamp**.
*   **PDF Service**: Use ReportLab "Canvases" to draw high-opacity background watermarks.

---

## 3. Implementation Plan (Phased)

### Phase 1: Enhanced Data Model
- [ ] Add columns to `billing_documents`: `due_date`, `expiry_date`, `discount_rate`, `tax_rate`, `notes`.
- [ ] Update `BillingDocument` schema.

### Phase 2: Multi-Stage Document Builder (UI)
- [ ] Build the "Wizard" interface in Streamlit using `st.session_state` to store partial progress.
- [ ] Implement a dynamic "Line Item" editor with `Add Row` buttons.

### Phase 3: Professional ReportLab Stamps
- [ ] Update `BillingPDFGenerator` to include watermark logic based on document status.
- [ ] Add "Company Metadata" (Registration #, Tax ID) to document footer.
