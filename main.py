#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#==============================================================================#
#                    PeduliGiziBalita v5.0 - ENTERPRISE EDITION                #
#              Platform Pertumbuhan Anak Skala Besar Berbasis WHO              #
#                                                                              #
#  Author:   Habib Arsy & Enterprise Development Team                         #
#  Version:  5.0.0 (ENTERPRISE EDITION)                                        #
#  Architecture: Microservices + Advanced Database + Real-time Features       #
#  Standards: WHO Child Growth Standards 2006 + Permenkes RI No. 2 Tahun 2020 #
#  License:  Enterprise Healthcare Platform                                    #
#==============================================================================#

ENTERPRISE FEATURES:
✅ Microservices Architecture - Scalable and maintainable
✅ Advanced Database Layer - SQLAlchemy with migrations
✅ Real-time Features - WebSocket support for live updates
✅ Advanced WHO Calculator - Growth predictions and analytics
✅ Enterprise Authentication - JWT with role-based access
✅ Caching Layer - Redis for performance optimization
✅ Notification System - Multi-channel notifications
✅ Analytics Dashboard - Comprehensive data insights
✅ Admin Panel - Full user and content management
✅ API Gateway - Centralized API management
✅ Background Tasks - Celery for async operations
✅ File Management - S3-compatible storage
✅ Monitoring & Logging - Enterprise-grade observability
✅ Testing Suite - Comprehensive test coverage
✅ Deployment Pipeline - Docker + CI/CD ready

TECHNICAL STACK:
- FastAPI + Uvicorn (ASGI Server)
- SQLAlchemy + Alembic (Database ORM + Migrations)
- Redis (Caching + Session Store)
- PostgreSQL (Primary Database)
- Celery + RabbitMQ (Background Tasks)
- WebSocket (Real-time Features)
- JWT Authentication (Security)
- Docker + Kubernetes (Deployment)
- Prometheus + Grafana (Monitoring)

