# Phase 1 Implementation Plan - Top Priority Features

## Overview

Based on the analysis, here are the **top 3 features** that will have the biggest impact on making this a world-class system:

1. **Dynamic Language Detection & Selection** ⭐⭐⭐
2. **Comparison View (Before/After)** ⭐⭐⭐
3. **Search & Navigation** ⭐⭐

Let me break down exactly how to implement each one.

---

## 🌍 Feature 1: Dynamic Language Detection & Selection

### Why This Matters
- Current system only works for Japanese → English
- AI models can handle 100+ languages
- Users may have documents in Chinese, Korean, German, etc.
- Auto-detection removes friction

### Implementation Steps

#### Step 1: Update Database Schema (1 hour)

```sql
-- Add to projects table
ALTER TABLE projects ADD COLUMN source_language VARCHAR(10) DEFAULT 'auto';
ALTER TABLE projects ADD COLUMN source_language_detected VARCHAR(10);
ALTER TABLE projects ADD COLUMN source_language_confidence FLOAT;

-- Add to pages table for per-page detection
ALTER TABLE pages ADD COLUMN detected_language VARCHAR(10);
ALTER TABLE pages ADD COLUMN language_confidence FLOAT;
```

#### Step 2: Create Language Detector (2 hours)

```python
# New file: src/language_detector.py

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class LanguageDetector:
    """Detect source language using AI."""

    # Supported languages (ISO 639-1 codes)
    SUPPORTED_LANGUAGES = {
        'auto': 'Auto-Detect',
        'ja': 'Japanese (日本語)',
        'zh': 'Chinese Simplified (简体中文)',
        'zh-TW': 'Chinese Traditional (繁體中文)',
        'ko': 'Korean (한국어)',
        'en': 'English',
        'es': 'Spanish (Español)',
        'fr': 'French (Français)',
        'de': 'German (Deutsch)',
        'pt': 'Portuguese (Português)',
        'ru': 'Russian (Русский)',
        'ar': 'Arabic (العربية)',
        'hi': 'Hindi (हिन्दी)',
        'it': 'Italian (Italiano)',
        'th': 'Thai (ไทย)',
        'vi': 'Vietnamese (Tiếng Việt)',
        'id': 'Indonesian (Bahasa Indonesia)',
        'tr': 'Turkish (Türkçe)',
        'pl': 'Polish (Polski)',
        'nl': 'Dutch (Nederlands)',
    }

    def __init__(self, ai_client):
        """Initialize with AI client (Gemini/Claude)."""
        self.ai_client = ai_client

    def detect_language(self, text_sample: str) -> Dict[str, any]:
        """
        Detect language from OCR text sample.

        Args:
            text_sample: Text extracted from OCR (first 500 chars is enough)

        Returns:
            {
                'language': 'ja',
                'language_name': 'Japanese',
                'confidence': 0.98,
                'script': 'kanji/hiragana'
            }
        """
        # Truncate to first 500 chars for efficiency
        sample = text_sample[:500]

        prompt = f"""
        Detect the language of this text sample. Return ONLY a JSON object.

        Text: "{sample}"

        Return format:
        {{
            "language": "ISO-639-1 code (e.g., 'ja', 'zh', 'ko', 'en')",
            "confidence": 0.0 to 1.0,
            "script": "writing system (e.g., 'kanji', 'latin', 'cyrillic')"
        }}
        """

        try:
            response = self.ai_client.generate_content(prompt)
            result = self._parse_json_response(response)

            # Add language name
            lang_code = result.get('language', 'unknown')
            result['language_name'] = self.SUPPORTED_LANGUAGES.get(
                lang_code,
                f"Unknown ({lang_code})"
            )

            logger.info(f"Detected language: {result['language_name']} "
                       f"(confidence: {result['confidence']:.2%})")

            return result

        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            # Default to Japanese for backward compatibility
            return {
                'language': 'ja',
                'language_name': 'Japanese',
                'confidence': 0.0,
                'script': 'unknown'
            }

    def _parse_json_response(self, response) -> dict:
        """Parse AI response into JSON."""
        import json
        import re

        # Extract JSON from response
        text = response.text if hasattr(response, 'text') else str(response)

        # Try to find JSON in response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        raise ValueError("No valid JSON in response")
```

#### Step 3: Update Project Creation UI (1 hour)

