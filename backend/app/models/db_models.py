"""Database models for users, projects, and pages."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ProjectStatus(str, enum.Enum):
    """Project processing status."""
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PageStatus(str, enum.Enum):
    """Page processing status."""
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Quality check failed, needs manual review


class User(Base):
    """User account table."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Billing & Credits
    is_admin = Column(Integer, default=0) # 0: user, 1: admin
    total_credits = Column(Integer, default=5) # 5 free pages initially
    used_credits = Column(Integer, default=0)
    stripe_customer_id = Column(String(255), nullable=True)
    subscription_status = Column(String(50), default="free") # free, pro, scale, cancelled
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    """Book translation project table."""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Book metadata
    title = Column(String(500), nullable=False)
    author = Column(String(255), nullable=True)
    source_language = Column(String(10), default="auto")  # ISO 639-1 code or 'auto' for detection
    target_language = Column(String(10), default="en")  # Target language for translation
    source_language_detected = Column(String(10), nullable=True)  # Actual detected language
    source_language_confidence = Column(Float, nullable=True)  # Detection confidence (0-1)
    book_context = Column(Text, nullable=True)  # Global context for translations
    
    # Status
    status = Column(Enum(ProjectStatus, values_callable=lambda obj: [e.value for e in obj]), default=ProjectStatus.CREATED, nullable=False)
    total_pages = Column(Integer, default=0)
    completed_pages = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="projects")
    pages = relationship("Page", back_populates="project", cascade="all, delete-orphan")


class Page(Base):
    """Individual page within a project."""
    __tablename__ = "pages"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # Page info
    page_number = Column(Integer, nullable=False)
    
    # File paths (relative to GCS bucket)
    original_image_path = Column(String(500), nullable=False)  # GCS path to original image
    output_pdf_path = Column(String(500), nullable=True)  # GCS path to translated PDF
    
    # Processing results
    status = Column(Enum(PageStatus, values_callable=lambda obj: [e.value for e in obj]), default=PageStatus.UPLOADED, nullable=False)
    ocr_text = Column(Text, nullable=True)  # Original OCR text
    translated_text = Column(Text, nullable=True)  # Translated text
    error_message = Column(Text, nullable=True)  # Error if processing failed

    # Quality verification
    quality_score = Column(Integer, nullable=True)  # 0-100 quality score
    quality_level = Column(String(50), nullable=True)  # Excellent, Good, Acceptable, Poor, Failed
    quality_issues = Column(Text, nullable=True)  # JSON array of quality issues
    quality_recommendations = Column(Text, nullable=True)  # JSON array of recommendations

    # Language detection (per-page)
    detected_language = Column(String(10), nullable=True)  # Detected language for this page
    language_confidence = Column(Float, nullable=True)  # Detection confidence (0-1)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    replaced_at = Column(DateTime(timezone=True), nullable=True)  # When image was last replaced

    # Relationships
    project = relationship("Project", back_populates="pages")