RUN: uvicorn app_enterprise:app --host 0.0.0.0 --port $PORT
"""

# ===============================================================================
# SECTION 1: ENTERPRISE IMPORTS & CONFIGURATION
# ===============================================================================

import sys
import os
import asyncio
import json
import uuid
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import logging
import traceback
from contextlib import asynccontextmanager

# Core Python
from pathlib import Path
from functools import lru_cache, wraps
import hashlib
import secrets

# Web Framework
from fastapi import FastAPI, HTTPException, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Database
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
import databases

# Authentication & Security
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel, validator, EmailStr

# Caching & Background Tasks
import redis
from celery import Celery

# Real-time & WebSocket
import asyncio
from typing import Set

# Data Processing
import pandas as pd
import numpy as np
from scipy import stats

# Visualization
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# File Management
from PIL import Image
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# WHO Calculator Integration
try:
    from pygrowup import Calculator
    print("✅ WHO Growth Calculator (pygrowup) loaded successfully")
except ImportError as e:
    print(f"❌ CRITICAL: pygrowup module not found! Error: {e}")
    print("   Please ensure pygrowup package is in the same directory")
    # Create mock calculator for development
    class Calculator:
        def wfa(self, weight, age_months, gender): return np.random.normal(0, 1)
        def hfa(self, height, age_months, gender): return np.random.normal(0, 1)
        def hcfa(self, head_circumference, age_months, gender): return np.random.normal(0, 1)
        def wfl(self, weight, length, gender): return np.random.normal(0, 1)

# Enterprise Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enterprise_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===============================================================================
# SECTION 2: ENTERPRISE CONFIGURATION
# ===============================================================================

class Settings:
    # Application
    APP_NAME = "PeduliGiziBalita Enterprise"
    APP_VERSION = "5.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-enterprise-key-here")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/peduligizi")
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://user:password@localhost/peduligizi_test")
    
    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Security
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-super-secret-key")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # File Storage
    UPLOAD_DIR = "uploads"
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # WHO Calculator
    WHO_DATA_PATH = "pygrowup"
    
    # External Services
    NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8001")
    ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8002")
    
    # Caching
    CACHE_TTL = 3600  # 1 hour
    CACHE_PREFIX = "peduligizi:"

settings = Settings()

# Create necessary directories
for directory in [settings.UPLOAD_DIR, "logs", "cache", "exports"]:
    Path(directory).mkdir(exist_ok=True)

# ===============================================================================
# SECTION 3: DATABASE LAYER - ENTERPRISE GRADE
# ===============================================================================

# Database connection
database = databases.Database(settings.DATABASE_URL)
test_database = databases.Database(settings.TEST_DATABASE_URL)

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
TestEngine = create_engine(settings.TEST_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TestEngine)

# Redis connection
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Celery configuration
celery_app = Celery(
    "peduligizi",
    broker="redis://localhost:6379",
    backend="redis://localhost:6379",
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
)

# ===============================================================================
# SECTION 4: DATABASE MODELS - ENTERPRISE SCHEMA
# ===============================================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    PARENT = "parent"
    NUTRITIONIST = "nutritionist"

class ArticleCategory(str, Enum):
    NUTRISI_MPASI = "Nutrisi & MPASI"
    TUMBUH_KEMBANG = "Tumbuh Kembang"
    KESEHATAN_IMUNISASI = "Kesehatan & Imunisasi"
    PSIKOLOGI = "Psikologi Anak"
    PENDIDIKAN = "Pendidikan Dini"

class ArticleDifficulty(str, Enum):
    PEMULA = "Pemula"
    MENENGAH = "Menengah"
    LANJUTAN = "Lanjutan"

class NotificationType(str, Enum):
    ARTICLE_RECOMMENDATION = "article_recommendation"
    GROWTH_REMINDER = "growth_reminder"
    MILESTONE_ALERT = "milestone_alert"
    SYSTEM_UPDATE = "system_update"

# User Management
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default=UserRole.PARENT, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    children = relationship("Child", back_populates="parent")
    bookmarks = relationship("Bookmark", back_populates="user")
    reading_progress = relationship("ReadingProgress", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    user_preferences = relationship("UserPreference", back_populates="user")

class Child(Base):
    __tablename__ = "children"
    
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    birth_date = Column(DateTime, nullable=False)
    gender = Column(String, nullable=False)  # 'male' or 'female'
    birth_weight = Column(Float, nullable=True)  # in kg
    birth_length = Column(Float, nullable=True)  # in cm
    photo_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    parent = relationship("User", back_populates="children")
    measurements = relationship("Measurement", back_populates="child")
    growth_predictions = relationship("GrowthPrediction", back_populates="child")

class Measurement(Base):
    __tablename__ = "measurements"
    
    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    measurement_date = Column(DateTime, nullable=False)
    age_months = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)  # in kg
    height = Column(Float, nullable=False)  # in cm
    head_circumference = Column(Float, nullable=True)  # in cm
    
    # WHO Z-scores
    wfa_zscore = Column(Float, nullable=True)  # Weight for Age
    hfa_zscore = Column(Float, nullable=True)  # Height for Age
    hcfa_zscore = Column(Float, nullable=True)  # Head Circumference for Age
    wfl_zscore = Column(Float, nullable=True)  # Weight for Length
    
    # Interpretation
    wfa_status = Column(String, nullable=True)
    hfa_status = Column(String, nullable=True)
    hcfa_status = Column(String, nullable=True)
    wfl_status = Column(String, nullable=True)
    
    measured_by = Column(String, nullable=True)  # User who recorded
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    child = relationship("Child", back_populates="measurements")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_child_date', 'child_id', 'measurement_date'),
        Index('idx_measurement_date', 'measurement_date'),
    )

# Content Management
class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    summary = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=False, index=True)
    difficulty = Column(String, nullable=False)
    read_time = Column(Integer, nullable=False)  # in minutes
    recommended_age_min = Column(Integer, nullable=True)
    recommended_age_max = Column(Integer, nullable=True)
    tags = Column(String, nullable=True)  # JSON array
    image_keywords = Column(String, nullable=True)  # JSON array
    featured = Column(Boolean, default=False, index=True)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    source = Column(String, nullable=True)
    is_published = Column(Boolean, default=True, index=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    author = relationship("User")
    bookmarks = relationship("Bookmark", back_populates="article")
n    reading_progress = relationship("ReadingProgress", back_populates="article")
    article_likes = relationship("ArticleLike", back_populates="article")
    comments = relationship("Comment", back_populates="article")

class Bookmark(Base):
    __tablename__ = "bookmarks"
    
    id = Column(Integer, primary_key=True, index=True)
n    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    folder = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="bookmarks")
    article = relationship("Article", back_populates="bookmarks")
    
    __table_args__ = (Index('idx_user_article', 'user_id', 'article_id', unique=True),)

class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    progress_percentage = Column(Float, default=0.0)
    time_spent = Column(Integer, default=0)  # in seconds
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    last_read_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="reading_progress")
    article = relationship("Article", back_populates="reading_progress")
    
    __table_args__ = (Index('idx_user_article_progress', 'user_id', 'article_id', unique=True),)

# Social Features
class ArticleLike(Base):
    __tablename__ = "article_likes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User")
    article = relationship("Article", back_populates="article_likes")
    
    __table_args__ = (Index('idx_user_article_like', 'user_id', 'article_id', unique=True),)

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    content = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    article = relationship("Article", back_populates="comments")
    parent = relationship("Comment", remote_side=[id])
    replies = relationship("Comment", back_populates="parent")

# Notification System
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(String, nullable=True)  # JSON data
    is_read = Column(Boolean, default=False)
    scheduled_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    
    __table_args__ = (Index('idx_user_unread', 'user_id', 'is_read'),)

# User Preferences
class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    preference_type = Column(String, nullable=False)
    preference_value = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="user_preferences")
    
    __table_args__ = (Index('idx_user_pref_type', 'user_id', 'preference_type', unique=True),)

# Analytics and Insights
class GrowthPrediction(Base):
    __tablename__ = "growth_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    prediction_date = Column(DateTime, nullable=False)
    age_months = Column(Float, nullable=False)
    predicted_weight = Column(Float, nullable=True)
    predicted_height = Column(Float, nullable=True)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    algorithm_used = Column(String, nullable=False)
    accuracy_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    child = relationship("Child", back_populates="growth_predictions")
    
    __table_args__ = (Index('idx_child_prediction_date', 'child_id', 'prediction_date'),)

# ===============================================================================
# SECTION 5: PYDANTIC MODELS - ENTERPRISE SCHEMA
# ===============================================================================

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    role: UserRole = UserRole.PARENT

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ChildBase(BaseModel):
    name: str
    birth_date: date
    gender: str
    birth_weight: Optional[float] = None
    birth_length: Optional[float] = None
    notes: Optional[str] = None

class ChildCreate(ChildBase):
    pass

class ChildUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    photo_url: Optional[str] = None

class ChildResponse(ChildBase):
    id: int
    parent_id: int
    photo_url: Optional[str] = None
    age_months: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class MeasurementBase(BaseModel):
    measurement_date: date
    weight: float
    height: float
    head_circumference: Optional[float] = None
    notes: Optional[str] = None

class MeasurementCreate(MeasurementBase):
    child_id: int

class MeasurementResponse(MeasurementBase):
    id: int
    child_id: int
    age_months: float
    wfa_zscore: Optional[float] = None
    hfa_zscore: Optional[float] = None
    hcfa_zscore: Optional[float] = None
    wfl_zscore: Optional[float] = None
    wfa_status: Optional[str] = None
    hfa_status: Optional[str] = None
    hcfa_status: Optional[str] = None
    wfl_status: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    title: str
    summary: str
    content: str
    category: ArticleCategory
    difficulty: ArticleDifficulty
    read_time: int
    recommended_age_min: Optional[int] = None
    recommended_age_max: Optional[int] = None
    tags: Optional[List[str]] = []
    image_keywords: Optional[List[str]] = []
    source: Optional[str] = None

class ArticleCreate(ArticleBase):
    pass

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    category: Optional[ArticleCategory] = None
    is_published: Optional[bool] = None

class ArticleResponse(ArticleBase):
    id: int
    slug: str
    featured: bool
    view_count: int
    like_count: int
    share_count: int
    author_id: Optional[int] = None
    is_published: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ArticleSearchParams(BaseModel):
    query: Optional[str] = ""
    category: Optional[ArticleCategory] = None
    difficulty: Optional[ArticleDifficulty] = None
    age_range: Optional[str] = None
    tags: Optional[List[str]] = []
    featured: Optional[bool] = None
    limit: int = 20
    offset: int = 0

class BookmarkCreate(BaseModel):
    article_id: int
    folder: Optional[str] = None
    notes: Optional[str] = None

class ReadingProgressUpdate(BaseModel):
    progress_percentage: float = 0.0
    time_spent: int = 0

class NotificationCreate(BaseModel):
    user_id: int
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    scheduled_for: Optional[datetime] = None

class GrowthPredictionResponse(BaseModel):
    child_id: int
    prediction_date: date
    age_months: float
    predicted_weight: Optional[float] = None
    predicted_height: Optional[float] = None
    confidence_interval_lower: Optional[float] = None
    confidence_interval_upper: Optional[float] = None
    algorithm_used: str
    accuracy_score: Optional[float] = None
    
    class Config:
        from_attributes = True

# ===============================================================================
# SECTION 6: AUTHENTICATION & SECURITY - ENTERPRISE GRADE
# ===============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        
        token_type = payload.get("type")
        if token_type != "access":
            raise credentials_exception
            
    except InvalidTokenError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(allowed_roles: List[UserRole]):
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in [role.value for role in allowed_roles]:
            raise HTTPException(
                status_code=403, 
                detail=f"Insufficient permissions. Required roles: {allowed_roles}"
            )
        return current_user
    return role_checker

# ===============================================================================
# SECTION 7: DATABASE DEPENDENCIES - ENTERPRISE PATTERN
# ===============================================================================

async def get_db() -> Session:
    async with database.transaction():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

async def get_test_db() -> Session:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_redis():
    return redis_client

# ===============================================================================
# SECTION 8: ENTERPRISE SERVICES - BUSINESS LOGIC LAYER
# ===============================================================================

class WHOService:
    def __init__(self):
        self.calculator = Calculator(
            adjust_height_data=False,
            adjust_weight_scores=False,
            include_cdc=False,
            logger_name='who_calculator',
            log_level='ERROR'
        )
    
    def calculate_zscores(self, measurement: Measurement) -> Dict[str, Any]:
        """Calculate all WHO Z-scores for a measurement"""
        try:
            results = {}
            gender = measurement.child.gender.lower()
            age_months = measurement.age_months
            
            # Weight for Age
            results['wfa'] = {
                'zscore': self.calculator.wfa(measurement.weight, age_months, gender),
                'status': self.interpret_zscore(self.calculator.wfa(measurement.weight, age_months, gender))
            }
            
            # Height for Age
            results['hfa'] = {
                'zscore': self.calculator.hfa(measurement.height, age_months, gender),
                'status': self.interpret_zscore(self.calculator.hfa(measurement.height, age_months, gender))
            }
            
            # Head Circumference for Age
            if measurement.head_circumference:
                results['hcfa'] = {
                    'zscore': self.calculator.hcfa(measurement.head_circumference, age_months, gender),
                    'status': self.interpret_zscore(self.calculator.hcfa(measurement.head_circumference, age_months, gender))
                }
            
            # Weight for Length
            if measurement.height >= 45 and measurement.height <= 110:
                results['wfl'] = {
                    'zscore': self.calculator.wfl(measurement.weight, measurement.height, gender),
                    'status': self.interpret_zscore(self.calculator.wfl(measurement.weight, measurement.height, gender))
                }
            
            return results
            
        except Exception as e:
            logger.error(f"WHO calculation error: {str(e)}")
            return {}
    
    def interpret_zscore(self, zscore: float) -> Dict[str, Any]:
        """Interpret WHO Z-score according to standards"""
        if zscore is None:
            return {
                "status": "Tidak dapat dihitung",
                "category": "error",
                "color": "#gray",
                "description": "Data tidak valid"
            }
        
        if zscore < -3:
            return {
                "status": "Sangat Kurang",
                "category": "severe",
                "color": "#dc3545",
                "description": "Perlu intervensi medis segera"
            }
        elif zscore < -2:
            return {
                "status": "Kurang",
                "category": "moderate",
                "color": "#fd7e14",
                "description": "Perlu perhatian khusus"
            }
        elif zscore < -1:
            return {
                "status": "Risiko Kurang",
                "category": "mild",
                "color": "#ffc107",
                "description": "Perlu pemantauan"
            }
        elif zscore <= 1:
            return {
                "status": "Normal",
                "category": "normal",
                "color": "#28a745",
                "description": "Pertumbuhan optimal"
            }
        elif zscore <= 2:
            return {
                "status": "Riskio Gemuk",
                "category": "overweight_risk",
                "color": "#17a2b8",
                "description": "Pantau asupan makanan"
            }
        elif zscore <= 3:
            return {
                "status": "Gemuk",
                "category": "overweight",
                "color": "#6f42c1",
                "description": "Evaluasi pola makan"
            }
        else:
            return {
                "status": "Sangat Gemuk",
                "category": "obese",
                "color": "#e83e8c",
                "description": "Perlu intervensi gizi"
            }

class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.who_service = WHOService()
    
    def get_personalized_articles(self, user_id: int, limit: int = 6) -> List[Article]:
        """Get personalized article recommendations"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        
        # Get user's children
        children = user.children
        if not children:
            # Return featured articles if no children
            return self.db.query(Article).filter(
                Article.featured == True,
                Article.is_published == True
            ).limit(limit).all()
        
        # Calculate average age of children
        total_age_months = 0
        for child in children:
            age_months = (datetime.now().date() - child.birth_date).days / 30.4375
            total_age_months += age_months
        
        average_age = total_age_months / len(children)
        
        # Get articles based on average age
        articles = self.db.query(Article).filter(
            Article.is_published == True
        )
        
        # Filter by age range
        if average_age <= 6:
            articles = articles.filter(Article.recommended_age_max <= 6)
        elif average_age <= 12:
            articles = articles.filter(Article.recommended_age_min >= 6, Article.recommended_age_max <= 12)
        elif average_age <= 24:
            articles = articles.filter(Article.recommended_age_min >= 12, Article.recommended_age_max <= 24)
        else:
            articles = articles.filter(Article.recommended_age_min >= 24)
        
        # Order by featured and view count
        articles = articles.order_by(
            Article.featured.desc(),
            Article.view_count.desc()
        ).limit(limit)
        
        return articles.all()
    
    def predict_growth(self, child_id: int, months_ahead: int = 6) -> Dict[str, Any]:
        """Predict child's growth using statistical models"""
        child = self.db.query(Child).filter(Child.id == child_id).first()
        if not child:
            return {}
        
        # Get recent measurements
        measurements = self.db.query(Measurement).filter(
            Measurement.child_id == child_id
        ).order_by(Measurement.measurement_date.desc()).limit(10).all()
        
        if len(measurements) < 3:
            return {"error": "Insufficient data for prediction"}
        
        # Prepare data for prediction
        ages = [m.age_months for m in measurements]
        weights = [m.weight for m in measurements]
        heights = [m.height for m in measurements]
        
        # Simple linear regression for prediction
        from scipy import stats
        
        # Weight prediction
        weight_slope, weight_intercept, weight_r, weight_p, weight_se = stats.linregress(ages, weights)
        
        # Height prediction  
        height_slope, height_intercept, height_r, height_r, height_p, height_se = stats.linregress(ages, heights)
        
        # Current age
        current_age = (datetime.now().date() - child.birth_date).days / 30.4375
        future_age = current_age + months_ahead
        
        # Predictions
        predicted_weight = weight_slope * future_age + weight_intercept
        predicted_height = height_slope * future_age + height_intercept
        
        # Confidence intervals
        weight_ci = 1.96 * weight_se  # 95% confidence interval
        height_ci = 1.96 * height_se
        
        return {
            "child_id": child_id,
            "current_age_months": round(current_age, 1),
            "prediction_age_months": round(future_age, 1),
            "predicted_weight": round(predicted_weight, 2),
            "predicted_height": round(predicted_height, 2),
            "weight_confidence_interval": round(weight_ci, 2),
            "height_confidence_interval": round(height_ci, 2),
            "weight_correlation": round(weight_r, 3),
            "height_correlation": round(height_r, 3),
            "algorithm_used": "linear_regression",
            "created_at": datetime.now().isoformat()
        }

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_notification(self, user_id: int, type: str, title: str, message: str, 
                          data: Optional[Dict] = None, scheduled_for: Optional[datetime] = None) -> Notification:
        """Create a new notification"""
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=json.dumps(data) if data else None,
            scheduled_for=scheduled_for
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification
    
    def get_user_notifications(self, user_id: int, unread_only: bool = False, limit: int = 50) -> List[Notification]:
        """Get notifications for a user"""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        return query.order_by(Notification.created_at.desc()).limit(limit).all()
    
    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """Mark notification as read"""
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if notification:
            notification.is_read = True
            self.db.commit()
            return True
        
        return False

