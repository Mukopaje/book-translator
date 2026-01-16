"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


# Enums
class ProjectStatusEnum(str, Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PageStatusEnum(str, Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# User schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_admin: int
    total_credits: int
    used_credits: int
    subscription_status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Project schemas
class ProjectCreate(BaseModel):
    title: str
    author: Optional[str] = None
    source_language: str = "auto"  # 'auto' for detection, or specific ISO code
    target_language: str = "en"
    book_context: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    book_context: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    user_id: int
    title: str
    author: Optional[str]
    source_language: str
    target_language: str
    source_language_detected: Optional[str] = None
    source_language_confidence: Optional[float] = None
    book_context: Optional[str]
    status: ProjectStatusEnum
    total_pages: int
    completed_pages: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int


# Page schemas
class PageUpload(BaseModel):
    page_number: int


class PageUpdate(BaseModel):
    status: Optional[str] = None
    ocr_text: Optional[str] = None
    translated_text: Optional[str] = None
    output_pdf_path: Optional[str] = None


class PageResponse(BaseModel):
    id: int
    project_id: int
    page_number: int
    status: PageStatusEnum
    original_image_path: str
    output_pdf_path: Optional[str]
    ocr_text: Optional[str]
    translated_text: Optional[str]
    error_message: Optional[str]
    quality_score: Optional[int] = None
    quality_level: Optional[str] = None
    quality_issues: Optional[str] = None
    quality_recommendations: Optional[str] = None
    detected_language: Optional[str] = None
    language_confidence: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime]
    processed_at: Optional[datetime]
    replaced_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PageListResponse(BaseModel):
    pages: List[PageResponse]
    total: int