```python
# In app_v3.py, update the "Create New Project" form

with st.expander("➕ Create New Project"):
    with st.form("new_project"):
        title = st.text_input("Book Title")
        author = st.text_input("Author")
        context = st.text_area("Book Context",
            help="Describe the book's subject matter for better translations")

        # NEW: Language selection
        col1, col2 = st.columns(2)

        with col1:
            source_lang = st.selectbox(
                "Source Language",
                options=list(LanguageDetector.SUPPORTED_LANGUAGES.keys()),
                format_func=lambda x: LanguageDetector.SUPPORTED_LANGUAGES[x],
                index=0,  # Default to 'auto'
                help="Select 'Auto-Detect' to let AI identify the language"
            )

        with col2:
            target_lang = st.selectbox(
                "Target Language",
                options=['en', 'es', 'fr', 'de', 'pt', 'zh', 'ja', 'ko', 'ar', 'ru', 'hi'],
                format_func=lambda x: LanguageDetector.SUPPORTED_LANGUAGES.get(x, x),
                index=0,  # Default to English
                help="Language to translate into"
            )

        if st.form_submit_button("Create Project"):
            if not title:
                st.error("Title is required")
            else:
                try:
                    project = api.create_project(
                        title=title,
                        author=author,
                        context=context,
                        source_language=source_lang,
                        target_language=target_lang
                    )
                    st.success(f"✅ Created: {title}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create project: {e}")
```

#### Step 4: Integrate into Translation Pipeline (2 hours)

```python
# In src/main.py, update BookTranslator class

class BookTranslator:
    def __init__(self, image_path, output_dir, book_context="",
                 source_language="auto", target_language="en"):
        self.source_language = source_language
        self.target_language = target_language
        self.language_detector = LanguageDetector(self.gemini_client)

    def process_page(self, verbose=False):
        """Process page with language detection."""

        # Step 1: OCR
        ocr_text = self.extract_text()

        # Step 2: Detect language if set to auto
        if self.source_language == "auto":
            detection = self.language_detector.detect_language(ocr_text)
            detected_lang = detection['language']
            confidence = detection['confidence']

            logger.info(f"Detected: {detection['language_name']} "
                       f"({confidence:.0%} confidence)")

            # Store detection results
            self.detected_language = detected_lang
            self.language_confidence = confidence
        else:
            # Use manually specified language
            self.detected_language = self.source_language
            self.language_confidence = 1.0

        # Step 3: Translate with detected/specified languages
        translated_text = self.translate_text(
            ocr_text,
            source_lang=self.detected_language,
            target_lang=self.target_language
        )

        # ... continue with diagrams, tables, etc.
```

#### Step 5: Update API & Database Models (1 hour)

```python
# backend/app/models/schemas.py

class ProjectCreate(BaseModel):
    title: str
    author: Optional[str] = None
    source_language: str = "auto"
    target_language: str = "en"
    book_context: Optional[str] = None

class ProjectResponse(BaseModel):
    # ... existing fields ...
    source_language: str
    target_language: str
    source_language_detected: Optional[str] = None
    source_language_confidence: Optional[float] = None

class PageResponse(BaseModel):
    # ... existing fields ...
    detected_language: Optional[str] = None
    language_confidence: Optional[float] = None
```

### Testing (1 hour)

1. Create project with source="auto", target="en"
2. Upload Japanese page → should detect Japanese
3. Upload Chinese page → should detect Chinese
4. Upload mixed page → should detect dominant language
5. Verify translations use correct source/target

### Total Time: ~8 hours

---

## 🔄 Feature 2: Comparison View (Before/After)

### Why This Matters
- Users want to see original vs translated side-by-side
- Helps verify translation quality
- Easy to spot layout issues
- Professional presentation

### Implementation Steps

#### Step 1: Create Comparison Component (3 hours)

