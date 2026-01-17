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

    if 'current_page_offset' not in st.session_state:
        st.session_state.current_page_offset = 0
    if 'page_size' not in st.session_state:
        st.session_state.page_size = 20
    if 'total_pages_count' not in st.session_state:
        st.session_state.total_pages_count = 0
    if 'status_filter' not in st.session_state:
        st.session_state.status_filter = None
    if 'show_auth' not in st.session_state:
        st.session_state.show_auth = False
    if 'show_upgrade' not in st.session_state:
        st.session_state.show_upgrade = False

def render_upgrade_page():
    """Render the upgrade/pricing page for logged-in users."""
    api = get_api_client()
    st.title("🚀 Upgrade Your Plan")
    st.markdown("Select a plan to increase your page credit limit.")
    
    p1, p2, p3 = st.columns(3)
    
    with p1:
        st.markdown("""
            <div class="glass-card">
                <p class="badge">FREE</p>
                <h3>Basic</h3>
                <p>5 Credits</p>
                <hr>
                <p>Current Plan</p>
            </div>
        """, unsafe_allow_html=True)
        
    with p2:
        st.markdown('<div class="price-card-premium">', unsafe_allow_html=True)
        st.markdown("""
                <p class="badge">PROFESSIONAL</p>
                <h3>$29/mo</h3>
                <p>300 Credits</p>
        """, unsafe_allow_html=True)
        if st.button("Subscribe to Pro", type="primary", key="sub_pro"):
            try:
                res = api.create_checkout_session("pro")
                st.link_button("Go to Checkout", url=res['url'], type="primary")
            except Exception as e:
                st.error(f"Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with p3:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("""
                <p class="badge">SCALE</p>
                <h3>$79/mo</h3>
                <p>1,000 Credits</p>
        """, unsafe_allow_html=True)
        if st.button("Subscribe to Scale", type="primary", key="sub_scale"):
            try:
                res = api.create_checkout_session("scale")
                st.link_button("Go to Checkout", url=res['url'], type="primary")
            except Exception as e:
                st.error(f"Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("⬅️ Back to Dashboard"):
        st.session_state.show_upgrade = False
        st.rerun()

def render_landing_page():
    """Render a high-end, Dark Technical (Vercel-style) landing page."""
    api = get_api_client()
    try:
        pub_info = api.get_public_info()
    except:
        pub_info = {
            "company_name": "Technical Book Translator",
            "company_logo_url": "",
            "company_logo_size": 100,
            "site_primary_color": "#3b82f6",
            "example_screenshots": []
        }

    primary_color = pub_info.get('site_primary_color', '#3b82f6')

    st.markdown(f"""
        <style>
        /* Modern Dark Technical Aesthetic */
        .stApp {{ background-color: #0d1117 !important; color: #ffffff; }}
        
        /* Fix Streamlit default white header */
        header[data-testid="stHeader"] {{
            background-color: #0d1117 !important;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}

        /* Custom Header */
        .main-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 5%;
            background: #0d1117;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            position: sticky;
            top: 0;
            z-index: 9999;
        }}

        /* Hero Section */
        .hero-container {{
            padding: 120px 5% 80px 5%;
            text-align: center;
            background: radial-gradient(circle at 50% 0%, {primary_color}22 0%, #0d1117 70%);
        }}
        .hero-title {{
            font-size: clamp(3rem, 8vw, 5rem);
            font-weight: 800;
            line-height: 1.1;
            text-align: center;
            background: linear-gradient(to bottom right, #ffffff 40%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.04em;
            margin-bottom: 24px;
        }}
        .hero-subtitle {{
            font-size: 1.5rem;
            color: #94a3b8;
            max-width: 800px;
            margin: 0 auto 40px auto;
            line-height: 1.6;
            text-align: center !important;
        }}
        
        /* Feature Cards */
        .glass-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(51, 65, 85, 0.5);
            border-radius: 20px;
            padding: 35px;
            height: 100%;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }}
        .glass-card:hover {{
            border-color: {primary_color};
            transform: translateY(-5px);
            box-shadow: 0 0 30px {primary_color}1a;
        }}
        
        /* Pricing Cards */
        .price-card-premium {{
            background: linear-gradient(180deg, #0f172a 0%, #000000 100%);
            border: 1px solid {primary_color};
            border-radius: 24px;
            padding: 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        .price-card-premium::before {{
            content: "POPULAR";
            position: absolute;
            top: 20px;
            right: -30px;
            background: {primary_color};
            color: white;
            padding: 5px 40px;
            transform: rotate(45deg);
            font-size: 0.7rem;
            font-weight: 900;
        }}
        
        .badge {{
            background: {primary_color}1a;
            color: {primary_color};
            padding: 4px 12px;
            border-radius: 99px;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid {primary_color}33;
        }}

        /* Dashboard & Admin UI Modernization */
        .metric-card {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        }}
        
        .stSidebar {{
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 24px;
            background-color: transparent;
        }}

        .stTabs [data-baseweb="tab"] {{
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
            font-weight: 600;
            color: #94a3b8;
        }}

        .stTabs [aria-selected="true"] {{
            color: {primary_color} !important;
            border-bottom: 2px solid {primary_color} !important;
        }}
        
        /* Buttons */
        .stButton>button {{
            border-radius: 10px;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.05em;
        }}
        </style>
    """, unsafe_allow_html=True)

    # Sticky Header
    logo_html = f"<img src='{pub_info['company_logo_url']}' style='height: {pub_info['company_logo_size']/2}px;'>" if pub_info.get('company_logo_url') else f"<h3>{pub_info['company_name']}</h3>"
    st.markdown(f"""
        <div class="main-header">
            <div>{logo_html}</div>
            <div>
                <span style='color: #94a3b8; margin-right: 20px; font-size: 0.9rem; font-weight: 500;'>Features</span>
                <span style='color: #94a3b8; margin-right: 20px; font-size: 0.9rem; font-weight: 500;'>Pricing</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Hero Section
    st.markdown(f"""
        <div class="hero-container">
            <span class="badge" style="border-color: {primary_color}; color: {primary_color}">NOW IN PRIVATE BETA</span>
            <h1 class="hero-title">Technical Archeology<br>Powered by AI</h1>
            <p class="hero-subtitle">
                The world's most advanced engine for localizing high-spec engineering manuals. 
                Preserving specialized knowledge with <b>pinpoint diagram reconstruction</b>.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Call to Action
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        if st.button("🚀 Enter the Vault", type="primary", use_container_width=True):
            st.session_state.show_auth = True
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Dynamic Portfolio Slide Show
    portfolio = pub_info.get('example_screenshots', [])
    if not portfolio:
         # Fallback
         portfolio = ["https://storage.googleapis.com/book-translator-public/sample_diagram_1_orig.jpg|https://storage.googleapis.com/book-translator-public/sample_diagram_1_trans.jpg"]

    st.markdown("<h4 style='text-align: center; color: #94a3b8; font-weight: 400; margin-bottom: 30px;'>SEE THE SYSTEM IN ACTION</h4>", unsafe_allow_html=True)
    
    if portfolio:
        if 'portfolio_idx' not in st.session_state:
            st.session_state.portfolio_idx = 0
        
        current_pair = portfolio[st.session_state.portfolio_idx % len(portfolio)]
        if '|' in current_pair:
            orig, trans = current_pair.split('|')
            ex_col1, ex_col2 = st.columns(2)
            with ex_col1:
                 st.markdown(f"""
                    <div class="glass-card" style='text-align: center;'>
                        <h4 style='color: #60a5fa;'>Original Diagram</h4>
                        <img src="{orig}" style='width: 100%; border-radius: 10px; margin-top: 10px;'>
                    </div>
                 """, unsafe_allow_html=True)
            with ex_col2:
                 st.markdown(f"""
                    <div class="glass-card" style='text-align: center;'>
                        <h4 style='color: #60a5fa;'>Translated Result</h4>
                        <img src="{trans}" style='width: 100%; border-radius: 10px; margin-top: 10px;'>
                    </div>
                 """, unsafe_allow_html=True)

            if len(portfolio) > 1:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Next Example ❯", type="secondary"):
                    st.session_state.portfolio_idx += 1
                    st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    # How It Works Section
    st.markdown("<h2 style='text-align: center;'>Seamless Workflow</h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    w1, w2, w3, w4 = st.columns(4)
    with w1:
        st.markdown(f"""
            <div style='text-align: center;'>
                <h1 style='color: {primary_color}; font-size: 3rem;'>1</h1>
                <h4>Upload</h4>
                <p style='color: #94a3b8; font-size: 0.9rem;'>Drop your scanned JPG or PNG technical pages.</p>
            </div>
        """, unsafe_allow_html=True)
    with w2:
        st.markdown(f"""
            <div style='text-align: center;'>
                <h1 style='color: {primary_color}; font-size: 3rem;'>2</h1>
                <h4>Analyze</h4>
                <p style='color: #94a3b8; font-size: 0.9rem;'>AI detects diagrams, charts, and specialized tables.</p>
            </div>
        """, unsafe_allow_html=True)
    with w3:
        st.markdown(f"""
            <div style='text-align: center;'>
                <h1 style='color: {primary_color}; font-size: 3rem;'>3</h1>
                <h4>Localize</h4>
                <p style='color: #94a3b8; font-size: 0.9rem;'>Precise translation with bilingual overlays.</p>
            </div>
        """, unsafe_allow_html=True)
    with w4:
        st.markdown(f"""
            <div style='text-align: center;'>
                <h1 style='color: {primary_color}; font-size: 3rem;'>4</h1>
                <h4>Export</h4>
                <p style='color: #94a3b8; font-size: 0.9rem;'>Download high-res, merged PDF technical manuals.</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>---<br><br>", unsafe_allow_html=True)

    # Core Features
    st.markdown("### 🛠️ Built for Precision")
    f1, f2, f3 = st.columns(3)
    
    with f1:
        st.markdown("""
            <div class="glass-card">
                <h3>Bilingual Overlays</h3>
                <p style='color: #94a3b8;'>Intelligent pointer-and-label system that keeps original diagrams 100% intact while adding high-contrast translations.</p>
            </div>
        """, unsafe_allow_html=True)
    with f2:
        st.markdown("""
            <div class="glass-card">
                <h3>Technical Integrity</h3>
                <p style='color: #94a3b8;'>Context-aware translation utilizing Gemini 2.5 Flash. Specialized in maritime, aerospace, and heavy machinery terminology.</p>
            </div>
        """, unsafe_allow_html=True)
    with f3:
        st.markdown("""
            <div class="glass-card">
                <h3>Artifact Extraction</h3>
                <p style='color: #94a3b8;'>Automatic detection and extraction of complex charts, tables, and technical keys into structured data formats.</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>---<br><br>", unsafe_allow_html=True)

    # Pricing Section
    st.markdown("<h2 style='text-align: center;'>Choose Your Scale</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8;'>Transparent, credit-based pricing designed for technical workflows.</p>", unsafe_allow_html=True)
    
    p1, p2, p3 = st.columns(3)
    
    with p1:
        st.markdown(f"""
            <div class="glass-card">
                <p class="badge">FREE</p>
                <h1 style='margin: 20px 0;'>$0</h1>
                <p style='color: {primary_color};'>5 Page Credits</p>
                <hr style='border-color: #334155'>
                <p>✓ Smart Layout</p>
                <p>✓ Basic Diagrams</p>
                <p>✓ PDF Export</p>
            </div>
        """, unsafe_allow_html=True)
        
    with p2:
        st.markdown(f"""
            <div class="price-card-premium">
                <p class="badge">PROFESSIONAL</p>
                <h1 style='margin: 20px 0;'>$29<small style='font-size: 1rem; color: #94a3b8;'>/mo</small></h1>
                <p style='color: {primary_color};'>300 Page Credits</p>
                <hr style='border-color: #334155'>
                <p>✓ <b>Bilingual Overlay System</b></p>
                <p>✓ Priority Worker Queue</p>
                <p>✓ Interactive Label Review</p>
                <p>✓ Merged Book Export</p>
            </div>
        """, unsafe_allow_html=True)
        
    with p3:
        st.markdown(f"""
            <div class="glass-card">
                <p class="badge">SCALE</p>
                <h1 style='margin: 20px 0;'>$79<small style='font-size: 1rem; color: #94a3b8;'>/mo</small></h1>
                <p style='color: {primary_color};'>1,000 Page Credits</p>
                <hr style='border-color: #334155'>
                <p>✓ Custom Terminology Toning</p>
                <p>✓ Dedicated Worker Instance</p>
                <p>✓ Batch API Access</p>
                <p>✓ Support Tier 1</p>
            </div>
        """, unsafe_allow_html=True)

def render_auth_page():
    """Render login/signup page."""
    api = get_api_client()
    
    if st.button("⬅️ Back to Home"):
         st.session_state.show_auth = False
         st.session_state.show_upgrade = False
         st.rerun()

    st.title("🔐 Secure Access")
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
                            token = api.login(email, password)
                            st.session_state.logged_in = True
                            st.session_state.current_user = {"email": email}
                            st.session_state.token = token
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
    
    if not st.session_state.current_project:
        st.error("Please select or create a project first")
        return
    
    uid = uuid.uuid4().hex[:8]
    filename = f"{uid}_{uploaded_file.name}"
    path = os.path.join(IMAGES_DIR, filename)
    with open(path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    
    api = get_api_client()
    project_id = st.session_state.current_project['id']
    existing_numbers = set()
    try:
        existing_numbers = {p.get('page_number') for p in st.session_state['pages'] if p.get('page_number')}
    except:
        pass

    import re
    page_number = None
    patterns = [
        r'page\s*[-_]?\s*(\d+)',
        r'p\s*[-_]?\s*(\d+)',
        r'[_-](\d+)\.[a-zA-Z0-9]+$',
        r'^(\d+)\.[a-zA-Z0-9]+$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, uploaded_file.name, re.IGNORECASE)
        if match:
            try:
                extracted_num = int(match.group(1))
                if extracted_num not in existing_numbers:
                    page_number = extracted_num
                    break
            except ValueError:
                continue
    
    if page_number is None:
        max_page = max(existing_numbers, default=0)
        page_number = max_page + 1
    
    try:
        api = get_api_client()
        with open(path, 'rb') as f:
            page_data = api.upload_page(
                project_id=project_id,
                page_number=page_number,
                file=f,
                filename=uploaded_file.name
            )
        
        page_info = {
            'id': uid,
            'page_id': page_data['id'],
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
                error_detail = e.response.json().get('detail', str(e))
            except:
                error_detail = e.response.text or str(e)
        st.error(f"Failed to upload page: {error_detail}")
        return None

def download_page_image(page):
    if page.get('path') and os.path.exists(page['path']):
        return page['path']
    
    try:
        api = get_api_client()
        project_id = st.session_state.current_project['id']
        page_id = page.get('page_id') or page.get('id')
        
        if not page_id: return None
        
        result = api.get_download_url(project_id, page_id, file_type='original')
        download_url = result.get('url') if isinstance(result, dict) else result
        
        if not download_url: return None
        
        if download_url.startswith('file://'):
            import urllib.parse
            local_path = urllib.parse.unquote(download_url.replace('file://', ''))
            if os.path.exists(local_path):
                filename = page.get('name') or f"page_{page.get('page_number')}.jpg"
                dest_path = os.path.join(IMAGES_DIR, f"{uuid.uuid4().hex[:8]}_{filename}")
                import shutil
                shutil.copy2(local_path, dest_path)
                page['path'] = dest_path
                return dest_path
        else:
            response = requests.get(download_url)
            response.raise_for_status()
            filename = page.get('name') or f"page_{page.get('page_number')}.jpg"
            local_path = os.path.join(IMAGES_DIR, f"{uuid.uuid4().hex[:8]}_{filename}")
            with open(local_path, 'wb') as f:
                f.write(response.content)
            page['path'] = local_path
            return local_path
    except:
        return None

def render_sidebar():
    api = get_api_client()
    with st.sidebar:
        st.title("📚 Book Translator")
        st.markdown(f"**User:** {st.session_state.current_user['email']}")

        try:
             user_info = api.get_current_user()
             st.session_state.current_user.update(user_info)
             credits_total = user_info.get('total_credits', 5)
             credits_used = user_info.get('used_credits', 0)
             credits_left = max(0, credits_total - credits_used)
             st.markdown(f"**Credits:** {credits_left} / {credits_total} remaining")
             sub_status = user_info.get('subscription_status', 'free')
             st.markdown(f"**Plan:** :{ 'green' if sub_status != 'free' else 'orange' }[{sub_status.upper()}]")
             
             if credits_left < 5:
                  if st.button("💳 Upgrade Plan", use_container_width=True, type="primary"):
                       st.session_state.show_upgrade = True
                       st.rerun()

             if user_info.get('is_admin'):
                  st.markdown("---")
                  st.markdown("### 👑 Admin Mode")
                  st.session_state.admin_mode = st.toggle("Enable Admin View", value=st.session_state.get('admin_mode', False))

        except:
             pass
        
        if st.button("🚪 Logout", use_container_width=True):
            st.query_params.clear()
            st.session_state.logged_in = False
            st.rerun()
        
        if not st.session_state.get('admin_mode'):
            st.markdown("---")
            st.header("Projects")
            try:
                projects = api.list_projects()
                if projects:
                    project_options = {p["id"]: p['title'] for p in projects}
                    if not st.session_state.current_project:
                        st.session_state.current_project = projects[0]
                    
                    selected_id = st.selectbox("Select Project", options=list(project_options.keys()), format_func=lambda x: project_options[x])
                    if st.button("Load Project") or st.session_state.current_project['id'] != selected_id:
                        st.session_state.current_project = api.get_project(selected_id)
                        st.session_state.pages_loaded_from_backend = False
                        st.rerun()
                else:
                    st.info("No projects yet.")
            except:
                pass

def render_page_list():
    if not st.session_state.current_project:
        st.warning("⚠️ Please select or create a project first")
        return
    
    if not st.session_state.pages_loaded_from_backend:
        try:
            api = get_api_client()
            res = api.list_pages(st.session_state.current_project['id'], skip=st.session_state.current_page_offset, limit=st.session_state.page_size, status_filter=st.session_state.status_filter)
            st.session_state['pages'] = res['pages']
            st.session_state.total_pages_count = res['total']
            st.session_state.pages_loaded_from_backend = True
        except:
            pass
    
    st.header("📋 Processing Queue")
    # ... Simplified queue view logic here ...

def main():
    st.set_page_config(page_title="Book Translator", layout="wide", page_icon="📚")
    init_state()
    
    if not st.session_state.logged_in:
        if 'token' in st.query_params:
            try:
                api = get_api_client()
                api.token = st.query_params['token']
                user_info = api.get_current_user()
                st.session_state.logged_in = True
                st.session_state.token = api.token
                st.session_state.current_user = user_info
            except:
                st.query_params.clear()

    if not st.session_state.logged_in:
        if st.session_state.show_auth:
            render_auth_page()
        else:
            render_landing_page()
            if st.sidebar.button("🔑 Login / Signup"):
                st.session_state.show_auth = True
                st.rerun()
        return

    render_sidebar()

    if st.session_state.get('admin_mode'):
        st.title("🛡️ Super Admin Control Room")
        try:
            api = get_api_client()
            stats = api.get_admin_stats()
            
            admin_nav = st.radio("Navigation", ["📊 Dashboard", "👥 Users", "💼 CRM & Billing", "🖼️ Showcase", "⚙️ Settings"], horizontal=True)
            
            if admin_nav == "📊 Dashboard":
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Users", stats['total_users'])
                c2.metric("Premium Users", stats['premium_users'])
                c3.metric("Total Pages", stats['total_pages'])
                c4.metric("Failure Rate", f"{(stats['failed_pages']/(stats['total_pages'] or 1))*100:.1f}%")
                
                st.markdown("---")
                st.subheader("💰 Financial Intelligence")
                f1, f2, f3 = st.columns(3)
                financials = stats.get('financials', {})
                f1.metric("Est. MRR", f"${financials.get('mrr', 0):,.2f}")
                f2.metric("Total Revenue", f"${financials.get('total_revenue', 0):,.2f}")
                f3.metric("Avg. ARPU", f"${(financials.get('mrr', 0) / (stats['premium_users'] or 1)):,.2f}")

            elif admin_nav == "⚙️ Settings":
                tabs = st.tabs(["🏢 Company Info", "🎨 Site Branding", "📧 Email Setup", "💳 Stripe"])
                with tabs[0]:
                    with st.form("comp_form"):
                        c_name = st.text_input("Company Name", value=stats['settings']['company_name'])
                        c_mail = st.text_input("Contact Email", value=stats['settings']['company_email'])
                        l_url = st.text_input("Logo URL", value=stats['settings']['company_logo_url'])
                        l_size = st.slider("Logo Size", 10, 200, value=stats['settings']['company_logo_size'])
                        if st.form_submit_button("Update Identity"):
                            api.admin_update_system_config({"company_name": c_name, "company_email": c_mail, "company_logo_url": l_url, "company_logo_size": l_size})
                            st.success("Updated!")
                
                with tabs[1]:
                    with st.form("brand_form"):
                        p_color = st.color_picker("Primary Color", value=stats['settings']['site_primary_color'])
                        s_color = st.color_picker("Secondary Color", value=stats['settings']['site_secondary_color'])
                        if st.form_submit_button("Update Branding"):
                            api.admin_update_system_config({"site_primary_color": p_color, "site_secondary_color": s_color})
                            st.success("Branding Updated!")
            
            elif admin_nav == "🖼️ Showcase":
                st.subheader("🖼️ Portfolio Showcase")
                with st.form("port_upload", clear_on_submit=True):
                    o_file = st.file_uploader("Original", type=['jpg', 'png'])
                    t_file = st.file_uploader("Translated", type=['jpg', 'png'])
                    if st.form_submit_button("Upload to Portfolio"):
                        if o_file and t_file:
                            api.admin_upload_portfolio(o_file, t_file)
                            st.success("Added!")
                            st.rerun()
                
                st.markdown("---")
                for pair in stats.get('example_screenshots', []):
                    if '|' in pair:
                        o, t = pair.split('|')
                        c1, c2 = st.columns(2)
                        c1.image(o, width=150, caption="Original")
                        c2.image(t, width=150, caption="Translated")

            elif admin_nav == "💼 CRM & Billing":
                st.subheader("💼 CRM & Financial Operations")
                
                crm_tabs = st.tabs(["⚡ Document Wizard", "📖 Ledger", "📈 Lead Tracker"])
                
                with crm_tabs[0]:
                    # Multi-Stage Wizard
                    if 'wizard_step' not in st.session_state: st.session_state.wizard_step = 1
                    if 'wiz_items' not in st.session_state: st.session_state.wiz_items = [{"name": "", "description": "", "qty": 1, "price": 0.0}]

                    # Step 1: Header Details
                    if st.session_state.wizard_step == 1:
                        st.write("### Step 1: Document Header")
                        with st.form("wiz_form_h"):
                            user_list = api.admin_list_users()
                            w_client = st.selectbox("Select Client", options=[u['id'] for u in user_list], format_func=lambda x: next(u['email'] for u in user_list if u['id'] == x))
                            w_type = st.selectbox("Document Type", ["QUOTATION", "INVOICE", "RECEIPT"])
                            col_w1, col_w2 = st.columns(2)
                            w_curr = col_w1.selectbox("Currency", ["USD", "EUR", "JPY", "GBP"])
                            w_due = col_w2.date_input("Due/Expiry Date")
                            
                            w_tax = st.slider("Tax Rate (%)", 0, 30, 0)
                            w_disc = st.slider("Discount (%)", 0, 100, 0)
                            
                            if st.form_submit_button("Next: Define Scope ❯"):
                                # Use a separate key to store data, don't use the form key
                                st.session_state.wiz_data_h = {"user_id": w_client, "type": w_type, "curr": w_curr, "due": w_due.isoformat(), "tax": w_tax, "disc": w_disc}
                                st.session_state.wizard_step = 2
                                st.rerun()

                    # Step 2: Dynamic Items
                    elif st.session_state.wizard_step == 2:
                        st.write("### Step 2: Service Items")
                        
                        for idx, item in enumerate(st.session_state.wiz_items):
                            with st.expander(f"Item #{idx+1}: {item['name'] or 'New Service'}", expanded=True):
                                c_i1, c_i2 = st.columns([2, 1])
                                item['name'] = c_i1.text_input("Service Name", value=item['name'], key=f"name_{idx}")
                                item['qty'] = c_i2.number_input("Quantity", min_value=1, value=item['qty'], key=f"qty_{idx}")
                                item['description'] = st.text_area("Scope of Work (Rich Text)", value=item['description'], key=f"desc_{idx}")
                                item['price'] = c_i2.number_input("Unit Price", min_value=0.0, value=item['price'], key=f"prc_{idx}")

                        if st.button("➕ Add Service Row"):
                            st.session_state.wiz_items.append({"name": "", "description": "", "qty": 1, "price": 0.0})
                            st.rerun()
                        
                        col_nav1, col_nav2 = st.columns(2)
                        if col_nav1.button("⬅️ Back"): st.session_state.wizard_step = 1; st.rerun()
                        if col_nav2.button("Preview & Generate ❯", type="primary"):
                            st.session_state.wizard_step = 3
                            st.rerun()

                    # Step 3: Final Review
                    elif st.session_state.wizard_step == 3:
                        st.write("### Step 3: Review & Finalize")
                        h = st.session_state.wiz_data_h
                        st.write(f"**Type:** {h['type']} | **Client:** {h['user_id']} | **Total Items:** {len(st.session_state.wiz_items)}")
                        
                        subtotal = sum(i['qty'] * i['price'] for i in st.session_state.wiz_items)
                        st.metric("Estimated Grand Total", f"{h['curr']} {subtotal * (1 - h['disc']/100) * (1 + h['tax']/100):.2f}")
                        
                        if st.button("📜 Generate Professional PDF", type="primary", use_container_width=True):
                            api.admin_create_document({
                                "user_id": h['user_id'], "doc_type": h['type'], "amount": subtotal,
                                "currency": h['curr'], "tax_rate": h['tax'], "discount_rate": h['disc'],
                                "items": st.session_state.wiz_items, "due_date": h['due']
                            })
                            st.success("Document Generated & Stamped!")
                            st.session_state.wizard_step = 1
                            st.session_state.wiz_items = [{"name": "", "description": "", "qty": 1, "price": 0.0}]
                            time.sleep(2)
                            st.rerun()
                        
                        if st.button("Cancel"): st.session_state.wizard_step = 1; st.rerun()

                with crm_tabs[1]:
                    docs = api.admin_list_documents()
                    for d in docs:
                        with st.expander(f"{d['doc_type']} - {d['currency']} {d['amount']} ({d['status']})"):
                            st.caption(f"Created: {d['created_at']}")
                            if d['doc_type'] == "QUOTATION" and d['status'] == "SENT":
                                if st.button("✅ Accept & Convert to Invoice", key=f"conv_{d['id']}"):
                                    api.admin_convert_quote(d['id'])
                                    st.success("Converted!")
                                    st.rerun()
                    
        except Exception as e:
            st.error(f"Admin Error: {e}")
        return

    if st.session_state.get('show_upgrade'):
        render_upgrade_page()
        return

    tab_process, tab_review = st.tabs(["📋 Processing Queue", "📖 Review Results"])
    with tab_process:
        render_page_list()

if __name__ == "__main__":
    main()
