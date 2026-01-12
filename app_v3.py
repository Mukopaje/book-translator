import os
import uuid
import requests
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
import logging
import time
import sys
from PIL import Image
import io

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
sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import BookTranslator
from api_client import get_api_client
from streamlit.components.v1 import html as st_html

OUTPUT_DIR = "output"
IMAGES_DIR = "images_to_process"

@st.cache_data(ttl=3600)
def get_thumbnail_url(project_id: int, page_id: int, token: str, base_url: str) -> str:
    """Cached function to get thumbnail URL from backend."""
    try:
        from api_client import APIClient
        api = APIClient(base_url=base_url)
        api.token = token
        url_data = api.get_download_url(project_id, page_id, file_type="original")
        return url_data.get('url') if url_data else None
    except Exception as e:
        logger.error(f"Failed to fetch thumbnail for page {page_id}: {e}")
        return None

def get_pdf_thumbnail(pdf_path: str, width: int = 200) -> Image.Image:
    """Convert first page of PDF to thumbnail image."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        page = doc[0]  # First page
        
        # Render page to pixmap
        zoom = width / page.rect.width
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        doc.close()
        return img
    except ImportError:
        logger.warning("PyMuPDF not installed - PDF thumbnails unavailable")
        return None
    except Exception as e:
        logger.debug(f"PDF thumbnail generation failed: {e}")
        return None
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_token_to_browser(token: str):
    """Save auth token to browser localStorage."""
    import streamlit.components.v1 as components
    components.html(
        f"""
        <script>
        localStorage.setItem('book_translator_token', '{token}');
        </script>
        """,
        height=0
    )

def get_token_from_browser():
    """Get auth token from browser localStorage."""
    import streamlit.components.v1 as components
    token = components.html(
        """
        <script>
        const token = localStorage.getItem('book_translator_token');
        window.parent.postMessage({type: 'streamlit:setComponentValue', value: token}, '*');
        </script>
        """,
        height=0
    )
    return token

def clear_token_from_browser():
    """Clear auth token from browser localStorage."""
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        localStorage.removeItem('book_translator_token');
        </script>
        """,
        height=0
    )

def init_state():
    """Initialize session state."""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'auth_checked' not in st.session_state:
        st.session_state.auth_checked = False
    if 'current_project' not in st.session_state:
        st.session_state.current_project = None
    if 'pages' not in st.session_state:
        st.session_state['pages'] = []
    if 'pages_loaded_from_backend' not in st.session_state:
        st.session_state.pages_loaded_from_backend = False
    if 'metadata' not in st.session_state:
        st.session_state['metadata'] = {'title': '', 'author': ''}
    if 'processing_queue' not in st.session_state:
        st.session_state['processing_queue'] = []
    if 'selected_pages' not in st.session_state:
        st.session_state['selected_pages'] = set()
    if 'reprocess_comparison' not in st.session_state:
        st.session_state['reprocess_comparison'] = None

    # NEW: Pagination state
    if 'current_page_offset' not in st.session_state:
        st.session_state.current_page_offset = 0
    if 'page_size' not in st.session_state:
        st.session_state.page_size = 20  # Show 20 pages at a time
    if 'total_pages_count' not in st.session_state:
        st.session_state.total_pages_count = 0
    if 'status_filter' not in st.session_state:
        st.session_state.status_filter = None