```python
# In app_v3.py, add new function

def render_comparison_view():
    """Render side-by-side comparison of original and translated pages."""

    st.header("📊 Before & After Comparison")

    # Get completed pages
    completed = [p for p in st.session_state['pages']
                 if p.get('status') in ['completed', 'COMPLETED']]

    if not completed:
        st.info("No completed pages to compare. Process some pages first.")
        return

    # Page selector
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_idx = st.selectbox(
            "Select page to compare",
            range(len(completed)),
            format_func=lambda i: f"Page {completed[i].get('page_number')} - {completed[i].get('name')}"
        )

    with col2:
        sync_scroll = st.checkbox("Sync Scroll", value=True)

    page = completed[selected_idx]

    # Side-by-side layout
    col_before, col_after = st.columns(2)

    with col_before:
        st.subheader("🇯🇵 Original")

        # Get original image
        original_path = page.get('path') or page.get('original_image_path')

        if original_path and os.path.exists(original_path):
            st.image(original_path, use_container_width=True)
        else:
            # Fetch from backend
            api = get_api_client()
            project_id = st.session_state.current_project['id']
            page_id = page.get('id')
            try:
                url_data = api.get_download_url(project_id, page_id, file_type="original")
                st.image(url_data['url'], use_container_width=True)
            except:
                st.error("Original image not available")

        # Show original text
        if page.get('ocr_text'):
            with st.expander("Original Text (OCR)"):
                st.text(page['ocr_text'][:500] + "...")

    with col_after:
        st.subheader("🇬🇧 Translated")

        # Get translated PDF as image
        pdf_path = page.get('output_pdf_path')

        if pdf_path and os.path.exists(pdf_path):
            # Convert PDF to image
            pdf_image = get_pdf_thumbnail(pdf_path, width=800)
            if pdf_image:
                st.image(pdf_image, use_container_width=True)
            else:
                st.error("PDF preview not available")
        else:
            # Try to fetch from backend
            try:
                api = get_api_client()
                project_id = st.session_state.current_project['id']
                page_id = page.get('id')
                url_data = api.get_download_url(project_id, page_id, file_type="pdf")

                # Show PDF viewer
                st.markdown(
                    f'<iframe src="{url_data["url"]}" width="100%" height="800px"></iframe>',
                    unsafe_allow_html=True
                )
            except:
                st.error("Translated PDF not available")

        # Show translated text
        if page.get('translated_text'):
            with st.expander("Translated Text"):
                st.text(page['translated_text'][:500] + "...")

    # Download both
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if original_path and os.path.exists(original_path):
            with open(original_path, 'rb') as f:
                st.download_button(
                    "📥 Download Original",
                    f,
                    file_name=f"original_page_{page.get('page_number')}.jpg",
                    mime="image/jpeg"
                )

    with col2:
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                st.download_button(
                    "📥 Download Translated",
                    f,
                    file_name=f"translated_page_{page.get('page_number')}.pdf",
                    mime="application/pdf"
                )

    with col3:
        # Quality info
        if page.get('quality_score'):
            score = page['quality_score']
            level = page.get('quality_level', 'Unknown')
            st.metric("Quality Score", f"{score}/100", level)
```

#### Step 2: Add to Main Tabs (30 minutes)

```python
# In main() function, add comparison tab

tab_process, tab_review, tab_compare = st.tabs([
    "📋 Processing Queue",
    "📖 Review Results",
    "📊 Compare"  # NEW
])

with tab_process:
    render_page_list()

with tab_review:
    render_results_view()

with tab_compare:
    render_comparison_view()  # NEW
```

### Total Time: ~4 hours

---

## 🔍 Feature 3: Search & Navigation

### Why This Matters
- Finding specific content in 500-page books is painful
- Jump to pages by number
- Search by keyword
- Filter by content type

### Implementation Steps

#### Step 1: Add Search to Backend (2 hours)

```python
# backend/app/api/pages.py

@router.get("/search", response_model=PageListResponse)
def search_pages(
    project_id: int,
    query: str,
    search_in: str = "all",  # all, ocr_text, translated_text, page_number
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search pages within a project.

    Args:
        project_id: Project ID
        query: Search query
        search_in: Where to search (all, ocr_text, translated_text, page_number)
    """
    verify_project_access(project_id, current_user, db)

    # Build search query
    base_query = db.query(Page).filter(Page.project_id == project_id)

    if search_in == "page_number":
        # Exact page number search
        try:
            page_num = int(query)
            pages = base_query.filter(Page.page_number == page_num).all()
        except ValueError:
            pages = []
    else:
        # Text search
        search_pattern = f"%{query}%"

        if search_in == "ocr_text":
            pages = base_query.filter(Page.ocr_text.ilike(search_pattern)).all()
        elif search_in == "translated_text":
            pages = base_query.filter(Page.translated_text.ilike(search_pattern)).all()
        else:  # all
            pages = base_query.filter(
                (Page.ocr_text.ilike(search_pattern)) |
                (Page.translated_text.ilike(search_pattern))
            ).all()

    return {"pages": pages, "total": len(pages)}
```

