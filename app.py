import os
import uuid
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load .env from project root
project_root = Path(__file__).parent.resolve()
load_dotenv(project_root / '.env')
logger.info(f"Loaded .env from {project_root}")

# Ensure src is importable
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import BookTranslator

OUTPUT_DIR = "output"
IMAGES_DIR = "images_to_process"
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def init_state():
    if 'pages' not in st.session_state:
        st.session_state['pages'] = []
    if 'metadata' not in st.session_state:
        st.session_state['metadata'] = {'title': '', 'author': ''}


def add_page(uploaded_file, role='page'):
    if not uploaded_file:
        return
    uid = uuid.uuid4().hex[:8]
    filename = f"{uid}_{uploaded_file.name}"
    path = os.path.join(IMAGES_DIR, filename)
    with open(path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    st.session_state['pages'].append({'path': path, 'name': uploaded_file.name, 'role': role, 'status': 'pending'})


def process_page(idx):
    page = st.session_state['pages'][idx]
    logger.info(f"Processing page {idx}: {page['name']}")
    
    translator = BookTranslator(page['path'], OUTPUT_DIR)
    results = translator.process_page(verbose=True)  # Enable verbose for terminal logging
    
    page['status'] = 'done' if results.get('success') else 'error'
    page['results'] = results
    
    # Log results summary
    if results.get('success'):
        ocr_len = results.get('steps', {}).get('ocr_extraction', {}).get('text_length', 0)
        trans_len = results.get('steps', {}).get('translation', {}).get('text_length', 0)
        diagrams_count = results.get('steps', {}).get('pdf_creation', {}).get('diagrams_translated', 0)
        logger.info(f"SUCCESS Page {idx}: OCR {ocr_len} chars -> Translation {trans_len} chars, {diagrams_count} diagrams")
    else:
        logger.error(f"FAILED Page {idx}: {results.get('error')}")
    
    return results


def export_pdf(book_title):
    """Export all pages to a single PDF book"""
    try:
        from PyPDF2 import PdfMerger
        import os
        
        # Collect all individual page PDFs
        pdf_pages = []
        for p in st.session_state['pages']:
            stem = Path(p['path']).stem
            pdf_path = os.path.join(OUTPUT_DIR, f"{stem}_translated.pdf")
            
            if os.path.exists(pdf_path):
                pdf_pages.append(pdf_path)
                logger.info(f"Found PDF: {pdf_path}")
            else:
                logger.warning(f"Missing PDF for: {stem}")
        
        if not pdf_pages:
            st.warning('No translated PDFs found. Process pages first.')
            return None
        
        # Merge PDFs
        merger = PdfMerger()
        for pdf in pdf_pages:
            merger.append(pdf)
        
        # Save merged PDF
        output_path = os.path.join(OUTPUT_DIR, f"{book_title or 'book'}_complete.pdf")
        merger.write(output_path)
        merger.close()
        
        logger.info(f"Merged {len(pdf_pages)} pages into: {output_path}")
        return output_path
        
    except ImportError:
        st.warning('PyPDF2 not installed. Install with: pip install PyPDF2')
        return None
    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        st.error(f'PDF export failed: {e}')
        return None


def main():
    st.set_page_config(page_title='Book Translator', layout='wide')
    init_state()

    st.title('📚 Book Translator — AI-Powered Japanese to English')
    
    # Show translator info
    try:
        from src.gemini_translator import GeminiTranslator
        st.success('🤖 Using Google Gemini 2.0 Flash for intelligent translation')
    except:
        st.info('🔤 Using Google Cloud Translate API')
    
    st.markdown('---')

    with st.sidebar:
        st.header('Book Metadata')
        st.session_state['metadata']['title'] = st.text_input('Book title', st.session_state['metadata'].get('title', ''))
        st.session_state['metadata']['author'] = st.text_input('Author', st.session_state['metadata'].get('author', ''))
        st.markdown('---')
        st.info('Upload pages one-by-one or upload multiple and add them.')
        st.markdown('---')
        st.header('Glossary')
        if 'glossary' not in st.session_state:
            st.session_state['glossary'] = {}
        if st.button('Auto-extract glossary'):
            # Enhanced extraction: support English and Japanese heuristics
            terms = {}
            for p in st.session_state['pages']:
                tpath = os.path.join(OUTPUT_DIR, f"{Path(p['path']).stem}_translation.txt")
                jpath = os.path.join(OUTPUT_DIR, f"{Path(p['path']).stem}_japanese.txt")
                content = ''
                if os.path.exists(tpath):
                    with open(tpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                elif os.path.exists(jpath):
                    with open(jpath, 'r', encoding='utf-8') as f:
                        content = f.read()

                # English-like extraction
                for w in content.split():
                    if len(w) > 5 and all(ord(ch) < 128 for ch in w) and w.isalpha():
                        terms[w] = terms.get(w, 0) + 1

                # Japanese-ish extraction: extract continuous non-ASCII sequences (kanji/kana)
                import re
                jap_candidates = re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]{2,}', content)
                for jc in jap_candidates:
                    terms[jc] = terms.get(jc, 0) + 1

            # take top 60 terms
            sorted_terms = sorted(terms.items(), key=lambda x: x[1], reverse=True)[:60]
            for term, _ in sorted_terms:
                if term not in st.session_state['glossary']:
                    st.session_state['glossary'][term] = ''
            st.success('Extracted glossary candidates')
        st.write('Edit glossary entries below (term -> translation):')
        for term in list(st.session_state['glossary'].keys()):
            val = st.text_input(f'{term}', value=st.session_state['glossary'][term])
            st.session_state['glossary'][term] = val

    st.header('Upload Page')
    uploaded = st.file_uploader('Choose an image (one at a time)', type=['jpg', 'jpeg', 'png'], accept_multiple_files=False)
    col1, col2, col3 = st.columns([1, 1, 1])
    role = col1.selectbox('Role', options=['page', 'cover', 'back'], index=0)
    if col2.button('Add page'):
        if uploaded is None:
            st.warning('Select a file first')
        else:
            add_page(uploaded, role=role)
            st.success(f"Added: {uploaded.name} as {role}")

    st.markdown('---')
    st.header('Pages')
    if not st.session_state['pages']:
        st.info('No pages added yet')
    else:
        for i, p in enumerate(st.session_state['pages']):
            st.subheader(f"{i+1}. {p['name']} ({p['role']})")
            cols = st.columns([1, 3, 1, 1])
            with cols[1]:
                st.image(p['path'], width=300)
            with cols[2]:
                if st.button('Process this page', key=f'proc_{i}'):
                    with st.spinner('Processing...'):
                        res = process_page(i)
                        if res.get('success'):
                            st.success('✓ Processed successfully')
                            # Show processing stats
                            steps = res.get('steps', {})
                            ocr_info = steps.get('ocr_extraction', {})
                            trans_info = steps.get('translation', {})
                            pdf_info = steps.get('pdf_creation', {})
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("OCR", f"{ocr_info.get('text_length', 0)} chars")
                            with col2:
                                st.metric("Translation", f"{trans_info.get('text_length', 0)} chars")
                            with col3:
                                diagrams = pdf_info.get('diagrams_translated', 0)
                                st.metric("Diagrams", f"{diagrams}")
                            
                            pdf_file = pdf_info.get('output_file', '')
                            if pdf_file:
                                st.info(f"📄 Created PDF: {pdf_file}")
                        else:
                            st.error('✗ Failed: ' + str(res.get('error')))
                st.write('Status: ' + p.get('status', 'pending'))
            with cols[3]:
                # Reorder controls
                if st.button('↑', key=f'up_{i}') and i > 0:
                    st.session_state['pages'][i], st.session_state['pages'][i-1] = st.session_state['pages'][i-1], st.session_state['pages'][i]
                    st.experimental_rerun()
                if st.button('↓', key=f'down_{i}') and i < len(st.session_state['pages']) - 1:
                    st.session_state['pages'][i], st.session_state['pages'][i+1] = st.session_state['pages'][i+1], st.session_state['pages'][i]
                    st.experimental_rerun()
                if st.button('Remove', key=f'rem_{i}'):
                    st.session_state['pages'].pop(i)
                    st.experimental_rerun()

    st.markdown('---')
    st.header('Batch Actions')
    if 'futures' not in st.session_state:
        st.session_state['futures'] = {}

    if st.button('Process all pages'):
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        for i in range(len(st.session_state['pages'])):
            if st.session_state['pages'][i].get('status') != 'done' and i not in st.session_state['futures']:
                fut = executor.submit(process_page, i)
                st.session_state['futures'][i] = fut
        st.success('Background processing started')

    # Show progress for background tasks
    if st.session_state.get('futures'):
        import concurrent.futures
        total = len(st.session_state['futures'])
        done = 0
        for idx, fut in list(st.session_state['futures'].items()):
            if fut.done():
                done += 1
                try:
                    res = fut.result()
                except Exception:
                    res = None
                st.session_state['pages'][idx]['status'] = 'done' if res and res.get('success') else 'error'
                st.session_state['futures'].pop(idx, None)
        if total > 0:
            prog = int((done / max(1, total)) * 100)
            st.progress(prog)

    st.markdown('---')
    st.header('Review & Edit')
    if st.session_state['pages']:
        sel = st.selectbox('Select page to review', options=list(range(len(st.session_state['pages']))), format_func=lambda x: f"{x+1}. {st.session_state['pages'][x]['name']}")
        
        # Add a refresh button
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.write("")
        with col_b:
            if st.button('🔄 Refresh View', key='refresh_view'):
                st.rerun()
        
        page = st.session_state['pages'][sel]
        
        # Show page overview
        st.subheader('Page Preview')
        col1, col2 = st.columns(2)
        with col1:
            st.write('**Original Page (Japanese)**')
            st.image(page['path'], width=300)
        with col2:
            st.write('**Translated PDF**')
            # Look for PDF file
            stem = Path(page['path']).stem
            pdf_path = os.path.join(OUTPUT_DIR, f"{stem}_translated.pdf")
            
            if os.path.exists(pdf_path):
                st.caption(f"📁 {stem}_translated.pdf")
                # Show first page of PDF as image using pdf2image or similar
                st.success(f"✅ PDF available: [{stem}_translated.pdf]({pdf_path})")
                
                # Show file info
                file_size = os.path.getsize(pdf_path) / 1024  # KB
                st.caption(f"Size: {file_size:.1f} KB")
                
                # Download link
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=f"{stem}_translated.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_{sel}"
                    )
            else:
                st.info('⚠ Process page first to generate PDF')
                logger.warning(f"No PDF generated for translated page")
                logger.warning(f"No translated image found for stem: {stem}")
        
        # Show original OCR if available - always try to load from file first
        ocr_text = ''
        jpath = os.path.join(OUTPUT_DIR, f"{Path(page['path']).stem}_japanese.txt")
        if os.path.exists(jpath):
            with open(jpath, 'r', encoding='utf-8') as f:
                ocr_text = f.read()
        elif page.get('results'):
            # Fallback to in-memory results if file doesn't exist
            ocr_text = page['results']['steps'].get('ocr_extraction', {}).get('preview', '')
        st.subheader('OCR / Original Text')
        # Show OCR stats
        if ocr_text:
            import re
            kanji = len(re.findall(r'[\u4e00-\u9fff]', ocr_text))
            hiragana = len(re.findall(r'[\u3040-\u309f]', ocr_text))
            katakana = len(re.findall(r'[\u30a0-\u30ff]', ocr_text))
            total_jp = kanji + hiragana + katakana
            jp_percent = int(total_jp/max(1,len(ocr_text))*100)
            st.caption(f"📊 {len(ocr_text)} chars total | {total_jp} Japanese ({jp_percent}%) | Kanji:{kanji} Hiragana:{hiragana} Katakana:{katakana}")
        st.text_area('Original OCR', value=ocr_text, height=120, key=f'ocr_{sel}')

        # Load translated text - always try to load from file first
        trans_text = ''
        tpath = os.path.join(OUTPUT_DIR, f"{Path(page['path']).stem}_translation.txt")
        if os.path.exists(tpath):
            with open(tpath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract just the English translation if it has the format markers
                if '=== TRANSLATION (English) ===' in content:
                    trans_text = content.split('=== TRANSLATION (English) ===')[1].strip()
                else:
                    trans_text = content
        elif page.get('results'):
            # Fallback to in-memory results if file doesn't exist
            trans_text = page.get('results', {}).get('steps', {}).get('translation', {}).get('preview', '')

        st.subheader('Translated Text (editable)')
        if trans_text:
            word_count = len(trans_text.split())
            st.caption(f"📊 {len(trans_text)} chars | {word_count} words")
        edited = st.text_area('Edit translated text', value=trans_text, height=250, key=f'trans_{sel}')
        if st.button('Save edited translation', key=f'save_trans_{sel}'):
            # overwrite translation file
            with open(tpath, 'w', encoding='utf-8') as f:
                f.write(edited)
            st.success('Saved edited translation')
            # Regenerate translated page with new translation
            if st.button('Update translated page with edits', key=f'update_overlay_{sel}'):
                try:
                    from src.text_overlay import TextOverlay
                    overlay = TextOverlay(page['path'])
                    overlay.create_translated_page(edited, os.path.join(OUTPUT_DIR, f"{Path(page['path']).stem}_translated_page.jpg"))
                    st.success('Translated page updated')
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f'Update failed: {e}')

    st.markdown('---')
    st.header('Export')
    if st.button('Export book to PDF'):
        out = export_pdf(st.session_state['metadata'].get('title', 'book'))
        if out:
            st.success(f'Exported to {out}')
            st.markdown(f'Download: [{out}]({out})')

    # Show available translated images and PDFs
    st.markdown('---')
    st.subheader('Generated outputs')
    files = []
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith('.jpg') or f.endswith('.pdf') or f.endswith('.png'):
            files.append(f)
    if files:
        for fn in files:
            path = os.path.join(OUTPUT_DIR, fn)
            st.write(fn)
            if fn.endswith('.jpg') or fn.endswith('.png'):
                st.image(path, width=300)
            st.markdown(f'[Download]({path})')
    else:
        st.info('No generated outputs yet')


if __name__ == '__main__':
    main()