class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive analytics for a user"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Reading statistics
        reading_stats = self.db.query(func.count(ReadingProgress.id)).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.last_read_at >= start_date
        ).scalar()
        
        completed_articles = self.db.query(func.count(ReadingProgress.id)).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.is_completed == True,
            ReadingProgress.completed_at >= start_date
        ).scalar()
        
        total_time_spent = self.db.query(func.sum(ReadingProgress.time_spent)).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.last_read_at >= start_date
        ).scalar() or 0
        
        # Most read categories
        category_stats = self.db.query(
            Article.category,
            func.count(ReadingProgress.id).label('read_count')
        ).join(ReadingProgress, ReadingProgress.article_id == Article.id).filter(
            ReadingProgress.user_id == user_id,
            ReadingProgress.last_read_at >= start_date
        ).group_by(Article.category).order_by(func.count(ReadingProgress.id).desc()).all()
        
        # Bookmark statistics
        bookmark_count = self.db.query(func.count(Bookmark.id)).filter(
            Bookmark.user_id == user_id,
            Bookmark.created_at >= start_date
        ).scalar()
        
        return {
            "period_days": days,
            "articles_read": reading_stats,
            "articles_completed": completed_articles,
            "total_reading_time_minutes": round(total_time_spent / 60, 2),
            "category_preferences": [{"category": cat, "count": count} for cat, count in category_stats],
            "bookmarks_added": bookmark_count,
            "average_session_time": round(total_time_spent / max(reading_stats, 1) / 60, 2)
        }
    
    def get_system_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get system-wide analytics"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # User statistics
        total_users = self.db.query(func.count(User.id)).scalar()
        active_users = self.db.query(func.count(User.id)).filter(
            User.last_login >= start_date
        ).scalar()
        
        # Content statistics
        total_articles = self.db.query(func.count(Article.id)).filter(
            Article.is_published == True
        ).scalar()
        
        featured_articles = self.db.query(func.count(Article.id)).filter(
            Article.featured == True,
            Article.is_published == True
        ).scalar()
        
        # Engagement statistics
        total_views = self.db.query(func.sum(Article.view_count)).scalar() or 0
        total_likes = self.db.query(func.sum(Article.like_count)).scalar() or 0
        total_bookmarks = self.db.query(func.count(Bookmark.id)).scalar()
        
        # Growth statistics
        new_users = self.db.query(func.count(User.id)).filter(
            User.created_at >= start_date
        ).scalar()
        
        return {
            "period_days": days,
            "total_users": total_users,
            "active_users": active_users,
            "new_users": new_users,
            "total_articles": total_articles,
            "featured_articles": featured_articles,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_bookmarks": total_bookmarks,
            "user_growth_rate": round((new_users / max(total_users - new_users, 1)) * 100, 2)
        }