#### Step 2: Add Search UI (2 hours)

```python
# In app_v3.py, add search component

def render_search_panel():
    """Render search interface."""

    st.markdown("---")
    st.subheader("🔍 Search Pages")

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        search_query = st.text_input(
            "Search",
            placeholder="Enter keyword or page number...",
            label_visibility="collapsed"
        )

    with col2:
        search_in = st.selectbox(
            "Search in",
            ["All", "Original Text", "Translated Text", "Page Number"],
            label_visibility="collapsed"
        )

    with col3:
        search_button = st.button("🔎 Search", use_container_width=True)

    if search_button and search_query:
        # Map UI options to API parameters
        search_field_map = {
            "All": "all",
            "Original Text": "ocr_text",
            "Translated Text": "translated_text",
            "Page Number": "page_number"
        }

        try:
            api = get_api_client()
            project_id = st.session_state.current_project['id']

            # Perform search
            results = api.search_pages(
                project_id,
                query=search_query,
                search_in=search_field_map[search_in]
            )

            # Display results
            st.success(f"Found {len(results['pages'])} matching pages")

            for page in results['pages']:
                with st.expander(f"Page {page['page_number']} - {page.get('status', 'Unknown')}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        if page.get('ocr_text') and search_query.lower() in page['ocr_text'].lower():
                            # Show context around match
                            context = _get_search_context(page['ocr_text'], search_query)
                            st.markdown(f"**Original:** ...{context}...")

                    with col2:
                        if page.get('translated_text') and search_query.lower() in page['translated_text'].lower():
                            context = _get_search_context(page['translated_text'], search_query)
                            st.markdown(f"**Translated:** ...{context}...")

                    # Jump button
                    if st.button(f"Jump to Page {page['page_number']}", key=f"jump_{page['id']}"):
                        # Calculate which pagination page this is on
                        page_idx = (page['page_number'] - 1) // st.session_state.page_size
                        st.session_state.current_page_offset = page_idx * st.session_state.page_size
                        st.session_state.pages_loaded_from_backend = False
                        st.rerun()

        except Exception as e:
            st.error(f"Search failed: {e}")

def _get_search_context(text: str, query: str, context_chars: int = 100) -> str:
    """Get context around search match."""
    text_lower = text.lower()
    query_lower = query.lower()

    idx = text_lower.find(query_lower)
    if idx == -1:
        return text[:200]

    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(query) + context_chars)

    context = text[start:end]

    # Highlight the match
    context = context.replace(
        text[idx:idx+len(query)],
        f"**{text[idx:idx+len(query)]}**"
    )

    return context
```

#### Step 3: Update API Client (30 minutes)

```python
# src/api_client.py

def search_pages(self, project_id: int, query: str,
                 search_in: str = "all") -> Dict[str, Any]:
    """Search pages within a project."""
    response = requests.get(
        f"{self.base_url}/projects/{project_id}/pages/search",
        params={"query": query, "search_in": search_in},
        headers=self._headers()
    )
    response.raise_for_status()
    return response.json()
```

### Total Time: ~5 hours

---

## 📊 Summary

### Total Implementation Time: ~17 hours (~2-3 days of focused work)

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Language Detection | ⭐⭐⭐⭐⭐ | 8 hours | 1 |
| Comparison View | ⭐⭐⭐⭐ | 4 hours | 2 |
| Search & Navigation | ⭐⭐⭐⭐ | 5 hours | 3 |

### What Users Will Get:

1. **Any Language → Any Language** translation
2. **Side-by-side comparison** to verify quality
3. **Instant search** to find content in 500+ page books

### Order of Implementation:

**Day 1**: Language Detection (8 hours)
- Morning: Database + Language Detector
- Afternoon: UI + Integration + Testing

**Day 2**: Comparison View + Search (9 hours)
- Morning: Comparison View (4 hours)
- Afternoon: Search & Navigation (5 hours)

---

## 🚀 Next Steps

Would you like me to:
1. Start implementing Language Detection first?
2. Create the migration scripts for database changes?
3. Implement all three features in sequence?

Let me know and I'll begin coding! 💪
