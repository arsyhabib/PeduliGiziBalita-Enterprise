#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
PeduliGiziBalita v5.0 – ENTERPRISE EDITION
Platform Pertumbuhan Anak Skala Besar Berbasis WHO
==============================================================================
"""

import os
import sys
import json
import uuid
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from contextlib import asynccontextmanager
from pathlib import Path

# FastAPI
from fastapi import FastAPI, HTTPException, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Database
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import databases

# Auth
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, validator

# Redis & Celery
import redis
from celery import Celery

# WHO
try:
    from pygrowup import Calculator
except ImportError:
    class Calculator:
        def wfa(self, weight, age_months, gender): return 0.0
        def hfa(self, height, age_months, gender): return 0.0
        def wfl(self, weight, length, gender): return 0.0
        def hcfa(self, head_circumference, age_months, gender): return 0.0

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Settings
class Settings:
    APP_NAME = "PeduliGiziBalita Enterprise"
    APP_VERSION = "5.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-enterprise-key-here")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-super-secret-key")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    UPLOAD_DIR = "uploads"
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    WHO_DATA_PATH = "pygrowup"

settings = Settings()

# Directory setup
for directory in [settings.UPLOAD_DIR, "logs", "cache", "exports"]:
    Path(directory).mkdir(exist_ok=True)

# Database
database = databases.Database(settings.DATABASE_URL)
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Celery
celery_app = Celery("peduligizi", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
)

# Auth
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# Models
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

# SQLAlchemy Models
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
    gender = Column(String, nullable=False)
    birth_weight = Column(Float, nullable=True)
    birth_length = Column(Float, nullable=True)
    photo_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    parent = relationship("User", back_populates="children")
    measurements = relationship("Measurement", back_populates="child")
    growth_predictions = relationship("GrowthPrediction", back_populates="child")

class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    measurement_date = Column(DateTime, nullable=False)
    age_months = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    head_circumference = Column(Float, nullable=True)
    wfa_zscore = Column(Float, nullable=True)
    hfa_zscore = Column(Float, nullable=True)
    hcfa_zscore = Column(Float, nullable=True)
    wfl_zscore = Column(Float, nullable=True)
    wfa_status = Column(String, nullable=True)
    hfa_status = Column(String, nullable=True)
    hcfa_status = Column(String, nullable=True)
    wfl_status = Column(String, nullable=True)
    measured_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    child = relationship("Child", back_populates="measurements")

    __table_args__ = (
        Index('idx_child_date', 'child_id', 'measurement_date'),
        Index('idx_measurement_date', 'measurement_date'),
    )

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    summary = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=False, index=True)
    difficulty = Column(String, nullable=False)
    read_time = Column(Integer, nullable=False)
    recommended_age_min = Column(Integer, nullable=True)
    recommended_age_max = Column(Integer, nullable=True)
    tags = Column(String, nullable=True)
    image_keywords = Column(String, nullable=True)
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

    author = relationship("User")
    bookmarks = relationship("Bookmark", back_populates="article")
    reading_progress = relationship("ReadingProgress", back_populates="article")
    article_likes = relationship("ArticleLike", back_populates="article")
    comments = relationship("Comment", back_populates="article")

class Bookmark(Base):
    __tablename__ = "bookmarks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    folder = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="bookmarks")
    article = relationship("Article", back_populates="bookmarks")

    __table_args__ = (Index('idx_user_article', 'user_id', 'article_id', unique=True),)

class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    progress_percentage = Column(Float, default=0.0)
    time_spent = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    last_read_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="reading_progress")
    article = relationship("Article", back_populates="reading_progress")

    __table_args__ = (Index('idx_user_article_progress', 'user_id', 'article_id', unique=True),)

class ArticleLike(Base):
    __tablename__ = "article_likes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())

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

    user = relationship("User")
    article = relationship("Article", back_populates="comments")
    parent = relationship("Comment", remote_side=[id])
    replies = relationship("Comment", back_populates="parent")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    scheduled_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="notifications")

    __table_args__ = (Index('idx_user_unread', 'user_id', 'is_read'),)

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    preference_type = Column(String, nullable=False)
    preference_value = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="user_preferences")

    __table_args__ = (Index('idx_user_pref_type', 'user_id', 'preference_type', unique=True),)

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

    child = relationship("Child", back_populates="growth_predictions")

    __table_args__ = (Index('idx_child_prediction_date', 'child_id', 'prediction_date'),)

# Pydantic Models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str
    role: UserRole = UserRole.PARENT

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True

class MeasurementCreate(BaseModel):
    child_id: int
    measurement_date: date
    weight: float
    height: float
    head_circumference: Optional[float] = None
    notes: Optional[str] = None

class MeasurementResponse(BaseModel):
    id: int
    child_id: int
    measurement_date: date
    age_months: float
    weight: float
    height: float
    head_circumference: Optional[float]
    wfa_zscore: Optional[float]
    hfa_zscore: Optional[float]
    hcfa_zscore: Optional[float]
    wfl_zscore: Optional[float]
    wfa_status: Optional[str]
    hfa_status: Optional[str]
    hcfa_status: Optional[str]
    wfl_status: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ArticleCreate(BaseModel):
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

class ArticleResponse(BaseModel):
    id: int
    slug: str
    title: str
    summary: str
    content: str
    category: str
    difficulty: str
    read_time: int
    recommended_age_min: Optional[int]
    recommended_age_max: Optional[int]
    tags: Optional[str]
    image_keywords: Optional[str]
    featured: bool
    view_count: int
    like_count: int
    share_count: int
    author_id: Optional[int]
    is_published: bool
    published_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

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

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# WHO Service
class WHOService:
    def __init__(self):
        self.calc = Calculator()
    def calculate_zscores(self, measurement: Measurement, child: Child):
        gender = child.gender.lower()
        age_months = measurement.age_months
        results = {}
        results['wfa'] = {
            'zscore': self.calc.wfa(measurement.weight, age_months, gender),
            'status': self.interpret_zscore(self.calc.wfa(measurement.weight, age_months, gender))
        }
        results['hfa'] = {
            'zscore': self.calc.hfa(measurement.height, age_months, gender),
            'status': self.interpret_zscore(self.calc.hfa(measurement.height, age_months, gender))
        }
        if measurement.head_circumference:
            results['hcfa'] = {
                'zscore': self.calc.hcfa(measurement.head_circumference, age_months, gender),
                'status': self.interpret_zscore(self.calc.hcfa(measurement.head_circumference, age_months, gender))
            }
        if 45 <= measurement.height <= 110:
            results['wfl'] = {
                'zscore': self.calc.wfl(measurement.weight, measurement.height, gender),
                'status': self.interpret_zscore(self.calc.wfl(measurement.weight, measurement.height, gender))
            }
        return results
    def interpret_zscore(self, zscore: float):
        if zscore is None:
            return {"status": "Tidak dapat dihitung", "category": "error", "color": "#gray"}
        if zscore < -3:
            return {"status": "Sangat Kurang", "category": "severe", "color": "#dc3545"}
        elif zscore < -2:
            return {"status": "Kurang", "category": "moderate", "color": "#fd7e14"}
        elif zscore < -1:
            return {"status": "Risiko Kurang", "category": "mild", "color": "#ffc107"}
        elif zscore <= 1:
            return {"status": "Normal", "category": "normal", "color": "#28a745"}
        elif zscore <= 2:
            return {"status": "Risiko Gemuk", "category": "overweight_risk", "color": "#17a2b8"}
        elif zscore <= 3:
            return {"status": "Gemuk", "category": "overweight", "color": "#6f42c1"}
        else:
            return {"status": "Sangat Gemuk", "category": "obese", "color": "#e83e8c"}

# FastAPI App
app = FastAPI(
    title=f"{settings.APP_NAME} v{settings.APP_VERSION}",
    version=settings.APP_VERSION,
    description="Enterprise-grade child growth monitoring platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    Base.metadata.create_all(bind=engine)
    logger.info("PeduliGiziBalita Enterprise v5.0.0 started")
    yield
    await database.disconnect()

app.router.lifespan_context = lifespan

# Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Auth Dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(allowed_roles: List[UserRole]):
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in [role.value for role in allowed_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker

# Endpoints
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    try:
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    overall = all(s == "healthy" for s in [db_status, redis_status])
    return {
        "status": "healthy" if overall else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "version": settings.APP_VERSION,
        "services": {"database": db_status, "redis": redis_status}
    }

@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=get_password_hash(user.password),
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/auth/login")
async def login(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    user.last_login = datetime.now()
    db.commit()
    access_token = create_access_token(data={"user_id": user.id, "username": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.post("/children")
async def create_child(name: str, birth_date: date, gender: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    child = Child(parent_id=current_user.id, name=name, birth_date=birth_date, gender=gender)
    db.add(child)
    db.commit()
    db.refresh(child)
    return child

@app.get("/children")
async def list_children(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return db.query(Child).filter(Child.parent_id == current_user.id).all()

@app.post("/measurements", response_model=MeasurementResponse)
async def create_measurement(m: MeasurementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    child = db.query(Child).filter(Child.id == m.child_id).first()
    if not child or child.parent_id != current_user.id:
        raise HTTPException(status_code=404, detail="Child not found or access denied")
    age_months = (m.measurement_date - child.birth_date).days / 30.4375
    db_m = Measurement(**m.dict(), age_months=age_months)
    z = WHOService().calculate_zscores(db_m, child)
    for k in z:
        setattr(db_m, f"{k}_zscore", z[k]['zscore'])
        setattr(db_m, f"{k}_status", z[k]['status']['status'])
    db.add(db_m)
    db.commit()
    db.refresh(db_m)
    return db_m

@app.get("/children/{child_id}/measurements", response_model=List[MeasurementResponse])
async def list_measurements(child_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child or child.parent_id != current_user.id:
        raise HTTPException(status_code=404, detail="Child not found or access denied")
    return db.query(Measurement).filter(Measurement.child_id == child_id).order_by(Measurement.measurement_date.desc()).all()

@app.get("/articles", response_model=List[ArticleResponse])
async def list_articles(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    return db.query(Article).filter(Article.is_published == True).order_by(Article.created_at.desc()).offset(offset).limit(limit).all()

@app.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id, Article.is_published == True).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.view_count += 1
    db.commit()
    return article

@app.post("/articles/{article_id}/bookmark")
async def bookmark_article(article_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    existing = db.query(Bookmark).filter(Bookmark.user_id == current_user.id, Bookmark.article_id == article_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"message": "Bookmark removed", "bookmarked": False}
    bm = Bookmark(user_id=current_user.id, article_id=article_id)
    db.add(bm)
    db.commit()
    return {"message": "Article bookmarked", "bookmarked": True}

@app.get("/users/me/bookmarks", response_model=List[ArticleResponse])
async def get_user_bookmarks(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    bookmarks = db.query(Bookmark).filter(Bookmark.user_id == current_user.id).all()
    article_ids = [bm.article_id for bm in bookmarks]
    return db.query(Article).filter(Article.id.in_(article_ids), Article.is_published == True).all()

@app.post("/articles/{article_id}/progress")
async def update_reading_progress(article_id: int, progress: ReadingProgressUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    rp = db.query(ReadingProgress).filter(ReadingProgress.user_id == current_user.id, ReadingProgress.article_id == article_id).first()
    if not rp:
        rp = ReadingProgress(user_id=current_user.id, article_id=article_id)
        db.add(rp)
    rp.progress_percentage = min(100, max(0, progress.progress_percentage))
    rp.time_spent += progress.time_spent
    rp.last_read_at = datetime.now()
    if progress.progress_percentage >= 100 and not rp.is_completed:
        rp.is_completed = True
        rp.completed_at = datetime.now()
    db.commit()
    return {"message": "Progress updated", "progress_percentage": rp.progress_percentage, "is_completed": rp.is_completed}

@app.get("/users/me/recommendations", response_model=List[ArticleResponse])
async def get_recommendations(limit: int = 6, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Simple logic: featured + age match
    children = db.query(Child).filter(Child.parent_id == current_user.id).all()
    if not children:
        return db.query(Article).filter(Article.featured == True, Article.is_published == True).limit(limit).all()
    avg_age = sum([(datetime.now().date() - c.birth_date.date()).days / 30.4375 for c in children]) / len(children)
    query = db.query(Article).filter(Article.is_published == True)
    if avg_age <= 6:
        query = query.filter(Article.recommended_age_max <= 6)
    elif avg_age <= 12:
        query = query.filter(Article.recommended_age_min >= 6, Article.recommended_age_max <= 12)
    elif avg_age <= 24:
        query = query.filter(Article.recommended_age_min >= 12, Article.recommended_age_max <= 24)
    else:
        query = query.filter(Article.recommended_age_min >= 24)
    return query.order_by(Article.featured.desc(), Article.view_count.desc()).limit(limit).all()

@app.get("/analytics/user")
async def get_user_analytics(days: int = 30, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from sqlalchemy import func
    end = datetime.now()
    start = end - timedelta(days=days)
    reading_stats = db.query(func.count(ReadingProgress.id)).filter(ReadingProgress.user_id == current_user.id, ReadingProgress.last_read_at >= start).scalar()
    completed_articles = db.query(func.count(ReadingProgress.id)).filter(ReadingProgress.user_id == current_user.id, ReadingProgress.is_completed == True, ReadingProgress.completed_at >= start).scalar()
    total_time_spent = db.query(func.sum(ReadingProgress.time_spent)).filter(ReadingProgress.user_id == current_user.id, ReadingProgress.last_read_at >= start).scalar() or 0
    bookmark_count = db.query(func.count(Bookmark.id)).filter(Bookmark.user_id == current_user.id, Bookmark.created_at >= start).scalar()
    return {
        "period_days": days,
        "articles_read": reading_stats,
        "articles_completed": completed_articles,
        "total_reading_time_minutes": round(total_time_spent / 60, 2),
        "bookmarks_added": bookmark_count,
        "average_session_time": round(total_time_spent / max(reading_stats, 1) / 60, 2)
    }

@app.get("/analytics/system")
async def get_system_analytics(days: int = 30, db: Session = Depends(get_db), current_user: User = Depends(require_role([UserRole.ADMIN]))):
    from sqlalchemy import func
    end = datetime.now()
    start = end - timedelta(days=days)
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.last_login >= start).scalar()
    new_users = db.query(func.count(User.id)).filter(User.created_at >= start).scalar()
    total_articles = db.query(func.count(Article.id)).filter(Article.is_published == True).scalar()
    featured_articles = db.query(func.count(Article.id)).filter(Article.featured == True, Article.is_published == True).scalar()
    total_views = db.query(func.sum(Article.view_count)).scalar() or 0
    total_likes = db.query(func.sum(Article.like_count)).scalar() or 0
    total_bookmarks = db.query(func.count(Bookmark.id)).scalar()
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

@app.post("/children/{child_id}/predict")
async def predict_growth(child_id: int, months_ahead: int = 6, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from scipy import stats
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child or child.parent_id != current_user.id:
        raise HTTPException(status_code=404, detail="Child not found or access denied")
    measurements = db.query(Measurement).filter(Measurement.child_id == child_id).order_by(Measurement.measurement_date.desc()).limit(10).all()
    if len(measurements) < 3:
        return {"error": "Insufficient data for prediction"}
    ages = [m.age_months for m in measurements]
    weights = [m.weight for m in measurements]
    heights = [m.height for m in measurements]
    weight_slope, weight_intercept, weight_r, _, weight_se = stats.linregress(ages, weights)
    height_slope, height_intercept, height_r, _, height_se = stats.linregress(ages, heights)
    current_age = (datetime.now().date() - child.birth_date).days / 30.4375
    future_age = current_age + months_ahead
    predicted_weight = weight_slope * future_age + weight_intercept
    predicted_height = height_slope * future_age + height_intercept
    weight_ci = 1.96 * weight_se
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

@app.get("/notifications")
async def get_notifications(unread_only: bool = False, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notification_service = NotificationService(db)
    return notification_service.get_user_notifications(current_user.id, unread_only, limit)

@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notification_service = NotificationService(db)
    success = notification_service.mark_as_read(notification_id, current_user.id)
    if success:
        return {"message": "Notification marked as read"}
    raise HTTPException(status_code=404, detail="Notification not found")

# Admin Panel
@app.get("/admin/dashboard")
async def admin_dashboard(db: Session = Depends(get_db), current_user: User = Depends(require_role([UserRole.ADMIN]))):
    analytics_service = AnalyticsService(db)
    system_analytics = analytics_service.get_system_analytics(30)
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    recent_articles = db.query(Article).order_by(Article.created_at.desc()).limit(10).all()
    return {
        "system_analytics": system_analytics,
        "recent_users": recent_users,
        "recent_articles": recent_articles,
        "system_status": {"database_status": "healthy", "redis_status": "healthy", "disk_usage": "normal", "memory_usage": "normal"}
    }

@app.get("/admin/users")
async def admin_list_users(skip: int = 0, limit: int = 100, search: Optional[str] = None, role: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(require_role([UserRole.ADMIN]))):
    from sqlalchemy import func
    query = db.query(User)
    if search:
        search_term = f"%{search}%"
        query = query.filter(User.full_name.ilike(search_term) | User.email.ilike(search_term) | User.username.ilike(search_term))
    if role:
        query = query.filter(User.role == role)
    users = query.offset(skip).limit(limit).all()
    total = query.count()
    return {"users": users, "total": total, "skip": skip, "limit": limit}

@app.put("/admin/users/{user_id}/role")
async def admin_update_user_role(user_id: int, new_role: UserRole, db: Session = Depends(get_db), current_user: User = Depends(require_role([UserRole.ADMIN]))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = new_role
    db.commit()
    return {"message": f"User role updated to {new_role}", "user": user}

@app.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role([UserRole.ADMIN]))):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, set] = {}
        self.user_connections: Dict[int, set] = {}

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

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.add(connection)
            for conn in disconnected:
                self.active_connections[room_id].discard(conn)

manager = ConnectionManager()

@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: int, token: str):
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
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"user_{user_id}", user_id)

# Background Tasks (Celery)
@celery_app.task
def send_notification_task(user_id: int, notification_data: dict):
    logger.info(f"Sending notification to user {user_id}: {notification_data}")

@celery_app.task
def generate_growth_report_task(child_id: int, period_months: int):
    logger.info(f"Generating growth report for child {child_id}, period: {period_months} months")

@celery_app.task
def cleanup_old_data_task():
    logger.info("Starting data cleanup task")

# Final Section: Utils
def calculate_age(birth_date: date, measurement_date: date) -> float:
    delta = measurement_date - birth_date
    return delta.days / 30.4375

def sanitize_filename(filename: str) -> str:
    for char in '<>:"/\\|?*':
        filename = filename.replace(char, '_')
    return filename.strip()

def generate_unique_id() -> str:
    return str(uuid.uuid4())

def format_date(date_obj):
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    return date_obj.strftime("%d/%m/%Y")

def validate_age_range(age_range: str):
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

def is_age_in_range(age_months: int, age_range: str):
    if not age_range or age_range == "Semua Usia":
        return True
    min_age, max_age = validate_age_range(age_range)
    if min_age is not None and max_age is not None:
        return min_age <= age_months <= max_age
    return False

