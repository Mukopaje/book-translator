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
    
    # Stripe
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = "price_pro_300"
    stripe_price_id_scale: str = "price_scale_1000"
    
    # Portfolio Examples (GCS Paths) - format: "orig_url|trans_url,orig_url|trans_url"
    example_screenshots: str = ""

    # Company Details
    company_name: str = "Technical Book Translator"
    company_address: str = ""
    company_email: str = "support@example.com"
    company_phone: str = ""
    company_logo_url: str = ""
    company_logo_size: int = 100 # percentage

    # Site Branding
    site_primary_color: str = "#3b82f6"
    site_secondary_color: str = "#1e3a8a"
    site_contact_info: str = "Available 24/7 for technical support."

    # Email Settings
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

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