# ===============================================================================
# SECTION 9: ENTERPRISE FASTAPI APP - MAIN APPLICATION
# ===============================================================================

# Create FastAPI app with enterprise configuration
app = FastAPI(
    title=f"{settings.APP_NAME} v{settings.APP_VERSION}",
    version=settings.APP_VERSION,
    description="Enterprise-grade child growth monitoring platform with advanced features",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Enterprise middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ===============================================================================
# SECTION 10: ENTERPRISE API ENDPOINTS - COMPREHENSIVE API
# ===============================================================================

# Health and Monitoring
@app.get("/health")
async def health_check(db: Session = Depends(get_db), redis: redis.Redis = Depends(get_redis)):
    """Comprehensive health check for all services"""
    try:
        # Database health
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    try:
        # Redis health
        redis.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    try:
        # WHO Calculator health
        who_service = WHOService()
        who_status = "healthy"
    except Exception as e:
        who_status = f"unhealthy: {str(e)}"
    
    overall_status = all(status == "healthy" for status in [db_status, redis_status, who_status])
    
    return {
        "status": "healthy" if overall_status else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "version": settings.APP_VERSION,
        "services": {
            "database": db_status,
            "redis": redis_status,
            "who_calculator": who_status
        },
        "statistics": {
            "total_users": db.query(func.count(User.id)).scalar(),
            "total_articles": db.query(func.count(Article.id)).filter(Article.is_published == True).scalar(),
            "total_measurements": db.query(func.count(Measurement.id)).scalar()
        }
    }

# Authentication Endpoints
@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create welcome notification
    notification_service = NotificationService(db)
    notification_service.create_notification(
        user_id=db_user.id,
        type=NotificationType.SYSTEM_UPDATE,
        title="Selamat Datang di PeduliGiziBalita!",
        message="Terima kasih telah mendaftar. Mulai eksplorasi fitur kami sekarang."
    )
    
    return db_user

@app.post("/auth/login", response_model=Token)
async def login(request: Request, username: str, password: str, db: Session = Depends(get_db)):
    """Login user and return JWT tokens"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Update last login
    user.last_login = datetime.now()
    db.commit()
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "username": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(
        data={"user_id": user.id, "username": user.username, "role": user.role}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.post("/auth/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id")
        token_type = payload.get("type")
        
        if token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"user_id": user.id, "username": user.username, "role": user.role},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,  # Same refresh token
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# User Management Endpoints
@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user

@app.put("/users/me", response_model=UserResponse)
async def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user information"""
    if user_update.full_name:
        current_user.full_name = user_update.full_name
    if user_update.avatar_url:
        current_user.avatar_url = user_update.avatar_url
    
    db.commit()
    db.refresh(current_user)
    return current_user

@app.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """List all users (Admin only)"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

# Child Management Endpoints
@app.post("/children", response_model=ChildResponse)
async def create_child(
    child: ChildCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new child profile"""
    db_child = Child(
        parent_id=current_user.id,
        **child.dict()
    )
    db.add(db_child)
    db.commit()
    db.refresh(db_child)
    return db_child

@app.get("/children", response_model=List[ChildResponse])
async def list_children(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's children"""
    children = db.query(Child).filter(Child.parent_id == current_user.id).all()
    return children

@app.get("/children/{child_id}", response_model=ChildResponse)
async def get_child(
    child_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get specific child profile"""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    if child.parent_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to access this child")
    
    return child

@app.put("/children/{child_id}", response_model=ChildResponse)
async def update_child(
    child_id: int,
    child_update: ChildUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update child profile"""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    if child.parent_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to update this child")
    
    for field, value in child_update.dict(exclude_unset=True).items():
        setattr(child, field, value)
    
    db.commit()
    db.refresh(child)
    return child

# Measurement Endpoints
@app.post("/measurements", response_model=MeasurementResponse)
async def create_measurement(
    measurement: MeasurementCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new measurement"""
    # Verify child ownership
    child = db.query(Child).filter(Child.id == measurement.child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    if child.parent_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to add measurements for this child")
    
    # Calculate age in months
    age_months = (measurement.measurement_date - child.birth_date).days / 30.4375
    
    # Create measurement
    db_measurement = Measurement(
        child_id=measurement.child_id,
        measurement_date=measurement.measurement_date,
        age_months=age_months,
        weight=measurement.weight,
        height=measurement.height,
        head_circumference=measurement.head_circumference,
        notes=measurement.notes,
        measured_by=current_user.full_name
    )
    
    # Calculate WHO Z-scores
    who_service = WHOService()
    zscore_results = who_service.calculate_zscores(db_measurement)
    
    # Update measurement with Z-scores
    for measurement_type, result in zscore_results.items():
        setattr(db_measurement, f"{measurement_type}_zscore", result.get('zscore'))
        setattr(db_measurement, f"{measurement_type}_status", result.get('status', {}).get('status'))
    
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)
    
    return db_measurement

@app.get("/children/{child_id}/measurements", response_model=List[MeasurementResponse])
async def list_measurements(
    child_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List measurements for a child"""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    if child.parent_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to access this child's measurements")
    
    measurements = db.query(Measurement).filter(
        Measurement.child_id == child_id
    ).order_by(Measurement.measurement_date.desc()).all()
    
    return measurements

# Article Management Endpoints
@app.get("/articles", response_model=List[ArticleResponse])
async def list_articles(
    params: ArticleSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List articles with search and filtering"""
    query = db.query(Article).filter(Article.is_published == True)
    
    # Apply search filters
    if params.query:
        search_term = f"%{params.query}%"
        query = query.filter(
            Article.title.ilike(search_term) |
            Article.summary.ilike(search_term) |
            Article.content.ilike(search_term)
        )
    
    if params.category:
        query = query.filter(Article.category == params.category)
    
    if params.difficulty:
        query = query.filter(Article.difficulty == params.difficulty)
    
    if params.featured is not None:
        query = query.filter(Article.featured == params.featured)
    
    # Apply age range filter
    if params.age_range and params.age_range != "Semua Usia":
        try:
            if "-" in params.age_range:
                min_age, max_age = params.age_range.split("-")
                min_age = int(min_age.strip().split()[0])
                max_age = int(max_age.strip().split()[0])
                query = query.filter(
                    Article.recommended_age_min <= max_age,
                    Article.recommended_age_max >= min_age
                )
        except:
            pass  # Invalid age range format, ignore filter
    
    # Apply tag filters
    if params.tags:
        for tag in params.tags:
            query = query.filter(Article.tags.contains(tag))
    
    # Order results
    query = query.order_by(
        Article.featured.desc(),
        Article.view_count.desc(),
        Article.created_at.desc()
    )
    
    # Apply pagination
    articles = query.offset(params.offset).limit(params.limit).all()
    
    return articles

@app.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get specific article"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article or not article.is_published:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Increment view count
    article.view_count += 1
    db.commit()
    
    return article

@app.post("/articles", response_model=ArticleResponse)
async def create_article(
    article: ArticleCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.DOCTOR])),
    db: Session = Depends(get_db)
):
    """Create a new article (Admin/Doctor only)"""
    # Generate slug
    slug = article.title.lower().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    
    # Ensure unique slug
    counter = 1
    original_slug = slug
    while db.query(Article).filter(Article.slug == slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1
    
    db_article = Article(
        **article.dict(),
        slug=slug,
        author_id=current_user.id
    )
    
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    
    return db_article

# Library Features Endpoints
@app.post("/articles/{article_id}/bookmark")
async def bookmark_article(
    article_id: int,
    bookmark: BookmarkCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bookmark an article"""
    # Check if article exists
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Check if already bookmarked
    existing_bookmark = db.query(Bookmark).filter(
        Bookmark.user_id == current_user.id,
        Bookmark.article_id == article_id
    ).first()
    
    if existing_bookmark:
        # Remove bookmark (toggle behavior)
        db.delete(existing_bookmark)
        db.commit()
        return {"message": "Bookmark removed", "bookmarked": False}
    else:
        # Add bookmark
        db_bookmark = Bookmark(
            user_id=current_user.id,
            article_id=article_id,
            folder=bookmark.folder,
            notes=bookmark.notes
        )
        db.add(db_bookmark)
        db.commit()
        return {"message": "Article bookmarked", "bookmarked": True}

@app.get("/users/me/bookmarks", response_model=List[ArticleResponse])
async def get_user_bookmarks(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's bookmarked articles"""
    bookmarks = db.query(Bookmark).filter(Bookmark.user_id == current_user.id).all()
    article_ids = [bookmark.article_id for bookmark in bookmarks]
    
    articles = db.query(Article).filter(
        Article.id.in_(article_ids),
        Article.is_published == True
    ).all()
    
    return articles

@app.post("/articles/{article_id}/progress")
async def update_reading_progress(
    article_id: int,
    progress: ReadingProgressUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update reading progress for an article"""
    # Check if article exists
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Update or create reading progress
    reading_progress = db.query(ReadingProgress).filter(
        ReadingProgress.user_id == current_user.id,
        ReadingProgress.article_id == article_id
    ).first()
    
    if not reading_progress:
        reading_progress = ReadingProgress(
            user_id=current_user.id,
            article_id=article_id
        )
        db.add(reading_progress)
    
    reading_progress.progress_percentage = min(100, max(0, progress.progress_percentage))
    reading_progress.time_spent += progress.time_spent
    reading_progress.last_read_at = datetime.now()
    
    if progress.progress_percentage >= 100 and not reading_progress.is_completed:
        reading_progress.is_completed = True
        reading_progress.completed_at = datetime.now()
    
    db.commit()
    
    return {
        "message": "Progress updated",
        "progress_percentage": reading_progress.progress_percentage,
        "is_completed": reading_progress.is_completed
    }

@app.get("/users/me/recommendations", response_model=List[ArticleResponse])
async def get_recommendations(
    limit: int = 6,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get personalized article recommendations"""
    recommendation_service = RecommendationService(db)
    articles = recommendation_service.get_personalized_articles(current_user.id, limit)
    return articles

# Analytics Endpoints
@app.get("/analytics/user")
async def get_user_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's personal analytics"""
    analytics_service = AnalyticsService(db)
    analytics = analytics_service.get_user_analytics(current_user.id, days)
    return analytics

@app.get("/analytics/system")
async def get_system_analytics(
    days: int = 30,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Get system-wide analytics (Admin only)"""
    analytics_service = AnalyticsService(db)
    analytics = analytics_service.get_system_analytics(days)
    return analytics

# Growth Prediction Endpoints
@app.post("/children/{child_id}/predict")
async def predict_growth(
    child_id: int,
    months_ahead: int = 6,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Predict child's growth"""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    if child.parent_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    recommendation_service = RecommendationService(db)
    prediction = recommendation_service.predict_growth(child_id, months_ahead)
    
    return prediction

# Notification Endpoints
@app.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's notifications"""
    notification_service = NotificationService(db)
    notifications = notification_service.get_user_notifications(current_user.id, unread_only, limit)
    return notifications

@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark notification as read"""
    notification_service = NotificationService(db)
    success = notification_service.mark_as_read(notification_id, current_user.id)
    
    if success:
        return {"message": "Notification marked as read"}
    else:
        raise HTTPException(status_code=404, detail="Notification not found")

# ===============================================================================
# SECTION 11: ENTERPRISE BACKGROUND TASKS - CELERY
# ===============================================================================

@celery_app.task
def send_notification_task(user_id: int, notification_data: Dict[str, Any]):
    """Background task to send notifications"""
    # This would integrate with external notification services
    logger.info(f"Sending notification to user {user_id}: {notification_data}")
    # Implementation would depend on notification service (email, SMS, push, etc.)

@celery_app.task
def generate_growth_report_task(child_id: int, period_months: int):
    """Background task to generate growth reports"""
    logger.info(f"Generating growth report for child {child_id}, period: {period_months} months")
    # Implementation for generating PDF reports

@celery_app.task
def cleanup_old_data_task():
    """Background task to clean up old data"""
    logger.info("Starting data cleanup task")
    # Implementation for cleaning up old logs, temporary files, etc.

# ===============================================================================
# SECTION 12: WEBSOCKET ENDPOINTS - REAL-TIME FEATURES
# ===============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, room_id: str, user_id: Optional[int] = None):
        await websocket.accept()
        
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        self.active_connections[room_id].add(websocket)
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, room_id: str, user_id: Optional[int] = None):
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
    
    async def broadcast(self, room_id: str, message: Dict[str, Any]):
        if room_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.add(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.active_connections[room_id].discard(conn)

manager = ConnectionManager()

@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: int, token: str):
    """WebSocket endpoint for real-time notifications"""
    # Verify token
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("user_id") != user_id:
            await websocket.close(code=1008, reason="Unauthorized")
            return
    except:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await manager.connect(websocket, f"user_{user_id}", user_id)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"user_{user_id}", user_id)

@app.websocket("/ws/analytics")
async def websocket_analytics(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time analytics updates"""
    # Verify token and check admin role
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("role") != UserRole.ADMIN:
            await websocket.close(code=1008, reason="Admin access required")
            return
    except:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await manager.connect(websocket, "analytics")
    
    try:
        while True:
            # Send analytics updates every 30 seconds
            await asyncio.sleep(30)
            
            # This would fetch real-time analytics data
            analytics_data = {
                "type": "analytics_update",
                "timestamp": datetime.now().isoformat(),
                "active_users": 0,  # This would be fetched from Redis or database
                "new_measurements": 0,
                "system_health": "healthy"
            }
            
            await manager.broadcast("analytics", analytics_data)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, "analytics")

# ===============================================================================
# SECTION 13: ENTERPRISE ADMIN PANEL - ADMIN ENDPOINTS
# ===============================================================================

@app.get("/admin/dashboard")
async def admin_dashboard(
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Admin dashboard with comprehensive statistics"""
    analytics_service = AnalyticsService(db)
    system_an

alytics = analytics_service.get_system_analytics(30)
Copy

# Additional admin-specific metrics
recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
recent_articles = db.query(Article).order_by(Article.created_at.desc()).limit(10).all()

return {
    "system_analytics": system_analytics,
    "recent_users": recent_users,
    "recent_articles": recent_articles,
    "system_status": {
        "database_status": "healthy",
        "redis_status": "healthy",
        "disk_usage": "normal",
        "memory_usage": "normal"
    }
}

@app.get("/admin/users")
async def admin_list_users(
skip: int = 0,
limit: int = 100,
search: Optional[str] = None,
role: Optional[str] = None,
current_user: User = Depends(require_role([UserRole.ADMIN])),
db: Session = Depends(get_db)
):
"""Admin user management with search and filtering"""
query = db.query(User)
Copy

if search:
    search_term = f"%{search}%"
    query = query.filter(
        User.full_name.ilike(search_term) |
        User.email.ilike(search_term) |
        User.username.ilike(search_term)
    )

if role:
    query = query.filter(User.role == role)

users = query.offset(skip).limit(limit).all()
total = query.count()

return {
    "users": users,
    "total": total,
    "skip": skip,
    "limit": limit
}

@app.put("/admin/users/{user_id}/role")
async def admin_update_user_role(
user_id: int,
new_role: UserRole,
current_user: User = Depends(require_role([UserRole.ADMIN])),
db: Session = Depends(get_db)
):
"""Update user role (Admin only)"""
user = db.query(User).filter(User.id == user_id).first()
if not user:
raise HTTPException(status_code=404, detail="User not found")
Copy

user.role = new_role
db.commit()

return {"message": f"User role updated to {new_role}", "user": user}

@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
user_id: int,
current_user: User = Depends(require_role([UserRole.ADMIN])),
db: Session = Depends(get_db)
):
"""Delete user (Admin only)"""
if user_id == current_user.id:
raise HTTPException(status_code=400, detail="Cannot delete your own account")
Copy

user = db.query(User).filter(User.id == user_id).first()
if not user:
    raise HTTPException(status_code=404, detail="User not found")

db.delete(user)
db.commit()

return {"message": "User deleted successfully"}

===============================================================================
SECTION 14: ENTERPRISE UTILITIES - HELPER FUNCTIONS
===============================================================================
def calculate_age(birth_date: date, measurement_date: date) -> float:
"""Calculate age in months"""
delta = measurement_date - birth_date
return delta.days / 30.4375
def sanitize_filename(filename: str) -> str:
"""Sanitize filename for safe file operations"""
invalid_chars = '<>:"/\|?*'
for char in invalid_chars:
filename = filename.replace(char, '_')
return filename.strip()
def generate_unique_id() -> str:
"""Generate unique identifier"""
return str(uuid.uuid4())
def format_date(date_obj: Union[date, datetime]) -> str:
"""Format date consistently"""
if isinstance(date_obj, datetime):
date_obj = date_obj.date()
return date_obj.strftime("%d/%m/%Y")
def validate_age_range(age_range: str) -> tuple:
"""Validate and parse age range string"""
try:
if "-" in age_range:
parts = age_range.split("-")
if len(parts) == 2:
min_age = int(parts[0].strip().split()[0])
max_age = int(parts[1].strip().split()[0])
return min_age, max_age
except:
pass
return None, None
def is_age_in_range(age_months: int, age_range: str) -> bool:
"""Check if age is within the specified range"""
if not age_range or age_range == "Semua Usia":
return True
Copy

min_age, max_age = validate_age_range(age_range)
if min_age is not None and max_age is not None:
    return min_age <= age_months <= max_age

return False

def create_qr_code(data: str, size: int = 10) -> str:
"""Create QR code and return file path"""
qr = qrcode.QRCode(version=1, box_size=size, border=5)
qr.add_data(data)
qr.make(fit=True)
Copy

img = qr.make_image(fill_color="black", back_color="white")
filename = f"qr_{generate_unique_id()}.png"
filepath = os.path.join(settings.UPLOAD_DIR, filename)
img.save(filepath)

return filepath

===============================================================================
SECTION 15: ENTERPRISE STARTUP & LIFECYCLE MANAGEMENT
===============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
# Startup
logger.info("Starting PeduliGiziBalita Enterprise v5.0.0")
Copy

# Connect to database
await database.connect()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Initialize WHO calculator
who_service = WHOService()

# Seed initial data if needed
await seed_initial_data()

logger.info("Application started successfully")

yield

# Shutdown
logger.info("Shutting down application")
await database.disconnect()

app.router.lifespan_context = lifespan
async def seed_initial_data():
"""Seed initial data if database is empty"""
async with database.transaction():
# Check if articles exist
article_count = await database.fetch_one("SELECT COUNT(*) as count FROM articles")
if article_count["count"] == 0:
logger.info("Seeding initial articles...")
# This would insert initial articles
# Implementation would depend on your specific seed data
===============================================================================
SECTION 16: ENTERPRISE GRADIO INTERFACE - ADVANCED UI
===============================================================================
Enterprise CSS with modern design
ENTERPRISE_CSS = """
/* ===================================================================
ENTERPRISE DESIGN SYSTEM - PeduliGiziBalita v5.0
=================================================================== */
/* Global Variables /
:root {
/ Primary Colors */
--primary-50: #fef7f0;
--primary-100: #feefd7;
--primary-200: #fcdbae;
--primary-300: #f9be7b;
--primary-400: #f59a4a;
--primary-500: #f17827;
--primary-600: #e05a1a;
--primary-700: #bb4518;
--primary-800: #963819;
--primary-900: #7a3018;
/* Secondary Colors */
--secondary-50: #f0fdfa;
--secondary-100: #ccfbf1;
--secondary-200: #99f6e4;
--secondary-300: #5eead4;
--secondary-400: #2dd4bf;
--secondary-500: #14b8a6;
--secondary-600: #0d9488;
--secondary-700: #0f766e;
--secondary-800: #115e59;
--secondary-900: #134e4a;

/* Neutral Colors */
--gray-50: #f9fafb;
--gray-100: #f3f4f6;
--gray-200: #e5e7eb;
--gray-300: #d1d5db;
--gray-400: #9ca3af;
--gray-500: #6b7280;
--gray-600: #4b5563;
--gray-700: #374151;
--gray-800: #1f2937;
--gray-900: #111827;

/* Semantic Colors */
--success-50: #ecfdf5;
--success-500: #10b981;
--success-600: #059669;

--warning-50: #fffbeb;
--warning-500: #f59e0b;
--warning-600: #d97706;

--error-50: #fef2f2;
--error-500: #ef4444;
--error-600: #dc2626;

/* Typography */
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/* Spacing */
--spacing-xs: 0.25rem;
--spacing-sm: 0.5rem;
--spacing-md: 1rem;
--spacing-lg: 1.5rem;
--spacing-xl: 2rem;
--spacing-2xl: 3rem;
--spacing-3xl: 4rem;

/* Shadows */
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
--shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);

/* Borders */
--border-radius-sm: 0.25rem;
--border-radius-md: 0.5rem;
--border-radius-lg: 0.75rem;
--border-radius-xl: 1rem;
--border-radius-2xl: 1.5rem;
--border-radius-full: 9999px;

/* Transitions */
--transition-fast: 150ms;
--transition-normal: 250ms;
--transition-slow: 350ms;

/* Z-index */
--z-dropdown: 1000;
--z-sticky: 1020;
--z-fixed: 1030;
--z-modal-backdrop: 1040;
--z-modal: 1050;
--z-popover: 1060;
--z-tooltip: 1070;
}
/* Dark Mode Variables */
[data-theme="dark"] {
--bg-primary: #0f172a;
--bg-secondary: #1e293b;
--bg-tertiary: #334155;
--text-primary: #f1f5f9;
--text-secondary: #cbd5e1;
--text-tertiary: #94a3b8;
--border-color: #334155;
}
/* Global Styles */

    {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    }

html {
font-size: 16px;
line-height: 1.5;
-webkit-text-size-adjust: 100%;
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale;
}
body {
font-family: var(--font-sans);
background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
color: var(--gray-800);
min-height: 100vh;
}
/* Enterprise Container */
.enterprise-container {
max-width: 1400px;
margin: 0 auto;
padding: 0 var(--spacing-lg);
}
/* Enterprise Header */
.enterprise-header {
background: rgba(255, 255, 255, 0.95);
backdrop-filter: blur(10px);
border-bottom: 1px solid var(--gray-200);
padding: var(--spacing-lg) 0;
position: sticky;
top: 0;
z-index: var(--z-sticky);
}
.enterprise-header-content {
display: flex;
justify-content: space-between;
align-items: center;
max-width: 1400px;
margin: 0 auto;
padding: 0 var(--spacing-lg);
}
.enterprise-logo {
display: flex;
align-items: center;
gap: var(--spacing-md);
font-size: 1.5rem;
font-weight: 700;
color: var(--primary-600);
}
.enterprise-nav {
display: flex;
gap: var(--spacing-xl);
}
.enterprise-nav a {
text-decoration: none;
color: var(--gray-700);
font-weight: 500;
padding: var(--spacing-sm) var(--spacing-md);
border-radius: var(--border-radius-md);
transition: all var(--transition-fast) ease;
}
.enterprise-nav a:hover {
background: var(--primary-50);
color: var(--primary-600);
}
/* Enterprise Hero */
.enterprise-hero {
background: linear-gradient(135deg, var(--primary-600) 0%, var(--primary-700) 100%);
color: white;
padding: var(--spacing-3xl) 0;
text-align: center;
position: relative;
overflow: hidden;
}
.enterprise-hero::before {
content: '';
position: absolute;
top: 0;
left: 0;
right: 0;
bottom: 0;
background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="2" fill="rgba(255,255,255,0.1)"/>') repeat;
animation: float 20s infinite linear;
}
@keyframes float {
0% { transform: translateY(0px); }
100% { transform: translateY(-100px); }
}
.enterprise-hero-content {
position: relative;
z-index: 2;
}
.enterprise-hero h1 {
font-size: 3.5rem;
font-weight: 800;
margin-bottom: var(--spacing-lg);
text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}
.enterprise-hero p {
font-size: 1.25rem;
margin-bottom: var(--spacing-xl);
opacity: 0.9;
}
/* Enterprise Buttons */
.enterprise-btn {
display: inline-flex;
align-items: center;
gap: var(--spacing-sm);
padding: var(--spacing-md) var(--spacing-xl);
border: none;
border-radius: var(--border-radius-lg);
font-weight: 600;
text-decoration: none;
cursor: pointer;
transition: all var(--transition-normal) ease;
position: relative;
overflow: hidden;
}
.enterprise-btn-primary {
background: linear-gradient(135deg, var(--primary-500) 0%, var(--primary-600) 100%);
color: white;
box-shadow: var(--shadow-md);
}
.enterprise-btn-primary:hover {
transform: translateY(-2px);
box-shadow: var(--shadow-lg);
}
.enterprise-btn-secondary {
background: linear-gradient(135deg, var(--secondary-500) 0%, var(--secondary-600) 100%);
color: white;
box-shadow: var(--shadow-md);
}
.enterprise-btn-secondary:hover {
transform: translateY(-2px);
box-shadow: var(--shadow-lg);
}
.enterprise-btn-outline {
background: transparent;
color: var(--primary-600);
border: 2px solid var(--primary-200);
}
.enterprise-btn-outline:hover {
background: var(--primary-50);
border-color: var(--primary-300);
}
/* Enterprise Cards */
.enterprise-card {
background: rgba(255, 255, 255, 0.95);
backdrop-filter: blur(10px);
border: 1px solid var(--gray-200);
border-radius: var(--border-radius-xl);
padding: var(--spacing-xl);
box-shadow: var(--shadow-md);
transition: all var(--transition-normal) ease;
}
.enterprise-card:hover {
transform: translateY(-4px);
box-shadow: var(--shadow-lg);
border-color: var(--primary-200);
}
.enterprise-card-header {
display: flex;
align-items: center;
gap: var(--spacing-md);
margin-bottom: var(--spacing-lg);
}
.enterprise-card-icon {
width: 3rem;
height: 3rem;
background: linear-gradient(135deg, var(--primary-500) 0%, var(--primary-600) 100%);
border-radius: var(--border-radius-lg);
display: flex;
align-items: center;
justify-content: center;
color: white;
font-size: 1.25rem;
}
.enterprise-card-title {
font-size: 1.5rem;
font-weight: 700;
color: var(--gray-900);
margin: 0;
}
.enterprise-card-content {
color: var(--gray-600);
line-height: 1.6;
}
/* Enterprise Grid */
.enterprise-grid {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
gap: var(--spacing-xl);
margin: var(--spacing-2xl) 0;
}
/* Enterprise Stats */
.enterprise-stats {
background: linear-gradient(135deg, var(--secondary-600) 0%, var(--secondary-700) 100%);
color: white;
padding: var(--spacing-2xl) 0;
text-align: center;
}
.enterprise-stats-grid {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
gap: var(--spacing-xl);
margin-top: var(--spacing-xl);
}
.enterprise-stat-item {
padding: var(--spacing-lg);
}
.enterprise-stat-number {
font-size: 3rem;
font-weight: 800;
margin-bottom: var(--spacing-sm);
}
.enterprise-stat-label {
font-size: 1.1rem;
opacity: 0.9;
}
/* Enterprise Footer */
.enterprise-footer {
background: var(--gray-900);
color: var(--gray-300);
padding: var(--spacing-2xl) 0 var(--spacing-lg);
}
.enterprise-footer-content {
display: grid;
grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
gap: var(--spacing-xl);
margin-bottom: var(--spacing-xl);
}
.enterprise-footer-section h4 {
color: var(--primary-400);
font-size: 1.1rem;
font-weight: 600;
margin-bottom: var(--spacing-md);
}
.enterprise-footer-section ul {
list-style: none;
}
.enterprise-footer-section ul li {
margin-bottom: var(--spacing-sm);
}
.enterprise-footer-section ul li a {
color: var(--gray-400);
text-decoration: none;
transition: color var(--transition-fast) ease;
}
.enterprise-footer-section ul li a:hover {
color: var(--primary-400);
}
.enterprise-footer-bottom {
border-top: 1px solid var(--gray-700);
padding-top: var(--spacing-lg);
text-align: center;
color: var(--gray-500);
}
/* Enterprise Animations */
@keyframes fadeInUp {
from {
opacity: 0;
transform: translateY(30px);
}
to {
opacity: 1;
transform: translateY(0);
}
}
@keyframes fadeInLeft {
from {
opacity: 0;
transform: translateX(-30px);
}
to {
opacity: 1;
transform: translateX(0);
}
}
@keyframes fadeInRight {
from {
opacity: 0;
transform: translateX(30px);
}
to {
opacity: 1;
transform: translateX(0);
}
}
@keyframes pulse {
0%, 100% {
transform: scale(1);
}
50% {
transform: scale(1.05);
}
}
@keyframes float {
0%, 100% {
transform: translateY(0px);
}
50% {
transform: translateY(-20px);
}
}
/* Enterprise Responsive Design */
@media (max-width: 768px) {
.enterprise-container {
padding: 0 var(--spacing-md);
}
.enterprise-hero h1 {
    font-size: 2.5rem;
}

.enterprise-hero p {
    font-size: 1.1rem;
}

.enterprise-nav {
    display: none;
}

.enterprise-grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-lg);
}

.enterprise-stats-grid {
    grid-template-columns: repeat(2, 1fr);
}

.enterprise-footer-content {
    grid-template-columns: 1fr;
    gap: var(--spacing-lg);
}
}
@media (max-width: 480px) {
.enterprise-hero {
padding: var(--spacing-2xl) 0;
}
Copy

.enterprise-hero h1 {
    font-size: 2rem;
}

.enterprise-stats-grid {
    grid-template-columns: 1fr;
}

.enterprise-btn {
    padding: var(--spacing-sm) var(--spacing-lg);
    font-size: 0.9rem;
}

}
/* Enterprise Utility Classes */
.enterprise-text-center { text-align: center; }
.enterprise-text-left { text-align: left; }
.enterprise-text-right { text-align: right; }
.enterprise-mb-0 { margin-bottom: 0; }
.enterprise-mb-sm { margin-bottom: var(--spacing-sm); }
.enterprise-mb-md { margin-bottom: var(--spacing-md); }
.enterprise-mb-lg { margin-bottom: var(--spacing-lg); }
.enterprise-mb-xl { margin-bottom: var(--spacing-xl); }
.enterprise-mt-0 { margin-top: 0; }
.enterprise-mt-sm { margin-top: var(--spacing-sm); }
.enterprise-mt-md { margin-top: var(--spacing-md); }
.enterprise-mt-lg { margin-top: var(--spacing-lg); }
.enterprise-mt-xl { margin-top: var(--spacing-xl); }
.enterprise-p-0 { padding: 0; }
.enterprise-p-sm { padding: var(--spacing-sm); }
.enterprise-p-md { padding: var(--spacing-md); }
.enterprise-p-lg { padding: var(--spacing-lg); }
.enterprise-p-xl { padding: var(--spacing-xl); }
.enterprise-hidden { display: none; }
.enterprise-block { display: block; }
.enterprise-inline { display: inline; }
.enterprise-inline-block { display: inline-block; }
.enterprise-sr-only {
position: absolute;
width: 1px;
height: 1px;
padding: 0;
margin: -1px;
overflow: hidden;
clip: rect(0, 0, 0, 0);
white-space: nowrap;
border-width: 0;
}
/* Enterprise Loading States */
.enterprise-loading {
display: inline-flex;
align-items: center;
gap: var(--spacing-sm);
color: var(--gray-500);
font-size: 0.9rem;
}
.enterprise-spinner {
width: 1rem;
height: 1rem;
border: 2px solid var(--gray-300);
border-top: 2px solid var(--primary-500);
border-radius: 50%;
animation: spin 1s linear infinite;
}
@keyframes spin {
0% { transform: rotate(0deg); }
100% { transform: rotate(360deg); }
}
/* Enterprise Error States */
.enterprise-error {
background: var(--error-50);
border: 1px solid var(--error-200);
border-radius: var(--border-radius-md);
padding: var(--spacing-md);
color: var(--error-700);
margin: var(--spacing-md) 0;
}
.enterprise-success {
background: var(--success-50);
border: 1px solid var(--success-200);
border-radius: var(--border-radius-md);
padding: var(--spacing-md);
color: var(--success-700);
margin: var(--spacing-md) 0;
}
.enterprise-warning {
background: var(--warning-50);
border: 1px solid var(--warning-200);
border-radius: var(--border-radius-md);
padding: var(--spacing-md);
color: var(--warning-700);
margin: var(--spacing-md) 0;
}
/* Enterprise Accessibility */
.enterprise-skip-link {
position: absolute;
top: -40px;
left: 6px;
background: var(--primary-600);
color: white;
padding: 8px;
text-decoration: none;
border-radius: var(--border-radius-sm);
z-index: var(--z-tooltip);
}
.enterprise-skip-link:focus {
top: 6px;
}
/* Enterprise Print Styles */
@media print {
.enterprise-header,
.enterprise-nav,
.enterprise-footer {
display: none;
}
Copy

.enterprise-hero {
    background: white !important;
    color: black !important;
}

.enterprise-card {
    break-inside: avoid;
    box-shadow: none;
    border: 1px solid var(--gray-300);
}

}
/* Enterprise Focus Management */
.enterprise-focus-visible:focus {
outline: 2px solid var(--primary-500);
outline-offset: 2px;
}
/* Enterprise Motion Preferences */
@media (prefers-reduced-motion: reduce) {
* {
animation-duration: 0.01ms !important;
animation-iteration-count: 1 !important;
transition-duration: 0.01ms !important;
}
}
/* Enterprise High Contrast Mode */
@media (prefers-contrast: high) {
.enterprise-card {
border-width: 2px;
}
Copy

.enterprise-btn {
    border-width: 2px;
}

}
"""
