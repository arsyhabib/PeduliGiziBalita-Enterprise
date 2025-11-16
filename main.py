#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
                    PeduliGiziBalita v5.0 - ENTERPRISE EDITION
              Platform Pertumbuhan Anak Skala Besar Berbasis WHO
==============================================================================
"""

import os
import json
import uuid
import redis
import logging
from celery import Celery
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from contextlib import asynccontextmanager

# FastAPI
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
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
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

# WHO
try:
    from pygrowup import Calculator
except ImportError:
    class Calculator:
        def wfa(self, w, a, g): return 0
        def hfa(self, h, a, g): return 0
        def wfl(self, w, l, g): return 0
        def hcfa(self, hc, a, g): return 0

# Settings
class Settings:
    APP_NAME = "PeduliGiziBalita Enterprise"
    APP_VERSION = "5.0.0"
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "rahasia123")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt123")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    UPLOAD_DIR = "uploads"

settings = Settings()

# Database
database = databases.Database(settings.DATABASE_URL)
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Auth
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Models
class UserRole(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    PARENT = "parent"
    NUTRITIONIST = "nutritionist"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default=UserRole.PARENT, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

class Child(Base):
    __tablename__ = "children"
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    birth_date = Column(DateTime, nullable=False)
    gender = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())

class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    measurement_date = Column(DateTime, nullable=False)
    age_months = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    wfa_zscore = Column(Float, nullable=True)
    hfa_zscore = Column(Float, nullable=True)
    wfl_zscore = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    child = relationship("Child", back_populates="measurements")

Child.measurements = relationship("Measurement", back_populates="child")

# Pydantic
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
    created_at: datetime

    class Config:
        from_attributes = True

class MeasurementCreate(BaseModel):
    child_id: int
    measurement_date: date
    weight: float
    height: float

class MeasurementResponse(BaseModel):
    id: int
    child_id: int
    age_months: float
    weight: float
    height: float
    wfa_zscore: Optional[float]
    hfa_zscore: Optional[float]
    wfl_zscore: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True

# Utils
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI App
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise child growth monitoring",
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

# WHO Service
class WHOService:
    def __init__(self):
        self.calc = Calculator()
    def zscore(self, m: Measurement, child: Child):
        gender = child.gender.lower()
        return {
            "wfa": self.calc.wfa(m.weight, m.age_months, gender),
            "hfa": self.calc.hfa(m.height, m.age_months, gender),
            "wfl": self.calc.wfl(m.weight, m.height, gender) if 45 <= m.height <= 110 else None
        }

# Endpoints
@app.on_event("startup")
async def startup():
    await database.connect()
    Base.metadata.create_all(bind=engine)

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    return {"status": "healthy", "version": settings.APP_VERSION}

@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"user_id": user.id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/measurements", response_model=MeasurementResponse)
async def create_measurement(m: MeasurementCreate, db: Session = Depends(get_db)):
    child = db.query(Child).filter(Child.id == m.child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    age_months = (m.measurement_date - child.birth_date).days / 30.4375
    db_m = Measurement(**m.dict(), age_months=age_months)
    z = WHOService().zscore(db_m, child)
    db_m.wfa_zscore = z.get("wfa")
    db_m.hfa_zscore = z.get("hfa")
    db_m.wfl_zscore = z.get("wfl")
    db.add(db_m)
    db.commit()
    db.refresh(db_m)
    return db_m

@app.get("/children/{child_id}/measurements", response_model=List[MeasurementResponse])
async def list_measurements(child_id: int, db: Session = Depends(get_db)):
    return db.query(Measurement).filter(Measurement.child_id == child_id).all()
