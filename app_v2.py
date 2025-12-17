import os
import uuid
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
import logging
import time

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
    if 'processing_queue' not in st.session_state:
        st.session_state['processing_queue'] = []

def add_page(uploaded_file, role='page'):
    if not uploaded_file:
        return
    uid = uuid.uuid4().hex[:8]
    filename = f"{uid}_{uploaded_file.name}"
    path = os.path.join(IMAGES_DIR, filename)
    with open(path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    
    page_info = {
        'id': uid,
        'path': path,
        'name': uploaded_file.name,
        'role': role,
        'status': 'pending',
        'results': None,
        'error': None
    }
    st.session_state['pages'].append(page_info)
    return page_info

def process_page_task(page_idx):
    page = st.session_state['pages'][page_idx]
    page['status'] = 'processing'
    
    try:
        # Get book context from metadata
        book_context = st.session_state['metadata'].get('context', '')
        if st.session_state['metadata'].get('title'):
            book_context = f"{st.session_state['metadata']['title']}. {book_context}"
            
        translator = BookTranslator(page['path'], OUTPUT_DIR, book_context=book_context)
        results = translator.process_page(verbose=True)
        
        if results.get('success'):
            page['status'] = 'completed'
            page['results'] = results
            
            # Check for warnings (like PDF creation failure)
            if 'warnings' in results:
                page['warnings'] = results['warnings']
                
            # Verify PDF existence
            stem = Path(page['path']).stem
            pdf_path = os.path.join(OUTPUT_DIR, f"{stem}_translated.pdf")
            if not os.path.exists(pdf_path):
                page['warnings'] = page.get('warnings', []) + ["PDF file was not created despite success status"]
                
        else:
            page['status'] = 'failed'
            page['error'] = results.get('error', 'Unknown error')
            
    except Exception as e:
        page['status'] = 'failed'
        page['error'] = str(e)
        import traceback
        traceback.print_exc()

    return page

def render_sidebar():
    with st.sidebar:
        st.title("📚 Book Translator")
        st.markdown("AI-Powered Japanese to English Translation")
        
        st.header("Project Settings")
        st.session_state['metadata']['title'] = st.text_input('Book Title', st.session_state['metadata'].get('title', ''))
        st.session_state['metadata']['author'] = st.text_input('Author', st.session_state['metadata'].get('author', ''))
        st.session_state['metadata']['context'] = st.text_area(
            'Book Context / Description', 
            st.session_state['metadata'].get('context', ''),
            help="Describe what the book is about (e.g. '4-stroke engine maintenance manual'). This helps the AI use correct technical terminology."
        )
        
        st.markdown("---")
        st.header("Upload")
        uploaded = st.file_uploader("Add Pages", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
        if uploaded:
            for f in uploaded:
                # Check if already added
                if not any(p['name'] == f.name for p in st.session_state['pages']):
                    add_page(f)
            st.success(f"Added {len(uploaded)} pages")
            
        st.markdown("---")
        if st.button("Clear All Pages"):
            st.session_state['pages'] = []
            st.rerun()

def render_page_list():
    st.header(f"Pages ({len(st.session_state['pages'])})")
    
    if not st.session_state['pages']:
        st.info("Upload pages to begin.")
        return

    # Batch actions
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Process All Pending"):
            with st.status("Processing pages...", expanded=True) as status:
                for i, page in enumerate(st.session_state['pages']):
                    if page['status'] in ['pending', 'failed']:
                        st.write(f"Processing {page['name']}...")
                        process_page_task(i)
                status.update(label="Batch processing complete!", state="complete", expanded=False)
            st.rerun()

    # Page list
    for i, page in enumerate(st.session_state['pages']):
        with st.expander(f"{i+1}. {page['name']} - {page['status'].upper()}", expanded=(page['status'] == 'processing')):
            col_img, col_info, col_actions = st.columns([1, 2, 1])
            
            with col_img:
                st.image(page['path'], width=150)
            
            with col_info:
                st.write(f"**Status:** {page['status']}")
                if page.get('error'):
                    st.error(f"Error: {page['error']}")
                if page.get('warnings'):
                    for w in page['warnings']:
                        st.warning(w)
                
                if page['status'] == 'completed':
                    res = page['results']
                    steps = res.get('steps', {})
                    st.caption(f"OCR: {steps.get('ocr_extraction', {}).get('text_length', 0)} chars")
                    st.caption(f"Translation: {steps.get('translation', {}).get('text_length', 0)} chars")
                    st.caption(f"Diagrams: {steps.get('pdf_creation', {}).get('diagrams_translated', 0)}")
            
            with col_actions:
                if st.button("Process", key=f"proc_{i}"):
                    with st.spinner(f"Processing {page['name']}..."):
                        process_page_task(i)
                    st.rerun()
                
                if st.button("Remove", key=f"rem_{i}"):
                    st.session_state['pages'].pop(i)
                    st.rerun()

def render_results_view():
    st.header("Review & Export")
    
    completed_pages = [p for p in st.session_state['pages'] if p['status'] == 'completed']
    
    if not completed_pages:
        st.info("Process pages to see results here.")
        return
        
    # Selector
    page_names = [f"{i+1}. {p['name']}" for i, p in enumerate(st.session_state['pages']) if p['status'] == 'completed']
    selected_idx = st.selectbox("Select Page", range(len(completed_pages)), format_func=lambda i: page_names[i])
    
    page = completed_pages[selected_idx]
    stem = Path(page['path']).stem
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["Side-by-Side", "PDF View", "Edit Text"])
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.image(page['path'], caption="Original", use_container_width=True)
        with c2:
            # Check for translated image
            preview_path = os.path.join(OUTPUT_DIR, f"{stem}_translated.jpg")
            if os.path.exists(preview_path):
                st.image(preview_path, caption="Translated Preview", use_container_width=True)
            else:
                st.info("PDF Preview not available as image. Check PDF View tab.")
            
    with tab2:
        pdf_path = os.path.join(OUTPUT_DIR, f"{stem}_translated.pdf")
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                base64_pdf = f.read()
            st.download_button(
                label="Download PDF",
                data=base64_pdf,
                file_name=f"{stem}_translated.pdf",
                mime="application/pdf"
            )
            # Embed PDF
            import base64
            base64_pdf = base64.b64encode(base64_pdf).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.error("PDF file not found.")
            
    with tab3:
        # Text editing
        txt_path = os.path.join(OUTPUT_DIR, f"{stem}_translation.txt")
        current_text = ""
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f:
                current_text = f.read()
        
        new_text = st.text_area("Translation Text", value=current_text, height=400)
        if st.button("Save Changes"):
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            st.success("Saved!")
            # Ideally trigger PDF regeneration here

def main():
    st.set_page_config(page_title="Book Translator", layout="wide")
    init_state()
    
    render_sidebar()
    
    tab_process, tab_review = st.tabs(["Processing Queue", "Review Results"])
    
    with tab_process:
        render_page_list()
        
    with tab_review:
        render_results_view()

if __name__ == "__main__":
    main()
