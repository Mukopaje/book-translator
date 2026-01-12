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
    def signup(self, email: str, password: str, full_name: str = "") -> Dict[str, Any]:
        """Register new user."""
        url = f"{self.base_url}/auth/signup"
        print(f"DEBUG: Signup URL = {url}")
        print(f"DEBUG: base_url = {self.base_url}")
        response = requests.post(
            url,
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

    def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user information."""
        response = requests.get(
            f"{self.base_url}/auth/me",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    # Projects
    def create_project(self, title: str, author: str = "", book_context: str = "",
                      source_language: str = "auto", target_language: str = "en") -> Dict[str, Any]:
        """Create new project with language selection."""
        response = requests.post(
            f"{self.base_url}/projects",
            headers=self._headers(),
            json={
                "title": title,
                "author": author,
                "source_language": source_language,
                "target_language": target_language,
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
    
    def update_project(self, project_id: int, title: str = None, author: str = None, 
                      book_context: str = None, completed_pages: int = None) -> Dict[str, Any]:
        """Update project metadata."""
        data = {}
        if title:
            data["title"] = title
        if author:
            data["author"] = author
        if book_context:
            data["book_context"] = book_context
        if completed_pages is not None:
            data["completed_pages"] = completed_pages
        
        response = requests.patch(
            f"{self.base_url}/projects/{project_id}",
            headers=self._headers(),
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def delete_project(self, project_id: int) -> None:
        """Delete a project."""
        response = requests.delete(
            f"{self.base_url}/projects/{project_id}",
            headers=self._headers()
        )
        response.raise_for_status()
    
    def download_complete_book(self, project_id: int) -> bytes:
        """Download merged PDF of all completed pages."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/download-book",
            headers=self._headers(),
            stream=True
        )
        response.raise_for_status()
        return response.content
    
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
    
    def list_pages(self, project_id: int, skip: int = 0, limit: int = 20,
                   status_filter: str = None) -> Dict[str, Any]:
        """
        Get project pages with pagination and optional filtering.

        Args:
            project_id: Project ID
            skip: Number of pages to skip (for pagination)
            limit: Maximum pages to return (default 20, max 500)
            status_filter: Optional comma-separated status filter (e.g., "COMPLETED,NEEDS_REVIEW")

        Returns:
            Dictionary with 'pages' list and 'total' count
        """
        params = {"skip": skip, "limit": limit}
        if status_filter:
            params["status_filter"] = status_filter

        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages",
            headers=self._headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()  # Returns {'pages': [...], 'total': N}
    
    def get_page(self, project_id: int, page_id: int) -> Dict[str, Any]:
        """Get page details."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()
    
    def get_download_url(self, project_id: int, page_id: int, file_type: str = "pdf") -> Dict[str, Any]:
        """Get signed download URL for a page file."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}/download",
            params={"file_type": file_type},
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()
    
    def update_page(self, project_id: int, page_id: int, status: str = None,
                   ocr_text: str = None, translated_text: str = None,
                   output_pdf_path: str = None) -> Dict[str, Any]:
        """Update page status and results."""
        data = {}
        if status:
            data['status'] = status
        if ocr_text:
            data['ocr_text'] = ocr_text
        if translated_text:
            data['translated_text'] = translated_text
        if output_pdf_path:
            data['output_pdf_path'] = output_pdf_path

        response = requests.patch(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}",
            headers=self._headers(),
            json=data
        )
        response.raise_for_status()
        return response.json()

    def replace_page_image(self, project_id: int, page_id: int, file: BinaryIO,
                          filename: str = None) -> Dict[str, Any]:
        """
        Replace the input image for a page.

        Args:
            project_id: Project ID
            page_id: Page ID to replace
            file: New image file (binary)
            filename: Optional filename

        Returns:
            Updated page data with reset status
        """
        files = {"file": (filename or "replaced_image.jpg", file, "image/jpeg")}

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.put(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}/replace-image",
            headers=headers,
            files=files
        )
        response.raise_for_status()
        return response.json()
    
    # Async Job Management
    def queue_page_processing(self, page_id: int) -> Dict[str, Any]:
        """Queue a page for async background processing."""
        response = requests.post(
            f"{self.base_url}/jobs/process-page/{page_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()
    
    def queue_batch_processing(self, page_ids: list[int]) -> Dict[str, Any]:
        """Queue multiple pages for processing."""
        response = requests.post(
            f"{self.base_url}/jobs/process-batch",
            headers=self._headers(),
            json=page_ids
        )
        response.raise_for_status()
        return response.json()

    def queue_by_status(self, project_id: int, statuses: list[str]) -> Dict[str, Any]:
        """Queue all pages in a project with specific statuses."""
        response = requests.post(
            f"{self.base_url}/jobs/queue-by-status/{project_id}",
            headers=self._headers(),
            json=statuses
        )
        response.raise_for_status()
        return response.json()

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a background task."""
        response = requests.get(
            f"{self.base_url}/jobs/status/{task_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()
    
    def get_page_status(self, page_id: int) -> Dict[str, Any]:
        """Get current processing status of a page."""
        response = requests.get(
            f"{self.base_url}/jobs/page-status/{page_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    # Artifacts
    def get_artifacts_json(self, project_id: int, page_id: int) -> Dict[str, Any]:
        """Fetch artifacts JSON for a page (tables/charts/diagrams)."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}/artifacts",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_tables_csv(self, project_id: int, page_id: int) -> bytes:
        """Fetch concatenated CSV for all tables in a page."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}/artifacts/tables.csv",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.content

    def get_tables_html(self, project_id: int, page_id: int) -> str:
        """Fetch simple HTML for all tables in a page."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}/artifacts/tables.html",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.text

    def get_diagram_key(self, project_id: int, page_id: int) -> Dict[str, Any]:
        """Fetch Diagram Key items for a page."""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/pages/{page_id}/artifacts/diagrams/key",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()


# Global API client instance
def get_api_client() -> APIClient:
    """Get or create API client in session state."""
    if "api_client" not in st.session_state:
        # Use environment variable or default to backend service name for Docker
        import os
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        st.session_state.api_client = APIClient(base_url=backend_url)
        print(f"API Client created with base_url: {backend_url}")
    
    # Restore token from session state if available
    if st.session_state.get('token') and not st.session_state.api_client.token:
        st.session_state.api_client.token = st.session_state.token
        print(f"Restored token from session state")
    
    return st.session_state.api_client
