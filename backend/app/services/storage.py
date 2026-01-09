"""Google Cloud Storage service for file uploads."""
from google.cloud import storage
from app.config import settings
import os
from typing import BinaryIO
from datetime import timedelta
import shutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError

def _initialize_gcs_client_with_timeout(credentials_path: str, timeout: int = 30):
    """
    Initializes the GCS client with a timeout.
    Raises:
        TimeoutError: If the client takes too long to initialize.
        Exception: For other initialization errors.
    """
    def init():
        return storage.Client.from_service_account_json(credentials_path)

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(init)
    
    try:
        client = future.result(timeout=timeout)
        return client
    except TimeoutError:
        raise TimeoutError(f"GCS client initialization timed out after {timeout} seconds.")
    finally:
        executor.shutdown(wait=False)

class StorageService:
    """Service for managing file uploads to Google Cloud Storage."""
    
    def __init__(self):
        """Initialize GCS client or local storage."""
        from app.config import settings
        
        # Read storage mode from settings (which reads from environment)
        self.use_local = settings.use_local_storage
        
        # Setup local storage paths
        self.local_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage"))
        os.makedirs(os.path.join(self.local_base_path, "originals"), exist_ok=True)
        os.makedirs(os.path.join(self.local_base_path, "outputs"), exist_ok=True)
        
        # GCS setup (if not using local)
        self.client = None
        self.originals_bucket = None
        self.outputs_bucket = None
        
        if not self.use_local:
            try:
                print(f"🔧 Initializing Google Cloud Storage...")
                self.client = _initialize_gcs_client_with_timeout(
                    settings.google_application_credentials
                )
                self.originals_bucket = self.client.bucket(settings.gcs_bucket_originals)
                self.outputs_bucket = self.client.bucket(settings.gcs_bucket_outputs)
                print(f"✅ GCS connected: {settings.gcs_bucket_originals}, {settings.gcs_bucket_outputs}")
            except Exception as e:
                print(f"❌ GCS configuration failed - falling back to local storage: {e}")
                self.use_local = True
        else:
            print(f"📁 Using local storage: {self.local_base_path}")
    
    def upload_original_image(
        self, 
        file: BinaryIO, 
        project_id: int, 
        page_number: int,
        filename: str
    ) -> str:
        """
        Upload an original page image to GCS or local storage.
        
        Returns:
            File path (GCS path or local path)
        """
        # Create path: projects/{project_id}/originals/page_{page_number}_{filename}
        blob_path = f"projects/{project_id}/originals/page_{page_number}_{filename}"
        
        if self.use_local:
            # Save to local filesystem
            local_path = os.path.join(self.local_base_path, "originals", blob_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                shutil.copyfileobj(file, f)
            return blob_path
        else:
            # Upload to GCS
            blob = self.originals_bucket.blob(blob_path)
            blob.upload_from_file(file, rewind=True)
            return blob_path
    
    def upload_output_pdf(
        self, 
        file_path: str, 
        project_id: int, 
        page_number: int
    ) -> str:
        """
        Upload a translated PDF to GCS or local storage.
        
        Returns:
            File path (GCS path or local path)
        """
        # Create path: projects/{project_id}/outputs/page_{page_number}.pdf
        blob_path = f"projects/{project_id}/outputs/page_{page_number}.pdf"
        
        if self.use_local:
            # Copy to local filesystem
            local_path = os.path.join(self.local_base_path, "outputs", blob_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            shutil.copy2(file_path, local_path)
            return blob_path
        else:
            # Upload to GCS
            blob = self.outputs_bucket.blob(blob_path)
            blob.upload_from_filename(file_path)
            return blob_path

    def upload_artifacts_json(
        self,
        file_path: str,
        project_id: int,
        page_number: int,
    ) -> str:
        """
        Upload artifacts JSON to storage under outputs.

        Path: projects/{project_id}/outputs/page_{page_number}_artifacts.json
        Returns the blob path (for local mode this is a relative path under storage/outputs).
        """
        blob_path = f"projects/{project_id}/outputs/page_{page_number}_artifacts.json"

        if self.use_local:
            local_path = os.path.join(self.local_base_path, "outputs", blob_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            shutil.copy2(file_path, local_path)
            return blob_path
        else:
            blob = self.outputs_bucket.blob(blob_path)
            blob.upload_from_filename(file_path)
            return blob_path
    
    def get_signed_url(self, bucket_name: str, blob_path: str, expiration: int = 3600) -> str:
        """
        Generate a signed URL for downloading a file.
        
        Args:
            bucket_name: Name of the GCS bucket (or "originals"/"outputs" for local)
            blob_path: Path to the blob in the bucket
            expiration: URL expiration time in seconds (default 1 hour)
        
        Returns:
            Signed URL or local file path
        """
        if self.use_local:
            # Return local file path
            folder = "originals" if "originals" in bucket_name else "outputs"
            local_path = os.path.join(self.local_base_path, folder, blob_path)
            return f"file://{local_path}"
        else:
            # Generate GCS signed URL
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expiration),
                method="GET"
            )
            return url
    
    def delete_project_files(self, project_id: int):
        """Delete all files associated with a project."""
        if self.use_local:
            # Delete local files
            for folder in ["originals", "outputs"]:
                project_path = os.path.join(self.local_base_path, folder, f"projects/{project_id}")
                if os.path.exists(project_path):
                    shutil.rmtree(project_path)
        else:
            # Delete from GCS
            prefix = f"projects/{project_id}/"
            blobs = self.originals_bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                blob.delete()
            
            blobs = self.outputs_bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                blob.delete()
    
    def get_local_path(self, blob_path: str, is_output: bool = True) -> str:
        """Get the local filesystem path for a stored file."""
        folder = "outputs" if is_output else "originals"
        return os.path.join(self.local_base_path, folder, blob_path)


# Global storage service instance
storage_service = StorageService()
