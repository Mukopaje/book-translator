# Streamlit Frontend Integration with Backend API

This guide shows how to update the Streamlit app to work with the FastAPI backend for persistent storage.

## Installation

Add to your `requirements.txt`:
```
requests==2.31.0
```

## API Client Service

Create `src/api_client.py`:

```python
"""Client for communicating with the FastAPI backend."""
import requests
from typing import Optional, Dict, Any, BinaryIO
import streamlit as st


class APIClient:
    """Client for backend API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: Optional[str] = None
    
    def _headers(self) -> Dict[str, str]:
        """Get headers with auth token."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    # Auth
    def signup(self, email: str, password: str, full_name: str) -> Dict[str, Any]:
        """Register new user."""
        response = requests.post(
            f"{self.base_url}/auth/signup",
            json={"email": email, "password": password, "full_name": full_name}
        )
        response.raise_for_status()
        return response.json()
    
    def login(self, email: str, password: str) -> str:
        """Login and return token."""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        return self.token
    
    # Projects
    def create_project(self, title: str, author: str, book_context: str) -> Dict[str, Any]:
        """Create new project."""
        response = requests.post(
            f"{self.base_url}/projects",
            headers=self._headers(),
            json={
                "title": title,
                "author": author,
                "source_language": "ja",
                "target_language": "en",
                "book_context": book_context
            }
        )
        response.raise_for_status()
        return response.json()
    
    def list_projects(self) -> list:
        """Get user's projects."""
        response = requests.get(
            f"{self.base_url}/projects",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()["projects"]
    
    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get project details."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()
    
    # Pages
    def upload_page(self, project_id: int, page_number: int, file: BinaryIO, filename: str) -> Dict[str, Any]:
        """Upload page image."""
        files = {"file": (filename, file, "image/jpeg")}
        data = {"page_number": page_number}
        
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/pages",
            headers=headers,
            files=files,
            data=data
        )
        response.raise_for_status()
        return response.json()
    
    def list_pages(self, project_id: int) -> list:
        """Get project pages."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()["pages"]
    
    def get_download_url(self, project_id: int, page_id: int, file_type: str = "pdf") -> str:
        """Get signed download URL."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}/download",
            headers=self._headers(),
            params={"file_type": file_type}
        )
        response.raise_for_status()
        return response.json()["url"]


# Global API client instance
def get_api_client() -> APIClient:
    """Get or create API client in session state."""
    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient()
    return st.session_state.api_client
```

## Updated Streamlit App

Update `app_v2.py`:

```python
import streamlit as st
from src.api_client import get_api_client

st.set_page_config(page_title="Book Translator", layout="wide")

# Get API client
api = get_api_client()

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_project" not in st.session_state:
    st.session_state.current_project = None

# Auth UI
if not st.session_state.logged_in:
    st.title("Book Translator - Login")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                try:
                    token = api.login(email, password)
                    st.session_state.logged_in = True
                    st.success("Logged in successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
    
    with tab2:
        with st.form("signup_form"):
            email = st.text_input("Email")
            full_name = st.text_input("Full Name")
            password = st.text_input("Password", type="password")
            password2 = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Sign Up")
            
            if submit:
                if password != password2:
                    st.error("Passwords don't match")
                else:
                    try:
                        api.signup(email, password, full_name)
                        st.success("Account created! Please login.")
                    except Exception as e:
                        st.error(f"Signup failed: {e}")
    
    st.stop()

# Main App (logged in)
st.title("Book Translator")

# Sidebar: Project selector
with st.sidebar:
    st.header("Projects")
    
    # Load projects
    try:
        projects = api.list_projects()
        
        if projects:
            project_titles = {p["id"]: p["title"] for p in projects}
            selected_id = st.selectbox(
                "Select Project",
                options=list(project_titles.keys()),
                format_func=lambda x: project_titles[x]
            )
            
            if st.button("Load Project"):
                st.session_state.current_project = api.get_project(selected_id)
                st.success(f"Loaded: {st.session_state.current_project['title']}")
        else:
            st.info("No projects yet")
    
    except Exception as e:
        st.error(f"Error loading projects: {e}")
    
    st.divider()
    
    # Create new project
    with st.expander("Create New Project"):
        with st.form("new_project"):
            title = st.text_input("Book Title")
            author = st.text_input("Author")
            context = st.text_area("Book Context", 
                help="Describe the book's subject matter for better translations")
            
            if st.form_submit_button("Create"):
                try:
                    project = api.create_project(title, author, context)
                    st.session_state.current_project = project
                    st.success(f"Created: {title}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.current_project = None
        api.token = None
        st.rerun()

# Main content
if st.session_state.current_project:
    project = st.session_state.current_project
    
    st.subheader(f"📖 {project['title']}")
    st.write(f"**Author:** {project['author']}")
    st.write(f"**Progress:** {project['completed_pages']}/{project['total_pages']} pages")
    
    # Upload new page
    st.divider()
    st.subheader("Upload New Page")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])
    with col2:
        page_number = st.number_input("Page Number", min_value=1, value=1)
    
    if uploaded_file and st.button("Upload & Process"):
        with st.spinner("Uploading..."):
            try:
                # Upload to backend
                page = api.upload_page(
                    project["id"],
                    page_number,
                    uploaded_file,
                    uploaded_file.name
                )
                st.success(f"Page {page_number} uploaded!")
                
                # TODO: Process locally or wait for backend processing
                # For now, process locally
                from src.main import BookTranslator
                from PIL import Image
                import io
                
                uploaded_file.seek(0)
                image = Image.open(uploaded_file)
                
                translator = BookTranslator(book_context=project["book_context"])
                results = translator.process_page(image, page_number)
                
                st.success("Processing complete!")
                # Show results...
                
            except Exception as e:
                st.error(f"Error: {e}")
    
    # List existing pages
    st.divider()
    st.subheader("Existing Pages")
    
    try:
        pages = api.list_pages(project["id"])
        
        for page in pages:
            col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
            
            with col1:
                st.write(f"**Page {page['page_number']}**")
            
            with col2:
                st.write(f"Status: {page['status']}")
            
            with col3:
                if page["output_pdf_path"]:
                    if st.button(f"Download PDF", key=f"download_{page['id']}"):
                        url = api.get_download_url(project["id"], page["id"], "pdf")
                        st.markdown(f"[Download PDF]({url})")
            
            with col4:
                if st.button("View", key=f"view_{page['id']}"):
                    st.session_state.viewing_page = page
    
    except Exception as e:
        st.error(f"Error loading pages: {e}")

else:
    st.info("👈 Select or create a project to get started")
```

## Migration Checklist

- [ ] Install `requests` library
- [ ] Create `src/api_client.py`
- [ ] Update `app_v2.py` with auth UI
- [ ] Replace `session_state` page storage with API calls
- [ ] Test signup/login flow
- [ ] Test project creation
- [ ] Test page upload
- [ ] Test page restoration on reload
- [ ] Configure CORS in backend for Streamlit origin

## Benefits

✅ **Persistent Storage**: Work survives page reloads  
✅ **Multi-Device**: Access from anywhere  
✅ **Multi-User**: Each user has their own projects  
✅ **Scalable**: Ready for batch processing  
✅ **Organized**: Projects group related pages  

## Next Steps

1. Test the integration locally
2. Add async processing worker (Phase 4)
3. Deploy backend to cloud
4. Update Streamlit to use production API URL