def render_auth_page():
    """Render login/signup page."""
    api = get_api_client()
    
    st.title("📚 Book Translator")
    st.markdown("### AI-Powered Japanese to English Translation")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to Your Account")
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Please enter both email and password")
                else:
                    try:
                        with st.spinner("Logging in..."):
                            token = api.login(email, password)
                            st.session_state.logged_in = True
                            st.session_state.current_user = {"email": email}
                            st.session_state.token = token
                            # Persist token in URL query params for page reload
                            st.query_params['token'] = token
                            st.success("✅ Logged in successfully!")
                            time.sleep(0.5)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Login failed: {str(e)}")
    
    with tab2:
        st.subheader("Create New Account")
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            full_name = st.text_input("Full Name (optional)", key="signup_name")
            password = st.text_input("Password", type="password", key="signup_password")
            password2 = st.text_input("Confirm Password", type="password", key="signup_password2")
            submit = st.form_submit_button("Sign Up", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Email and password are required")
                elif password != password2:
                    st.error("Passwords don't match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    try:
                        with st.spinner("Creating account..."):
                            api.signup(email, password, full_name)
                            # Auto-login after signup
                            token = api.login(email, password)
                            st.session_state.logged_in = True
                            st.session_state.current_user = {"email": email}
                            st.session_state.token = token
                            # Persist token in URL query params
                            st.query_params['token'] = token
                            st.success("✅ Account created! Logging you in...")
                            time.sleep(0.5)
                            st.rerun()
                    except Exception as e:
                        error_msg = str(e)
                        if "400" in error_msg:
                            st.error("❌ Email already registered")
                        else:
                            st.error(f"❌ Signup failed: {error_msg}")

def add_page(uploaded_file, role='page'):
    if not uploaded_file:
        return
    
    # Check if project selected
    if not st.session_state.current_project:
        st.error("Please select or create a project first")
        return
    
    # Save locally first
    uid = uuid.uuid4().hex[:8]
    filename = f"{uid}_{uploaded_file.name}"
    path = os.path.join(IMAGES_DIR, filename)
    with open(path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    
    # Get existing pages to determine next page number
    api = get_api_client()
    project_id = st.session_state.current_project['id']
    existing_numbers = set()
    try:
        # We use the session state pages if available to avoid API spam, 
        # but for accuracy with multiple uploads, we should be careful.
        # Let's trust the backend + local session state combination.
        # Actually, let's just look at what we have in session state 'pages' 
        # because that includes what we just added in this loop (if we update it correctly).
        
        # Wait, st.session_state['pages'] is updated at the end of this function.
        # So if we loop, we can check it.
        existing_numbers = {p.get('page_number') for p in st.session_state['pages'] if p.get('page_number')}
    except:
        pass

    # Extract page number from filename
    import re
    page_number = None
    
    # Robust patterns - strictly looking for page indicators or end-of-string numbers
    patterns = [
        r'page\s*[-_]?\s*(\d+)',    # page1, page-1, page_1
        r'p\s*[-_]?\s*(\d+)',       # p1, p-1, p_1
        r'[_-](\d+)\.[a-zA-Z0-9]+$', # _1.jpg, -1.jpg (at end of file)
        r'^(\d+)\.[a-zA-Z0-9]+$'     # 1.jpg (start of file)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, uploaded_file.name, re.IGNORECASE)
        if match:
            try:
                extracted_num = int(match.group(1))
                # Only use it if it's not already taken
                if extracted_num not in existing_numbers:
                    page_number = extracted_num
                    break
            except ValueError:
                continue
    
    # If no valid page number found or collision, use next available
    if page_number is None:
        max_page = max(existing_numbers, default=0)
        page_number = max_page + 1
    
    logger.info(f"Assigning page number {page_number} to {uploaded_file.name}")
    
    # Upload to backend
    try:
        api = get_api_client()
        project_id = st.session_state.current_project['id']
        
        # Upload file to backend
        with open(path, 'rb') as f:
            page_data = api.upload_page(
                project_id=project_id,
                page_number=page_number,
                file=f,
                filename=uploaded_file.name
            )
        
        # Add to local session with backend page_id
        page_info = {
            'id': uid,
            'page_id': page_data['id'],  # Backend page ID
            'path': path,
            'name': uploaded_file.name,
            'role': role,
            'status': 'uploaded',
            'page_number': page_number,
            'results': None,
            'error': None
        }
        st.session_state['pages'].append(page_info)
        return page_info
    except requests.HTTPError as e:
        error_detail = "Unknown error"
        if e.response is not None:
            try:
                error_data = e.response.json()
                error_detail = error_data.get('detail', str(e))
            except:
                error_detail = e.response.text or str(e)
        
        st.error(f"Failed to upload page: {error_detail}")
        logger.error(f"Upload failed: {error_detail}")
        
        # Still add locally even if backend fails
        page_info = {
            'id': uid,
            'page_id': None,
            'path': path,
            'name': uploaded_file.name,
            'role': role,
            'status': 'pending',
            'page_number': page_number,
            'results': None,
            'error': str(error_detail)
        }
        st.session_state['pages'].append(page_info)
        return page_info
    except Exception as e:
        st.error(f"Failed to upload page: {e}")
        # Still add locally even if backend fails
        page_info = {
            'id': uid,
            'page_id': None,
            'path': path,
            'name': uploaded_file.name,
            'role': role,
            'status': 'pending',
            'page_number': page_number,
            'results': None,
            'error': str(e)
        }
        st.session_state['pages'].append(page_info)
        return page_info

def download_page_image(page):
    """Download page image from backend to local storage if needed."""
    # If we already have a local path, use it
    if page.get('path') and os.path.exists(page['path']):
        return page['path']
    
    # Try to get the file from backend storage
    try:
        api = get_api_client()
        project_id = st.session_state.current_project['id']
        page_id = page.get('page_id') or page.get('id')
        
        if not page_id:
            logger.error("No page_id found for download")
            return None
        
        logger.info(f"Getting download URL for page_id={page_id}, project_id={project_id}")
        
        # Get download URL
        result = api.get_download_url(project_id, page_id, file_type='original')
        logger.info(f"Download result type: {type(result)}, value: {result}")
        
        if isinstance(result, str):
            # If result is a string, treat it as the URL directly
            download_url = result
        elif isinstance(result, dict):
            download_url = result.get('url')
        else:
            logger.error(f"Unexpected result type: {type(result)}")
            return None
        
        if not download_url:
            logger.error("No download URL returned")
            return None
        
        logger.info(f"Download URL: {download_url}")
        
        # Handle local file:// URLs (when backend uses local storage)
        if download_url.startswith('file://'):
            # Extract local path from file:// URL
            import urllib.parse
            local_path = urllib.parse.unquote(download_url.replace('file://', ''))
            logger.info(f"Local file path: {local_path}")
            
            if os.path.exists(local_path):
                # Copy to images_to_process for consistency
                filename = page.get('name') or f"page_{page.get('page_number')}.jpg"
                uid = uuid.uuid4().hex[:8]
                dest_path = os.path.join(IMAGES_DIR, f"{uid}_{filename}")
                import shutil
                shutil.copy2(local_path, dest_path)
                page['path'] = dest_path
                logger.info(f"Copied to: {dest_path}")
                return dest_path
            else:
                logger.error(f"Local file not found: {local_path}")
                return None
        else:
            # Download from HTTP URL (GCS signed URL)
            import requests
            response = requests.get(download_url)
            response.raise_for_status()
            
            # Save locally
            filename = page.get('name') or f"page_{page.get('page_number')}.jpg"
            uid = uuid.uuid4().hex[:8]
            local_filename = f"{uid}_{filename}"
            local_path = os.path.join(IMAGES_DIR, local_filename)
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            # Update page with local path
            page['path'] = local_path
            logger.info(f"Downloaded to: {local_path}")
            return local_path
        
    except Exception as e:
        logger.error(f"Failed to download page image: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def process_page_task(page_idx):
    page = st.session_state['pages'][page_idx]
    page['status'] = 'processing'
    
    # Get or download the local file
    page_path = download_page_image(page)
    if not page_path or not os.path.exists(page_path):
        page['status'] = 'failed'
        page['error'] = "Image file not available locally for processing"
        return
    
    try:
        # Get book context from current project or metadata
        book_context = ''
        if st.session_state.current_project:
            book_context = st.session_state.current_project.get('book_context', '')
        else:
            book_context = st.session_state['metadata'].get('context', '')
            if st.session_state['metadata'].get('title'):
                book_context = f"{st.session_state['metadata']['title']}. {book_context}"
            
        translator = BookTranslator(page_path, OUTPUT_DIR, book_context=book_context)
        results = translator.process_page(verbose=True)
        
        if results.get('success'):
            page['status'] = 'completed'
            page['results'] = results
            
            if 'warnings' in results:
                page['warnings'] = results['warnings']
                
            stem = Path(page_path).stem
            pdf_path = os.path.join(OUTPUT_DIR, f"{stem}_translated.pdf")
            
            # Save results to backend
            if st.session_state.current_project:
                try:
                    api = get_api_client()
                    # Get OCR and translation text from results
                    ocr_text = results.get('steps', {}).get('ocr_extraction', {}).get('preview', '')
                    trans_text = results.get('steps', {}).get('translation', {}).get('preview', '')
                    
                    # Use 'id' for backend pages or 'page_id' for local pages
                    backend_page_id = page.get('id') or page.get('page_id')
                    
                    if backend_page_id:
                        # Update page in backend
                        logger.info(f"Updating backend page {backend_page_id}: status=completed, ocr_len={len(ocr_text)}, trans_len={len(trans_text)}")
                        updated_page = api.update_page(
                            project_id=st.session_state.current_project['id'],
                            page_id=backend_page_id,
                            status='COMPLETED',
                            ocr_text=ocr_text,
                            translated_text=trans_text,
                            output_pdf_path=pdf_path
                        )
                        logger.info(f"Backend responded: {updated_page.get('status')}")
                    
                        # Update project completed count
                        current_completed = st.session_state.current_project.get('completed_pages', 0)
                        api.update_project(
                            project_id=st.session_state.current_project['id'],
                            completed_pages=current_completed + 1
                        )
                except Exception as e:
                    logger.warning(f"Failed to save to backend: {e}")
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
    api = get_api_client()
    
    with st.sidebar:
        st.title("📚 Book Translator")
        st.markdown(f"**User:** {st.session_state.current_user['email']}")
        
        if st.button("🚪 Logout"):
            st.query_params.clear()
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.current_project = None
            st.session_state.token = None
            st.session_state.auth_checked = False
            st.session_state.pages_loaded_from_backend = False
            api.token = None
            st.rerun()
        
        st.markdown("---")
        st.header("Projects")
        
        # Load projects
        try:
            projects = api.list_projects()

            if projects:
                project_options = {p["id"]: f"{p['title']}" for p in projects}

                # Auto-select first project if none selected (helps after page reload)
                if not st.session_state.current_project and projects:
                    first_project = projects[0]
                    st.session_state.current_project = first_project
                    st.session_state['metadata']['title'] = first_project['title']
                    st.session_state['metadata']['author'] = first_project.get('author', '')
                    st.session_state['metadata']['context'] = first_project.get('book_context', '')
                    st.session_state['pages'] = []
                    st.session_state.pages_loaded_from_backend = False
                    st.session_state.current_page_offset = 0
                    st.session_state.status_filter = None
                    st.session_state.total_pages_count = 0
                    logger.info(f"Auto-selected first project: {first_project['title']}")

                # Current project selector
                current_id = st.session_state.current_project['id'] if st.session_state.current_project else None
                selected_id = st.selectbox(
                    "Select Project",
                    options=list(project_options.keys()),
                    format_func=lambda x: project_options[x],
                    index=list(project_options.keys()).index(current_id) if current_id in project_options else 0
                )
                
                if st.button("Load Project") or (st.session_state.current_project and st.session_state.current_project['id'] != selected_id):
                    try:
                        project = api.get_project(selected_id)
                        st.session_state.current_project = project
                        st.session_state['metadata']['title'] = project['title']
                        st.session_state['metadata']['author'] = project.get('author', '')
                        st.session_state['metadata']['context'] = project.get('book_context', '')
                        # Clear pages and reload from backend
                        st.session_state['pages'] = []
                        st.session_state.pages_loaded_from_backend = False
                        # IMPORTANT: Reset pagination when switching projects
                        st.session_state.current_page_offset = 0
                        st.session_state.status_filter = None
                        st.session_state.total_pages_count = 0
                        st.success(f"✅ Loaded: {project['title']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to load project: {e}")
            else:
                st.info("No projects yet. Create one below!")
        
        except Exception as e:
            st.error(f"Error loading projects: {e}")
        
        st.markdown("---")
        
        # Create new project
        with st.expander("➕ Create New Project"):
            with st.form("new_project"):
                title = st.text_input("Book Title")
                author = st.text_input("Author")
                context = st.text_area("Book Context",
                    help="Describe the book's subject matter for better translations")

                # Language selection
                st.markdown("**Language Settings**")
                col1, col2 = st.columns(2)

                # Define language options
                source_languages = {
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
                    'it': 'Italian (Italiano)',
                    'ru': 'Russian (Русский)',
                    'ar': 'Arabic (العربية)',
                    'th': 'Thai (ไทย)',
                    'vi': 'Vietnamese (Tiếng Việt)',
                    'tr': 'Turkish (Türkçe)',
                    'hi': 'Hindi (हिन्दी)',
                }

                target_languages = {
                    'en': 'English',
                    'es': 'Spanish (Español)',
                    'fr': 'French (Français)',
                    'de': 'German (Deutsch)',
                    'pt': 'Portuguese (Português)',
                    'it': 'Italian (Italiano)',
                    'ja': 'Japanese (日本語)',
                    'zh': 'Chinese Simplified (简体中文)',
                    'zh-TW': 'Chinese Traditional (繁體中文)',
                    'ko': 'Korean (한국어)',
                    'ru': 'Russian (Русский)',
                    'ar': 'Arabic (العربية)',
                    'th': 'Thai (ไทย)',
                    'vi': 'Vietnamese (Tiếng Việt)',
                    'tr': 'Turkish (Türkçe)',
                    'hi': 'Hindi (हिन्दी)',
                }

                with col1:
                    source_lang = st.selectbox(
                        "Source Language",
                        options=list(source_languages.keys()),
                        format_func=lambda x: source_languages[x],
                        index=0,  # Default to 'auto'
                        help="Select 'Auto-Detect' to automatically identify the source language"
                    )

                with col2:
                    target_lang = st.selectbox(
                        "Target Language",
                        options=list(target_languages.keys()),
                        format_func=lambda x: target_languages[x],
                        index=0,  # Default to 'en'
                        help="Language to translate into"
                    )

                if st.form_submit_button("Create Project"):
                    if not title:
                        st.error("Title is required")
                    else:
                        try:
                            project = api.create_project(title, author, context, source_lang, target_lang)
                            st.session_state.current_project = project
                            st.session_state['metadata']['title'] = title
                            st.session_state['metadata']['author'] = author
                            st.session_state['metadata']['context'] = context
                            st.session_state['pages'] = []
                            st.session_state.pages_loaded_from_backend = False
                            st.success(f"✅ Created: {title} ({source_languages[source_lang]} → {target_languages[target_lang]})")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to create project: {e}")
        
        # Current project info
        if st.session_state.current_project:
            st.markdown("---")
            st.subheader("Current Project")
            proj = st.session_state.current_project
            st.write(f"**Title:** {proj['title']}")
            st.write(f"**Author:** {proj.get('author', 'N/A')}")
            st.write(f"**Progress:** {proj['completed_pages']}/{proj['total_pages']} pages")

            # Display language information
            source_lang = proj.get('source_language', 'auto')
            target_lang = proj.get('target_language', 'en')
            detected_lang = proj.get('source_language_detected')
            confidence = proj.get('source_language_confidence')

            if source_lang == 'auto' and detected_lang:
                confidence_pct = int(confidence * 100) if confidence else 0
                st.write(f"**Languages:** {detected_lang.upper()} (detected, {confidence_pct}% confidence) → {target_lang.upper()}")
            else:
                st.write(f"**Languages:** {source_lang.upper()} → {target_lang.upper()}")
            
            # Download complete book button
            if proj.get('completed_pages', 0) > 0:
                if st.button("📚 Download Complete Book", type="primary", use_container_width=True):
                    try:
                        with st.spinner("Merging PDFs..."):
                            api = get_api_client()
                            pdf_data = api.download_complete_book(proj['id'])
                            
                            # Offer download
                            st.download_button(
                                label="📥 Download Merged PDF",
                                data=pdf_data,
                                file_name=f"{proj['title']}_complete.pdf",
                                mime="application/pdf",
                                type="primary"
                            )
                            st.success(f"✅ Book ready! ({len(pdf_data) // 1024} KB)")
                    except Exception as e:
                        st.error(f"Failed to merge book: {e}")

        
        st.markdown("---")
        st.header("Upload")
        uploaded = st.file_uploader("Add Pages", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
        if uploaded:
            for f in uploaded:
                # Check if page already exists (by name for local pages, or filename match for backend pages)
                page_name = f.name
                already_exists = any(
                    p.get('name') == page_name or 
                    (p.get('original_image_path', '').endswith(page_name))
                    for p in st.session_state['pages']
                )
                if not already_exists:
                    add_page(f)
            st.success(f"Added {len(uploaded)} pages")
            
        st.markdown("---")
        if st.button("Clear All Pages"):
            st.session_state['pages'] = []
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

def render_page_list():
    if not st.session_state.current_project:
        st.warning("⚠️ Please select or create a project first")
        return
    
    # Load pages from backend with pagination
    if not st.session_state.pages_loaded_from_backend:
        try:
            api = get_api_client()
            project_id = st.session_state.current_project['id']

            # Use pagination parameters from session state
            offset = st.session_state.current_page_offset
            page_size = st.session_state.page_size
            status_filter = st.session_state.status_filter

            # Fetch paginated pages from backend
            result = api.list_pages(
                project_id,
                skip=offset,
                limit=page_size,
                status_filter=status_filter
            )

            backend_pages = result['pages']
            total_count = result['total']

            logger.info(f"Loaded {len(backend_pages)} pages from backend (total: {total_count}, offset: {offset})")
            # Log each page status for debugging
            for p in backend_pages:
                logger.info(f"  Page {p.get('page_number')}: status={p.get('status')}, id={p.get('id')}")

            st.session_state['pages'] = backend_pages
            st.session_state.total_pages_count = total_count
            st.session_state.pages_loaded_from_backend = True
        except Exception as e:
            logger.warning(f"Failed to load pages from backend: {e}")
            # Handle expired/invalid token with explicit re-auth action
            if "401" in str(e):
                st.warning("Session expired. Please re-authenticate to continue.")
                col_a, col_b = st.columns([1, 3])
                with col_a:
                    if st.button("🔐 Re-authenticate", type="primary"):
                        # Clear token and auth state, then rerun to show login
                        try:
                            api = get_api_client()
                            api.token = None
                        except Exception:
                            pass
                        st.query_params.clear()
                        st.session_state.logged_in = False
                        st.session_state.current_user = None
                        st.session_state.current_project = None
                        st.session_state.token = None
                        st.session_state.auth_checked = False
                        st.session_state.pages_loaded_from_backend = False
                        st.session_state['pages'] = []
                        st.rerun()
                with col_b:
                    st.info("You will be redirected to the login page after re-auth.")
    
    # Header with total count and pagination info
    total = st.session_state.total_pages_count
    offset = st.session_state.current_page_offset
    page_size = st.session_state.page_size
    current_page_num = (offset // page_size) + 1
    total_page_groups = (total + page_size - 1) // page_size if total > 0 else 1

    st.header(f"Pages ({total} total)")

    # Show filter status if active
    if st.session_state.status_filter:
        st.caption(f"🔍 Filtered by: **{st.session_state.status_filter}** | Showing page {current_page_num} of {total_page_groups} ({page_size} pages per view)")
    else:
        st.caption(f"Showing page {current_page_num} of {total_page_groups} ({page_size} pages per view)")
    
    if not st.session_state['pages']:
        if st.session_state.status_filter:
            st.info(f"No pages found with status '{st.session_state.status_filter}'. Try changing the filter or upload pages to begin.")
        else:
            st.info("Upload pages to begin.")
        return
    
    # Check if any pages are processing
    processing_pages = [p for p in st.session_state['pages'] 
                       if p.get('status') in ['queued', 'processing', 'QUEUED', 'PROCESSING']]
    
    if processing_pages:
        st.info(f"⏳ {len(processing_pages)} page(s) in progress. Auto-refreshing every 5 seconds...")
        time.sleep(5)
        st.session_state.pages_loaded_from_backend = False
        st.rerun()
    else:
        # Also check if we have any pages that are 'uploaded' but we just queued them
        # This handles the case where the user clicked queue, but the backend hasn't updated yet
        # or the local state is stale.
        pass

    # NEW: Pagination controls
    st.markdown("---")

    # First row: Page size and filter
    size_col, filter_col = st.columns([1, 2])

    with size_col:
        page_size_options = [20, 50, 100, 500]
        current_page_size = st.session_state.page_size
        selected_page_size = st.selectbox(
            "Pages per view",
            options=page_size_options,
            index=page_size_options.index(current_page_size) if current_page_size in page_size_options else 0,
            key="page_size_select",
            help="Number of pages to display at once (max 500 for bulk operations)"
        )

        if selected_page_size != current_page_size:
            st.session_state.page_size = selected_page_size
            st.session_state.current_page_offset = 0  # Reset to first page
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

    with filter_col:
        # Status filter with all possible statuses
        status_options = ["All", "UPLOADED", "QUEUED", "PROCESSING", "COMPLETED", "FAILED", "NEEDS_REVIEW"]
        current_filter = st.session_state.status_filter or "All"
        selected_filter = st.selectbox(
            "Filter by status",
            options=status_options,
            index=status_options.index(current_filter) if current_filter in status_options else 0,
            key="status_filter_select",
            help="Filter pages by their processing status"
        )

        if selected_filter != current_filter:
            st.session_state.status_filter = None if selected_filter == "All" else selected_filter
            st.session_state.current_page_offset = 0  # Reset to first page when filtering
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

    # Second row: Navigation buttons
    pagination_col1, pagination_col2, pagination_col3, pagination_col4, pagination_col5 = st.columns([1, 1, 1.5, 1, 1])

    with pagination_col1:
        if st.button("⏮️ First", disabled=offset == 0, key="first_page"):
            st.session_state.current_page_offset = 0
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

    with pagination_col2:
        if st.button("◀️ Prev", disabled=offset == 0, key="prev_page"):
            st.session_state.current_page_offset = max(0, offset - page_size)
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

    with pagination_col3:
        st.markdown(f"**Page {current_page_num} / {total_page_groups}**")

    with pagination_col4:
        if st.button("Next ▶️", disabled=offset + page_size >= total, key="next_page"):
            st.session_state.current_page_offset = min(total - page_size, offset + page_size)
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

    with pagination_col5:
        if st.button("Last ⏭️", disabled=offset + page_size >= total, key="last_page"):
            last_page_offset = ((total - 1) // page_size) * page_size
            st.session_state.current_page_offset = last_page_offset
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

    st.markdown("---")

    # Batch actions
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1.5, 1.5])
    with col1:
        # Select all on current page
        if st.button(f"☑️ Select Page ({len(st.session_state['pages'])})", key="select_all_page"):
            for i in range(len(st.session_state['pages'])):
                page = st.session_state['pages'][i]
                if page.get('status') in ['completed', 'failed', 'COMPLETED', 'FAILED', 'NEEDS_REVIEW']:
                    st.session_state['selected_pages'].add(i)
            st.rerun()

    with col2:
        # Queue All with status selection
        with st.popover("🚀 Queue All", use_container_width=True):
            st.markdown("**Select statuses to queue:**")

            # Default to UPLOADED and FAILED
            queue_uploaded = st.checkbox("📤 UPLOADED", value=True, key="queue_uploaded")
            queue_failed = st.checkbox("❌ FAILED", value=True, key="queue_failed")
            queue_needs_review = st.checkbox("⚠️ NEEDS_REVIEW", value=False, key="queue_needs_review")

            st.markdown("---")

            # Count pages matching selected statuses
            statuses_to_queue = []
            if queue_uploaded:
                statuses_to_queue.extend(['uploaded', 'UPLOADED'])
            if queue_failed:
                statuses_to_queue.extend(['failed', 'FAILED'])
            if queue_needs_review:
                statuses_to_queue.extend(['needs_review', 'NEEDS_REVIEW'])

            # Helper function to get backend ID
            def _backend_id(p):
                val = p.get('id')
                if isinstance(val, int):
                    return val
                try:
                    return int(val)
                except Exception:
                    pass
                alt = p.get('page_id')
                if isinstance(alt, int):
                    return alt
                try:
                    return int(alt)
                except Exception:
                    return None

            candidate_pages = [p for p in st.session_state['pages']
                               if p.get('status') in statuses_to_queue]
            pending_ids = []
            for p in candidate_pages:
                bid = _backend_id(p)
                if bid is not None:
                    pending_ids.append(bid)
            # De-duplicate
            pending_ids = list(dict.fromkeys(pending_ids))

            st.caption(f"Will queue {len(pending_ids)} page(s) from current view")

            if st.button("✅ Queue Selected Statuses", type="primary", use_container_width=True):
                if not statuses_to_queue:
                    st.warning("Please select at least one status")
                elif pending_ids:
                    try:
                        api = get_api_client()
                        result = api.queue_batch_processing(pending_ids)
                        st.success(f"✅ Queued {len(pending_ids)} pages!")
                        st.info(f"Task ID: {result['task_id']}")
                        time.sleep(1)
                        st.session_state.pages_loaded_from_backend = False
                        st.rerun()
                    except Exception as e:
                        # Try to show more server detail when available
                        try:
                            st.error(f"Failed to queue: {e.response.text}")
                        except Exception:
                            st.error(f"Failed to queue: {e}")
                else:
                    st.warning("No pages match the selected statuses")

    with col3:
        # Queue All Project - queues across entire project, not just current view
        with st.popover("🚀🌐 Queue Project", use_container_width=True):
            st.markdown("**Queue across entire project:**")
            st.caption("This will queue pages from ALL pages in the project, not just the current view")

            # Default to UPLOADED and FAILED
            queue_proj_uploaded = st.checkbox("📤 UPLOADED", value=True, key="queue_proj_uploaded")
            queue_proj_failed = st.checkbox("❌ FAILED", value=True, key="queue_proj_failed")
            queue_proj_needs_review = st.checkbox("⚠️ NEEDS_REVIEW", value=False, key="queue_proj_needs_review")

            st.markdown("---")

            # Build status list
            project_statuses = []
            if queue_proj_uploaded:
                project_statuses.append('UPLOADED')
            if queue_proj_failed:
                project_statuses.append('FAILED')
            if queue_proj_needs_review:
                project_statuses.append('NEEDS_REVIEW')

            st.caption(f"Will queue ALL pages with selected statuses in project (up to 500)")

            if st.button("✅ Queue Entire Project", type="primary", use_container_width=True):
                if not project_statuses:
                    st.warning("Please select at least one status")
                else:
                    try:
                        api = get_api_client()
                        project_id = st.session_state.current_project['id']
                        result = api.queue_by_status(project_id, project_statuses)

                        if result.get('count', 0) > 0:
                            st.success(f"✅ Queued {result['count']} pages across entire project!")
                            st.info(f"Task ID: {result['task_id']}")
                            time.sleep(1)
                            st.session_state.pages_loaded_from_backend = False
                            st.rerun()
                        else:
                            st.info(result.get('message', 'No pages found matching the selected statuses'))
                    except Exception as e:
                        try:
                            st.error(f"Failed to queue: {e.response.text}")
                        except Exception:
                            st.error(f"Failed to queue: {e}")

    with col4:
        if st.button("🔄 Refresh Status", key="refresh_status"):
            st.session_state.pages_loaded_from_backend = False
            st.rerun()

    with col5:
        # Reprocess selected pages button - calculate count right before rendering
        # to ensure we have the latest session state value
        if 'selected_pages' not in st.session_state:
            st.session_state['selected_pages'] = set()
        
        selected_count = len(st.session_state['selected_pages'])
        button_label = f"🔁 Reprocess Selected ({selected_count})" if selected_count > 0 else "🔁 Reprocess Selected"
        button_disabled = selected_count == 0
        
        if st.button(button_label, disabled=button_disabled, key="reprocess_btn"):
            api = get_api_client()
            try:
                selected_indices = sorted(list(st.session_state['selected_pages']))
                page_ids = []
                for idx in selected_indices:
                    page = st.session_state['pages'][idx]
                    pid = page.get('id')
                    if isinstance(pid, int):
                        page_ids.append(pid)
                
                if page_ids:
                    # Mark pages as queued for reprocessing
                    for idx in selected_indices:
                        st.session_state['pages'][idx]['status'] = 'queued'
                        st.session_state['pages'][idx]['reprocessing'] = True
                    
                    result = api.queue_batch_processing(page_ids)
                    st.success(f"✅ Reprocessing {len(page_ids)} page(s)!")
                    st.session_state['selected_pages'] = set()
                    time.sleep(1)
                    st.session_state.pages_loaded_from_backend = False
                    st.rerun()
                else:
                    st.warning("Selected pages don't have backend IDs")
            except Exception as e:
                st.error(f"Failed to reprocess: {e}")

    # Page list
    for i, page in enumerate(st.session_state['pages']):
        # Handle both backend pages and local pages
        page_name = page.get('name') or f"Page {page.get('page_number', i+1)}"
        page_path = page.get('path') or page.get('original_image_path', '')
        page_status = page.get('status', 'pending')
        
        # Determine status emoji and color
        status_map = {
            'uploaded': ('📤', 'blue'),
            'queued': ('⏰', 'orange'),
            'pending': ('⏳', 'orange'),
            'processing': ('⚙️', 'orange'),
            'completed': ('✅', 'green'),
            'failed': ('❌', 'red'),
            'UPLOADED': ('📤', 'blue'),
            'QUEUED': ('⏰', 'orange'),
            'PENDING': ('⏳', 'orange'),
            'PROCESSING': ('⚙️', 'orange'),
            'COMPLETED': ('✅', 'green'),
            'FAILED': ('❌', 'red')
        }
        emoji, color = status_map.get(page_status, ('❓', 'gray'))
        
        # Add checkbox for selection (allow selecting completed/failed pages for reprocessing)
        col_check, col_thumb, col_expander = st.columns([0.05, 0.15, 0.8])
        with col_check:
            if page_status in ['completed', 'failed', 'COMPLETED', 'FAILED']:
                # Ensure selected_pages exists
                if 'selected_pages' not in st.session_state:
                    st.session_state['selected_pages'] = set()
                
                is_selected = i in st.session_state['selected_pages']
                checkbox_val = st.checkbox("Select", value=is_selected, key=f"select_{i}", label_visibility="collapsed")
                
                # Update selection set based on checkbox value
                if checkbox_val and i not in st.session_state['selected_pages']:
                    st.session_state['selected_pages'].add(i)
                    st.rerun()  # Force update to show new count
                elif not checkbox_val and i in st.session_state['selected_pages']:
                    st.session_state['selected_pages'].discard(i)
                    st.rerun()  # Force update to show new count
        
        with col_thumb:
            # Show mini thumbnail in list
            shown = False
            if page_path and os.path.exists(page_path):
                # Check if it's a PDF
                if page_path.lower().endswith('.pdf'):
                    pdf_thumb = get_pdf_thumbnail(page_path, width=80)
                    if pdf_thumb:
                        st.image(pdf_thumb, width=80)
                        shown = True
                else:
                    # Regular image file
                    st.image(page_path, width=80)
                    shown = True
            
            if not shown:
                # Try to get from backend using cached function
                project_id = st.session_state.get('current_project', {}).get('id')
                page_id = page.get('id')
                token = st.session_state.get('token')
                
                if project_id and page_id and token:
                    try:
                        api = get_api_client()
                        thumb_url = get_thumbnail_url(int(project_id), int(page_id), token, api.base_url)
                        if thumb_url:
                            st.image(thumb_url, width=80)
                            shown = True
                    except Exception as e:
                        logger.debug(f"Thumbnail fetch error for page {page_id}: {e}")
                
                if not shown:
                    st.markdown(f"**P{i+1}**")
        
        with col_expander:
            with st.expander(f"{emoji} {i+1}. {page_name} - {page_status.upper()}", 
                            expanded=(page_status == 'processing')):
                col_img, col_info, col_actions = st.columns([1, 2, 1])
                
                with col_img:
                    # Try to display thumbnail - check multiple sources
                    # IMPORTANT: Shows ORIGINAL uploaded file, not processed output
                    shown = False
                    
                    # 1. Try local original image/PDF path
                    if page_path and os.path.exists(page_path):
                        if page_path.lower().endswith('.pdf'):
                            # Convert PDF first page to thumbnail
                            pdf_thumb = get_pdf_thumbnail(page_path, width=200)
                            if pdf_thumb:
                                st.image(pdf_thumb, width=200, caption=f"Page {page.get('page_number', i+1)} (Original)")
                                shown = True
                            else:
                                st.info("PDF preview requires PyMuPDF: `pip install pymupdf`")
                                shown = True
                        else:
                            # Regular image file
                            st.image(page_path, width=200, caption=f"Page {page.get('page_number', i+1)} (Original)")
                            shown = True
                    
                    # 2. Try to fetch from backend if we have page ID
                    if not shown:
                        project_id = st.session_state.get('current_project', {}).get('id')
                        page_id = page.get('id')
                        token = st.session_state.get('token')
                        
                        if project_id and page_id and token:
                            try:
                                api = get_api_client()
                                thumb_url = get_thumbnail_url(int(project_id), int(page_id), token, api.base_url)
                                if thumb_url:
                                    st.image(thumb_url, width=200, caption=f"Page {page.get('page_number', i+1)} (Original)")
                                    shown = True
                            except Exception as e:
                                logger.debug(f"Thumbnail error for page {page_id}: {e}")
                    
                    # 3. Show placeholder if nothing worked
                    if not shown:
                        st.markdown(f"**📄 Page {page.get('page_number', i+1)}**")
                        st.caption("Original preview unavailable")
                
                with col_info:
                    st.write(f"**Page #:** {page.get('page_number', i+1)}")
                    st.write(f"**Status:** :{color}[{page.get('status', 'pending')}]")
                    
                    if page.get('error'):
                        st.error(f"Error: {page['error']}")
                    if page.get('warnings'):
                        for w in page['warnings']:
                            st.warning(w)
                    
                    # Show quality score for completed/needs_review pages
                    if page.get('quality_score') is not None:
                        score = page['quality_score']
                        level = page.get('quality_level', 'Unknown')

                        # Color code the quality level
                        if score >= 90:
                            quality_color = "green"
                        elif score >= 70:
                            quality_color = "blue"
                        elif score >= 50:
                            quality_color = "orange"
                        else:
                            quality_color = "red"

                        st.write(f"**Quality:** :{quality_color}[{level} ({score}/100)]")

                        # Show quality issues if present
                        if page.get('quality_issues'):
                            import json
                            try:
                                issues = json.loads(page['quality_issues'])
                                if issues:
                                    with st.expander(f"⚠️ {len(issues)} Quality Issues"):
                                        for issue in issues[:3]:  # Show first 3
                                            st.caption(f"• [{issue['severity']}] {issue['message']}")
                                        if len(issues) > 3:
                                            st.caption(f"... and {len(issues) - 3} more")
                            except:
                                pass

                    # Show processing stats for completed pages
                    if page.get('status') == 'completed':
                        if page.get('results'):
                            res = page['results']
                            steps = res.get('steps', {})
                            st.caption(f"📝 OCR: {steps.get('ocr_extraction', {}).get('text_length', 0)} chars")
                            st.caption(f"🌐 Translation: {steps.get('translation', {}).get('text_length', 0)} chars")
                            st.caption(f"📊 Diagrams: {steps.get('pdf_creation', {}).get('diagrams_translated', 0)}")
                        elif page.get('ocr_text'):
                            st.caption(f"📝 OCR: {len(page.get('ocr_text', ''))} chars")
                            st.caption(f"🌐 Translation: {len(page.get('translated_text', ''))} chars")
                
                with col_actions:
                    # "View PDF" button for completed pages (gets a URL from API)
                    if page_status.upper() == 'COMPLETED':
                        project_id = st.session_state.current_project.get('id')
                        page_id = page.get('id')  # Backend page ID is 'id'

                        if project_id and page_id:
                            try:
                                api = get_api_client()
                                url_data = api.get_download_url(project_id, page_id, file_type="pdf")
                                pdf_url = url_data.get('url') if isinstance(url_data, dict) else None

                                if pdf_url:
                                    st.link_button("View PDF", url=pdf_url)

                            except Exception as e:
                                logger.warning(f"Could not retrieve PDF URL for page {page_id}: {e}")

                    # "Download PDF" button (local file fallback)
                    if page_status.upper() == 'COMPLETED' and page.get('output_pdf_path'):
                        pdf_path = page.get('output_pdf_path')
                        if os.path.exists(pdf_path):
                            with open(pdf_path, 'rb') as pdf_file:
                                st.download_button(
                                    label="📥 Download PDF",
                                    data=pdf_file,
                                    file_name=f"page_{page.get('page_number', i+1)}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_{i}"
                                )
                        else:
                            st.caption("PDF not on local disk.")

                    # Action buttons
                    if page_status.upper() in ['UPLOADED', 'FAILED']:
                        if st.button("🚀 Queue", key=f"queue_{i}"):
                            try:
                                api = get_api_client()
                                # Resolve backend page ID safely
                                pid = page.get('id')
                                if not isinstance(pid, int):
                                    try:
                                        pid = int(pid)
                                    except Exception:
                                        pid = page.get('page_id')
                                        if not isinstance(pid, int):
                                            pid = int(pid) if pid is not None else None
                                if pid is None:
                                    st.warning("Cannot queue local-only page; upload succeeded?")
                                else:
                                    result = api.queue_page_processing(pid)
                                    st.success(f"Queued! Task: {result['task_id']}")
                                    time.sleep(1)
                                    st.session_state.pages_loaded_from_backend = False
                                    st.rerun()
                            except Exception as e:
                                try:
                                    st.error(f"Failed: {e.response.text}")
                                except Exception:
                                    st.error(f"Failed: {e}")

                    # NEW: Replace Image button for failed or low quality pages
                    show_replace = (
                        page_status.upper() in ['FAILED', 'NEEDS_REVIEW'] or
                        (page.get('quality_score') is not None and page['quality_score'] < 70)
                    )

                    if show_replace:
                        replace_file = st.file_uploader(
                            f"🔄 Replace Image",
                            type=['jpg', 'jpeg', 'png'],
                            key=f"replace_{i}",
                            label_visibility="collapsed",
                            help="Upload a better quality image to replace this page"
                        )

                        if replace_file:
                            try:
                                api = get_api_client()
                                project_id = st.session_state.current_project['id']
                                page_id = page.get('id')

                                if page_id:
                                    with st.spinner("Replacing image..."):
                                        updated_page = api.replace_page_image(
                                            project_id,
                                            page_id,
                                            replace_file,
                                            replace_file.name
                                        )
                                    st.success("✅ Image replaced! Page reset to 'UPLOADED' status.")
                                    time.sleep(1)
                                    st.session_state.pages_loaded_from_backend = False
                                    st.rerun()
                                else:
                                    st.error("Cannot replace local-only page")
                            except Exception as e:
                                st.error(f"Failed to replace: {e}")

                    if st.button("Remove", key=f"rem_{i}"):
                        st.session_state['pages'].pop(i)
                        st.rerun()

def render_results_view():
    st.header("Review & Export")
    
    completed_pages = [p for p in st.session_state['pages'] if p.get('status') == 'completed']
    
    if not completed_pages:
        st.info("Process pages to see results here.")
        return
        
    # Selector
    page_names = []
    for i, p in enumerate(st.session_state['pages']):
        if p.get('status') == 'completed':
            name = p.get('name') or f"Page {p.get('page_number', i+1)}"
            page_names.append(f"{i+1}. {name}")
    
    selected_idx = st.selectbox("Select Page", range(len(completed_pages)), format_func=lambda i: page_names[i])
    
    page = completed_pages[selected_idx]
    page_path = page.get('path') or page.get('original_image_path', '')
    stem = Path(page_path).stem if page_path else f"page_{page.get('page_number', selected_idx+1)}"
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["Side-by-Side", "PDF View", "Edit Text", "Artifacts"])
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            if page_path and os.path.exists(page_path):
                st.image(page_path, caption="Original", use_container_width=True)
            else:
                st.info("Original image not available locally")
        with c2:
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
                label="📥 Download PDF",
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
        if st.button("💾 Save Changes"):
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            st.success("Saved!")

    with tab4:
        api = get_api_client()
        backend_page_id = page.get('id') or page.get('page_id')
        project_id = st.session_state.current_project['id'] if st.session_state.current_project else None

        if not backend_page_id or not project_id:
            st.info("Artifacts available for backend-managed pages only.")
        else:
            try:
                artifacts = api.get_artifacts_json(project_id, backend_page_id)
                tables = artifacts.get('tables', [])
                charts = artifacts.get('charts', [])
                diags = artifacts.get('diagrams', [])
                st.caption(f"Tables: {len(tables)} | Charts: {len(charts)} | Diagrams: {len(diags)}")

                # Tables panel
                if tables:
                    st.subheader("Tables")
                    # HTML view
                    try:
                        html_text = api.get_tables_html(project_id, backend_page_id)
                        st_html(html_text, height=300, scrolling=True)
                    except Exception as e:
                        st.warning(f"Failed to render tables HTML: {e}")

                    # CSV download
                    try:
                        csv_bytes = api.get_tables_csv(project_id, backend_page_id)
                        st.download_button(
                            label="📥 Download Tables CSV",
                            data=csv_bytes,
                            file_name=f"{stem}_tables.csv",
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.warning(f"CSV not available: {e}")
                else:
                    st.info("No table artifacts detected.")

                # Charts rendering via Vega-Lite
                if charts:
                    st.subheader("Charts")
                    # Stacking control (applies to all rendered charts in this view)
                    stack_choice = st.selectbox(
                        "Stacking",
                        options=["auto", "none", "zero", "normalize"],
                        index=0,
                        help="Override chart stacking. 'auto' uses the agent's default."
                    )
                    for idx, ch in enumerate(charts):
                        spec = ch.get('spec') or {}
                        meta = ch.get('meta') or {}
                        # Streamlit expects data separately; use meta.data_values if available
                        data_values = meta.get('data_values')
                        # Apply stacking override if requested
                        if stack_choice != "auto" and spec:
                            enc = spec.setdefault("encoding", {})
                            y_enc = enc.setdefault("y", {})
                            if stack_choice == "none":
                                # Remove stack if present
                                if "stack" in y_enc:
                                    y_enc.pop("stack", None)
                            else:
                                y_enc["stack"] = stack_choice
                        if spec and data_values:
                            st.vega_lite_chart(data_values, spec, use_container_width=True)
                        elif spec:
                            # Fallback: try rendering spec alone (may not work in all versions)
                            st.vega_lite_chart([], spec, use_container_width=True)
                        else:
                            st.caption(f"Chart #{idx+1}: spec missing")
                # Diagrams summary
                if diags:
                    st.subheader("Diagrams")
                    st.caption("Diagram annotations normalized; see PDF for on-image labels.")
                    try:
                        lists = api.get_diagram_key(project_id, backend_page_id)
                        key_items = lists.get('key', [])
                        on_items = lists.get('on_image', [])
                        if key_items:
                            st.markdown("**Diagram Key**")
                            for it in key_items:
                                st.markdown(f"- {it}")
                        else:
                            st.caption("No key items identified.")
                        if on_items:
                            st.markdown("**On-Image Labels**")
                            cols = st.columns(2)
                            half = (len(on_items)+1)//2
                            with cols[0]:
                                for it in on_items[:half]:
                                    st.caption(it)
                            with cols[1]:
                                for it in on_items[half:]:
                                    st.caption(it)
                    except Exception as e:
                        st.warning(f"Diagram Key unavailable: {e}")
            except Exception as e:
                st.warning(f"Artifacts not available: {e}")

def main():
    st.set_page_config(page_title="Book Translator", layout="wide", page_icon="📚")
    init_state()
    
    # Try to restore session from browser storage
    if not st.session_state.logged_in and not st.session_state.auth_checked:
        st.session_state.auth_checked = True
        # Use query params as a simple persistence mechanism
        if 'token' in st.query_params:
            try:
                token = st.query_params['token']
                api = get_api_client()
                api.token = token
                # Verify token and get user info
                user_info = api.get_current_user()
                # Token is valid
                st.session_state.logged_in = True
                st.session_state.token = token
                st.session_state.current_user = {"email": user_info.get('email', 'user@example.com')}
                logger.info(f"Restored session for user: {user_info.get('email')}")
            except Exception as e:
                logger.warning(f"Failed to restore session: {e}")
                # Clear invalid token
                st.query_params.clear()
    
    # Show auth page if not logged in
    if not st.session_state.logged_in:
        render_auth_page()
        return
    
    # Main app (logged in)
    render_sidebar()
    
    tab_process, tab_review = st.tabs(["📋 Processing Queue", "📖 Review Results"])
    
    with tab_process:
        render_page_list()
        
    with tab_review:
        render_results_view()

if __name__ == "__main__":
    main()
