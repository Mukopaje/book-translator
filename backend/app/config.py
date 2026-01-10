"""Application configuration using Pydantic settings."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str
    
    # JWT Authentication
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Storage
    use_local_storage: bool = True
    
    # Google Cloud Storage (optional if using local storage)
    gcs_bucket_originals: str = "dev-bucket-originals"
    gcs_bucket_outputs: str = "dev-bucket-outputs"
    google_application_credentials: str = "/tmp/credentials.json"
    
    # SendGrid (optional for email features)
    sendgrid_api_key: str = "dev-sendgrid-key"
    from_email: str = "noreply@example.com"
    
    # Redis & Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # CORS
    allowed_origins: str = "http://localhost:8501"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
