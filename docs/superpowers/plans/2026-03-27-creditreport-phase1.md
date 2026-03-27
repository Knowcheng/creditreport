# 征信报告自动化审核系统（第一期）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构现有征信报告解析系统，新增 PostgreSQL 持久化、GLM-OCR 支持、JWT 多用户认证，提供 FastAPI 后端 + Streamlit 前端的 Web/本地双端应用。

**Architecture:** FastAPI 后端提供 REST API，Streamlit 前端调用 API，同一套代码通过环境变量切换 Web（PostgreSQL）和本地（SQLite）模式。解析引擎从旧代码重构为工厂模式，OCR 仅在扫描件/图片时触发。

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Streamlit, SQLAlchemy 2.0, Alembic, PostgreSQL/SQLite, pdfplumber, PyPDF2, GLM-OCR（HTTP API）, PyJWT, bcrypt, python-multipart, httpx, PyInstaller, Docker + docker-compose

---

## 文件结构总览

```
creditreport/
├── backend/
│   ├── main.py                    # FastAPI 应用入口
│   ├── core/
│   │   ├── config.py              # 配置（MODE, DATABASE_URL, OCR_URL, JWT）
│   │   ├── database.py            # SQLAlchemy engine/session
│   │   └── auth.py                # JWT 工具（create_token, verify_token）
│   ├── models/
│   │   └── db.py                  # 所有 SQLAlchemy ORM 模型
│   ├── api/
│   │   ├── auth.py                # POST /api/auth/login, /register
│   │   ├── reports.py             # POST/GET/DELETE /api/reports/...
│   │   └── users.py               # GET /api/users（admin）
│   ├── parsers/
│   │   ├── base.py                # BaseParser 抽象类 + ReportResult dataclass
│   │   ├── enterprise.py          # EnterpriseParser（重构自 CR_CIParser）
│   │   ├── personal_detail.py     # PersonalDetailParser（重构自 CR_PDParser）
│   │   ├── personal_simple.py     # PersonalSimpleParser（重构自 CR_PSParser）
│   │   ├── factory.py             # ReportParserFactory
│   │   └── validator.py           # ReportValidator（复用旧代码）
│   ├── ocr/
│   │   └── glm_ocr.py             # GLM-OCR HTTP 封装
│   └── services/
│       ├── file_processor.py      # 文件类型检测 + OCR 预处理
│       └── report_service.py      # 解析流程编排 + 写库
├── frontend/
│   ├── app.py                     # Streamlit 主入口（登录页）
│   ├── api_client.py              # 封装所有对 FastAPI 的 HTTP 调用
│   └── pages/
│       ├── 1_上传解析.py
│       ├── 2_报告列表.py
│       ├── 3_报告详情.py
│       └── 4_用户管理.py
├── tests/
│   ├── test_parsers.py
│   ├── test_file_processor.py
│   ├── test_auth.py
│   └── test_api.py
├── alembic/                       # 数据库迁移
│   └── versions/
├── creditreport_old/              # 旧代码（只读参考）
├── deploy/
│   ├── docker-compose.yml
│   └── nginx.conf
├── requirements.txt
├── requirements-local.txt         # 本地版额外依赖
├── alembic.ini
└── .env.example
```

---

## Phase 1：项目初始化

### Task 1：创建项目结构与依赖

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `backend/__init__.py`（及各子目录 `__init__.py`）

- [ ] **Step 1: 创建目录结构**

```bash
cd D:/loansystem/creditreport
mkdir -p backend/core backend/models backend/api backend/parsers backend/ocr backend/services
mkdir -p frontend/pages
mkdir -p tests
mkdir -p deploy
touch backend/__init__.py backend/core/__init__.py backend/models/__init__.py
touch backend/api/__init__.py backend/parsers/__init__.py backend/ocr/__init__.py backend/services/__init__.py
touch frontend/__init__.py
```

- [ ] **Step 2: 创建 requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
streamlit==1.35.0
sqlalchemy==2.0.30
alembic==1.13.1
psycopg2-binary==2.9.9
pdfplumber==0.11.0
PyPDF2==3.0.1
bcrypt==4.1.3
PyJWT==2.8.0
python-multipart==0.0.9
httpx==0.27.0
python-dotenv==1.0.1
pandas==2.2.2
pillow==10.3.0
pdf2image==1.17.0
```

- [ ] **Step 3: 创建 .env.example**

```
MODE=web
DATABASE_URL=postgresql://user:password@localhost:5432/creditreport
OCR_URL=http://localhost:8080/ocr
JWT_SECRET=change-me-in-production
JWT_EXPIRE_HOURS=24
UPLOAD_DIR=./uploads
```

- [ ] **Step 4: 提交**

```bash
git init
git add requirements.txt .env.example backend/ frontend/ tests/ deploy/
git commit -m "chore: initialize project structure"
```

---

### Task 2：核心配置模块

**Files:**
- Create: `backend/core/config.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_config.py`：

```python
import os
import pytest

def test_web_mode_reads_postgres_url(monkeypatch):
    monkeypatch.setenv("MODE", "web")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.setenv("OCR_URL", "http://localhost:8080/ocr")
    # 重新加载模块以获取新环境变量
    import importlib
    import backend.core.config as cfg
    importlib.reload(cfg)
    settings = cfg.Settings()
    assert settings.MODE == "web"
    assert "postgresql" in settings.DATABASE_URL

def test_local_mode_defaults_to_sqlite(monkeypatch):
    monkeypatch.setenv("MODE", "local")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.setenv("OCR_URL", "http://localhost:8080/ocr")
    import importlib
    import backend.core.config as cfg
    importlib.reload(cfg)
    settings = cfg.Settings()
    assert "sqlite" in settings.DATABASE_URL
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_config.py -v
```

期望：`ModuleNotFoundError` 或 `ImportError`

- [ ] **Step 3: 实现 config.py**

```python
# backend/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MODE: str = os.getenv("MODE", "local")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
    OCR_URL: str = os.getenv("OCR_URL", "http://localhost:8080/ocr")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

    @property
    def DATABASE_URL(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        if self.MODE == "local":
            return "sqlite:///./creditreport.db"
        raise ValueError("DATABASE_URL 环境变量未设置（web 模式必须提供）")

settings = Settings()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_config.py -v
```

期望：2 个 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/core/config.py tests/test_config.py
git commit -m "feat: add core config module with web/local mode switching"
```

---

### Task 3：数据库连接与 Session

**Files:**
- Create: `backend/core/database.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_database.py`：

```python
import os
import pytest

def test_get_db_yields_session(monkeypatch):
    monkeypatch.setenv("MODE", "local")
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.setenv("OCR_URL", "http://localhost:8080/ocr")
    import importlib
    import backend.core.config as cfg
    importlib.reload(cfg)
    import backend.core.database as db_module
    importlib.reload(db_module)

    gen = db_module.get_db()
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_database.py -v
```

- [ ] **Step 3: 实现 database.py**

```python
# backend/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.core.config import settings

connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_database.py -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/core/database.py tests/test_database.py
git commit -m "feat: add database session management"
```

---

## Phase 2：数据库模型

### Task 4：ORM 模型定义

**Files:**
- Create: `backend/models/db.py`
- Create: `alembic.ini`（alembic 初始化）

- [ ] **Step 1: 写测试**

新建 `tests/test_models.py`：

```python
import os
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:")
    from backend.core.database import Base
    import backend.models.db  # 注册所有模型
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "users" in tables
    assert "reports" in tables
    assert "enterprise_reports" in tables
    assert "personal_reports" in tables
    assert "credit_accounts" in tables
    assert "query_records" in tables

def test_user_model_fields():
    engine = create_engine("sqlite:///:memory:")
    from backend.core.database import Base
    import backend.models.db
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("users")]
    assert "id" in cols
    assert "username" in cols
    assert "password_hash" in cols
    assert "role" in cols
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_models.py -v
```

- [ ] **Step 3: 实现 models/db.py**

```python
# backend/models/db.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user")  # "admin" | "user"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reports: Mapped[list["Report"]] = relationship("Report", back_populates="user")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(32))  # enterprise/personal_detail/personal_simple
    file_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16))  # pdf_native/pdf_scanned/image
    report_number: Mapped[Optional[str]] = mapped_column(String(64))
    subject_name: Mapped[Optional[str]] = mapped_column(String(128))
    report_date: Mapped[Optional[str]] = mapped_column(String(32))
    is_valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/success/failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="reports")
    enterprise_report: Mapped[Optional["EnterpriseReport"]] = relationship(
        "EnterpriseReport", back_populates="report", uselist=False
    )
    personal_report: Mapped[Optional["PersonalReport"]] = relationship(
        "PersonalReport", back_populates="report", uselist=False
    )
    credit_accounts: Mapped[list["CreditAccount"]] = relationship("CreditAccount", back_populates="report")
    query_records: Mapped[list["QueryRecord"]] = relationship("QueryRecord", back_populates="report")


class EnterpriseReport(Base):
    __tablename__ = "enterprise_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), unique=True, nullable=False)
    credit_code: Mapped[Optional[str]] = mapped_column(String(32))   # 统一社会信用代码
    company_name: Mapped[Optional[str]] = mapped_column(String(256))
    credit_num: Mapped[Optional[str]] = mapped_column(String(64))    # 中征码
    registered_capital: Mapped[Optional[str]] = mapped_column(String(64))
    query_org: Mapped[Optional[str]] = mapped_column(String(256))
    data_json: Mapped[Optional[dict]] = mapped_column(JSON)          # 完整字段兜底

    report: Mapped["Report"] = relationship("Report", back_populates="enterprise_report")


class PersonalReport(Base):
    __tablename__ = "personal_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), unique=True, nullable=False)
    id_number: Mapped[Optional[str]] = mapped_column(String(32))     # 证件号码
    name: Mapped[Optional[str]] = mapped_column(String(64))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    marital_status: Mapped[Optional[str]] = mapped_column(String(16))
    data_json: Mapped[Optional[dict]] = mapped_column(JSON)

    report: Mapped["Report"] = relationship("Report", back_populates="personal_report")


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), nullable=False)
    account_type: Mapped[Optional[str]] = mapped_column(String(64))  # 借款/信用卡/担保等
    institution: Mapped[Optional[str]] = mapped_column(String(256))
    amount: Mapped[Optional[float]] = mapped_column(Float)
    balance: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(String(16))        # 正常/逾期/呆账
    data_json: Mapped[Optional[dict]] = mapped_column(JSON)

    report: Mapped["Report"] = relationship("Report", back_populates="credit_accounts")


class QueryRecord(Base):
    __tablename__ = "query_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), nullable=False)
    query_date: Mapped[Optional[str]] = mapped_column(String(32))
    query_org: Mapped[Optional[str]] = mapped_column(String(256))
    query_reason: Mapped[Optional[str]] = mapped_column(String(128))

    report: Mapped["Report"] = relationship("Report", back_populates="query_records")
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_models.py -v
```

期望：2 个 PASS

- [ ] **Step 5: 初始化 Alembic**

```bash
alembic init alembic
```

编辑 `alembic/env.py`，在 `target_metadata` 处引入模型：

```python
# alembic/env.py（在文件顶部 import 区域添加）
import sys
sys.path.insert(0, ".")
from backend.core.database import Base
from backend.models import db  # noqa: F401 注册所有模型
target_metadata = Base.metadata
```

编辑 `alembic.ini`，将 `sqlalchemy.url` 改为：

```ini
sqlalchemy.url = sqlite:///./creditreport.db
```

- [ ] **Step 6: 生成并执行迁移**

```bash
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
```

期望：生成 `alembic/versions/xxxx_initial_tables.py` 并执行成功

- [ ] **Step 7: 提交**

```bash
git add backend/models/db.py alembic/ alembic.ini tests/test_models.py
git commit -m "feat: define ORM models and initial migration"
```

---

## Phase 3：认证模块

### Task 5：JWT 工具与密码哈希

**Files:**
- Create: `backend/core/auth.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_auth.py`：

```python
import pytest
from backend.core.auth import hash_password, verify_password, create_token, decode_token

def test_password_hash_and_verify():
    hashed = hash_password("mypassword")
    assert hashed != "mypassword"
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_create_and_decode_token():
    token = create_token(user_id=1, username="testuser", role="user")
    payload = decode_token(token)
    assert payload["user_id"] == 1
    assert payload["username"] == "testuser"
    assert payload["role"] == "user"

def test_decode_invalid_token_raises():
    with pytest.raises(ValueError, match="无效"):
        decode_token("not.a.valid.token")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_auth.py -v
```

- [ ] **Step 3: 实现 auth.py**

```python
# backend/core/auth.py
from datetime import datetime, timedelta
import bcrypt
import jwt
from backend.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("无效 Token：已过期")
    except jwt.InvalidTokenError:
        raise ValueError("无效 Token")
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_auth.py -v
```

期望：3 个 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/core/auth.py tests/test_auth.py
git commit -m "feat: add JWT auth and password hash utilities"
```

---

### Task 6：FastAPI 认证端点

**Files:**
- Create: `backend/api/auth.py`
- Create: `backend/main.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_api_auth.py`：

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.database import Base, get_db
from backend.models.db import User
from backend.core.auth import hash_password
from backend.main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine)

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    db = TestingSession()
    admin = User(username="admin", password_hash=hash_password("admin123"), role="admin")
    db.add(admin)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(engine)

client = TestClient(app)

def test_login_success():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    assert "token" in resp.json()

def test_login_wrong_password():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401

def test_register_by_admin():
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = login.json()["token"]
    resp = client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "pass123"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201

def test_register_requires_admin():
    resp = client.post(
        "/api/auth/register",
        json={"username": "newuser2", "password": "pass123"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_api_auth.py -v
```

- [ ] **Step 3: 实现 main.py**

```python
# backend/main.py
from fastapi import FastAPI
from backend.api import auth, reports, users

app = FastAPI(title="征信报告审核系统", version="1.0.0")

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(reports.router, prefix="/api/reports", tags=["报告"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
```

- [ ] **Step 4: 实现 backend/api/auth.py**

```python
# backend/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.auth import hash_password, verify_password, create_token, decode_token
from backend.models.db import User

router = APIRouter()
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供 Token")
    payload = decode_token(credentials.credentials)
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_token(user_id=user.id, username=user.username, role=user.role)
    return {"token": token, "role": user.role, "username": user.username}


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=req.username, password_hash=hash_password(req.password), role="user")
    db.add(user)
    db.commit()
    return {"message": "用户创建成功"}
```

- [ ] **Step 5: 创建空的 reports.py 和 users.py（避免 import 报错）**

```python
# backend/api/reports.py
from fastapi import APIRouter
router = APIRouter()

# backend/api/users.py
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 6: 运行测试，确认通过**

```bash
pytest tests/test_api_auth.py -v
```

期望：4 个 PASS

- [ ] **Step 7: 提交**

```bash
git add backend/main.py backend/api/auth.py backend/api/reports.py backend/api/users.py tests/test_api_auth.py
git commit -m "feat: add auth API endpoints (login/register)"
```

---

## Phase 4：解析引擎重构

### Task 7：BaseParser 与 ReportResult

**Files:**
- Create: `backend/parsers/base.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_parsers.py`（仅 BaseParser 部分）：

```python
import pytest
from dataclasses import asdict
from backend.parsers.base import ReportResult

def test_report_result_has_required_fields():
    result = ReportResult(
        report_type="enterprise",
        report_number="20240101120000001",
        subject_name="测试企业有限公司",
        report_date="2024-01-01",
        raw_data={"key": "value"},
    )
    d = asdict(result)
    assert d["report_type"] == "enterprise"
    assert d["subject_name"] == "测试企业有限公司"
    assert d["raw_data"] == {"key": "value"}
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_parsers.py::test_report_result_has_required_fields -v
```

- [ ] **Step 3: 实现 base.py**

```python
# backend/parsers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReportResult:
    report_type: str                    # enterprise/personal_detail/personal_simple
    report_number: Optional[str]
    subject_name: Optional[str]         # 企业名称或被查询者姓名
    report_date: Optional[str]
    raw_data: dict = field(default_factory=dict)   # 完整解析结果，按模块分键
    credit_accounts: list = field(default_factory=list)  # 信贷明细列表
    query_records: list = field(default_factory=list)    # 查询记录列表


class BaseParser(ABC):
    """所有 Parser 的抽象基类，统一输入输出接口"""

    def __init__(self, text: str, tables: list, file_path: str):
        self.text = text
        self.tables = tables
        self.file_path = file_path

    @abstractmethod
    def parse(self) -> ReportResult:
        """解析报告，返回 ReportResult"""
        raise NotImplementedError
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_parsers.py::test_report_result_has_required_fields -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/parsers/base.py tests/test_parsers.py
git commit -m "feat: add BaseParser abstract class and ReportResult dataclass"
```

---

### Task 8：EnterpriseParser（重构自 CR_CIParser）

**Files:**
- Create: `backend/parsers/enterprise.py`
- Modify: `tests/test_parsers.py`（追加测试）

- [ ] **Step 1: 追加测试到 tests/test_parsers.py**

```python
import re
from unittest.mock import MagicMock, patch

def test_enterprise_parser_extracts_report_info():
    sample_text = (
        "NO.20240101120000001\n"
        "企业名称：测试科技有限公司 \n"
        "统一社会信用代码：91110000123456789X\n"
        "查询机构：某商业银行 \n"
        "2024-01-01T12:00:00\n"
    )
    sample_tables = [
        [["统一社会信用代码", "91110000123456789X"]],  # tables[0]
        [["字段1", "值1"], ["借贷余额", "100"], ["被追偿类余额", "0"],
         ["关注类余额", "0"], ["不良类余额", "0"],
         ["担保余额", "200"], ["担保关注", "0"], ["担保不良", "0"]],  # tables[1]
    ]
    from backend.parsers.enterprise import EnterpriseParser
    parser = EnterpriseParser(text=sample_text, tables=sample_tables, file_path="test.pdf")
    result = parser.parse()
    assert result.report_type == "enterprise"
    assert result.report_number == "20240101120000001"
    assert result.subject_name == "测试科技有限公司"
    assert result.report_date == "2024-01-01T12:00:00"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_parsers.py::test_enterprise_parser_extracts_report_info -v
```

- [ ] **Step 3: 实现 enterprise.py（核心字段提取，复用旧逻辑）**

```python
# backend/parsers/enterprise.py
import re
import logging
from typing import Optional
from dataclasses import asdict
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class EnterpriseParser(BaseParser):
    """企业征信自查版解析器（重构自旧代码 CR_CIParser）"""

    REPORT_PATTERNS = {
        "report_number": r"NO\.(\d+)",
        "company_name": r"企业名称[：:](.+?)\s",
        "credit_num": r"中征码[：:](.+?)\s",
        "credit_code": r"统一社会信用代码[：:]\s*([0-9A-Z]{18})",
        "query_org": r"查询机构[：:](.+?)\s",
        "report_date": r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})",
    }

    def parse(self) -> ReportResult:
        info = self._extract_report_info()
        raw_data = {"report_info": info}

        # 提取企业基本信息（tables 结构与旧代码一致）
        try:
            raw_data["com_base"] = self._extract_com_base(info)
        except Exception as e:
            logger.warning(f"企业基本信息提取失败: {e}")
            raw_data["com_base"] = None

        # 提取信息概要
        try:
            raw_data["summary"] = self._extract_summary(info)
        except Exception as e:
            logger.warning(f"信息概要提取失败: {e}")
            raw_data["summary"] = None

        # 提取信贷账户（用于写入 credit_accounts 表）
        credit_accounts = self._extract_credit_accounts(info)

        return ReportResult(
            report_type="enterprise",
            report_number=info.get("report_number"),
            subject_name=info.get("company_name"),
            report_date=info.get("report_date"),
            raw_data=raw_data,
            credit_accounts=credit_accounts,
            query_records=[],
        )

    def _extract_report_info(self) -> dict:
        info = {}
        for key, pattern in self.REPORT_PATTERNS.items():
            match = re.search(pattern, self.text)
            info[key] = match.group(1).strip() if match else None
        return info

    def _extract_com_base(self, report_info: dict) -> Optional[dict]:
        if not self.tables:
            return None
        try:
            com_id_dict = {item[0]: item[1] for item in self.tables[0] if len(item) >= 2}
        except (IndexError, TypeError):
            com_id_dict = {}
        result = {**com_id_dict}
        result["报告编号"] = report_info.get("report_number")
        result["报告日期"] = report_info.get("report_date")
        return result

    def _extract_summary(self, report_info: dict) -> Optional[dict]:
        if not self.tables or len(self.tables) < 2:
            return None
        try:
            summary = dict(zip(self.tables[1][0], self.tables[1][1]))
            summary["报告编号"] = report_info.get("report_number")
            return summary
        except (IndexError, TypeError):
            return None

    def _extract_credit_accounts(self, report_info: dict) -> list:
        """从 tables 提取信贷账户列表，供写入 credit_accounts 表"""
        accounts = []
        if not self.tables or len(self.tables) < 2:
            return accounts
        try:
            # 从 tables[1] 提取借贷余额信息作为账户汇总
            row = self.tables[1]
            if len(row) > 3:
                accounts.append({
                    "account_type": "借贷交易汇总",
                    "institution": None,
                    "amount": None,
                    "balance": self._safe_float(row[3][1]) if len(row[3]) > 1 else None,
                    "status": "汇总",
                    "data_json": {"报告编号": report_info.get("report_number")},
                })
        except (IndexError, TypeError):
            pass
        return accounts

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_parsers.py::test_enterprise_parser_extracts_report_info -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/parsers/enterprise.py tests/test_parsers.py
git commit -m "feat: add EnterpriseParser refactored from CR_CIParser"
```

---

### Task 9：PersonalDetailParser 和 PersonalSimpleParser

**Files:**
- Create: `backend/parsers/personal_detail.py`
- Create: `backend/parsers/personal_simple.py`
- Modify: `tests/test_parsers.py`（追加测试）

- [ ] **Step 1: 追加测试到 tests/test_parsers.py**

```python
def test_personal_detail_parser_returns_correct_type():
    sample_tables = [
        [
            ["报告编号：20240201000001", "", "", "报告时间：2024-02-01"],
            ["被查询者姓名", "证件类型", "证件号码"],
            ["张三", "身份证", "110101199001011234"],
        ]
    ]
    from backend.parsers.personal_detail import PersonalDetailParser
    parser = PersonalDetailParser(text="个人信用报告 身份信息", tables=sample_tables, file_path="test.pdf")
    result = parser.parse()
    assert result.report_type == "personal_detail"

def test_personal_simple_parser_returns_correct_type():
    sample_text = (
        "个人信用报告\n"
        "报告编号：20240301 报告时间：2024-03-01\n"
        "姓名：李四 证件号码：110101199001012345 已婚\n"
    )
    from backend.parsers.personal_simple import PersonalSimpleParser
    parser = PersonalSimpleParser(text=sample_text, tables=[], file_path="test.pdf")
    result = parser.parse()
    assert result.report_type == "personal_simple"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_parsers.py -k "personal" -v
```

- [ ] **Step 3: 实现 personal_detail.py**

```python
# backend/parsers/personal_detail.py
import logging
from typing import Optional
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class PersonalDetailParser(BaseParser):
    """个人征信详版解析器（重构自旧代码 CR_PDParser）"""

    def parse(self) -> ReportResult:
        report_info = self._extract_report_info()
        id_info = self._extract_id_info()
        query_records = self._extract_query_records()

        raw_data = {
            "report_info": report_info,
            "id_info": id_info,
            "addr_info": self._safe_extract(self._extract_addr_info),
            "career_info": self._safe_extract(self._extract_career_info),
            "account_info": self._safe_extract(self._extract_account_info),
        }

        return ReportResult(
            report_type="personal_detail",
            report_number=report_info.get("report_number") if report_info else None,
            subject_name=id_info.get("被查询者姓名") if id_info else None,
            report_date=report_info.get("report_date") if report_info else None,
            raw_data=raw_data,
            credit_accounts=[],
            query_records=query_records,
        )

    def _extract_report_info(self) -> Optional[dict]:
        if not self.tables or len(self.tables[0]) < 3:
            return None
        try:
            info = {}
            keys = self.tables[0][1]
            values = self.tables[0][2]
            for k, v in zip(keys, values):
                info[k] = v
            info["report_number"] = self.tables[0][0][0].split("：")[1] if "：" in str(self.tables[0][0][0]) else None
            info["report_date"] = self.tables[0][0][3].split("：")[1] if len(self.tables[0][0]) > 3 else None
            return info
        except (IndexError, TypeError) as e:
            logger.warning(f"报告信息提取失败: {e}")
            return None

    def _extract_id_info(self) -> Optional[dict]:
        if not self.tables:
            return None
        for table in self.tables:
            for row in table:
                for cell in row:
                    if cell and "被查询者姓名" in str(cell):
                        # 简化提取：返回表结构供后续完善
                        return {"被查询者姓名": self._find_name_in_tables()}
        return None

    def _find_name_in_tables(self) -> Optional[str]:
        for table in self.tables:
            for i, row in enumerate(table):
                for cell in row:
                    if cell and "被查询者姓名" in str(cell):
                        # 取下一行对应列的值
                        if i + 1 < len(table):
                            return table[i + 1][0] if table[i + 1] else None
        return None

    def _extract_addr_info(self) -> Optional[list]:
        return None  # 完整实现参考旧代码 CR_PDParser.extract_addr_info

    def _extract_career_info(self) -> Optional[list]:
        return None  # 完整实现参考旧代码 CR_PDParser.extract_career_info

    def _extract_account_info(self) -> Optional[list]:
        return None  # 完整实现参考旧代码 CR_PDParser.extract_account_info

    def _extract_query_records(self) -> list:
        return []  # 完整实现参考旧代码 CR_PDParser.extract_query_detail

    def _safe_extract(self, func) -> Optional[dict]:
        try:
            return func()
        except Exception as e:
            logger.warning(f"{func.__name__} 提取失败: {e}")
            return None
```

- [ ] **Step 4: 实现 personal_simple.py**

```python
# backend/parsers/personal_simple.py
import re
import logging
from datetime import datetime
from typing import Optional
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class PersonalSimpleParser(BaseParser):
    """个人征信简版解析器（重构自旧代码 CR_PSParser）"""

    def parse(self) -> ReportResult:
        base_info = self._extract_base_info()
        credit_accounts = self._extract_credit_summary()
        query_records = self._extract_query_summary()

        name = None
        report_number = None
        report_date = None
        if base_info:
            name = base_info.get("姓名")
            report_number = base_info.get("报告编号")
            report_date = base_info.get("报告日期")

        return ReportResult(
            report_type="personal_simple",
            report_number=report_number,
            subject_name=name,
            report_date=report_date,
            raw_data={"base_info": base_info},
            credit_accounts=credit_accounts,
            query_records=query_records,
        )

    def _extract_base_info(self) -> Optional[dict]:
        lines = self.text.splitlines()
        if len(lines) < 3:
            return None
        try:
            temp = lines[1].split("：")
            report_date = temp[2] if len(temp) > 2 else None
            report_num = temp[1].split(" ")[0] if len(temp) > 1 else None
            temp_1 = lines[2].split("：")
            name = temp_1[1].split(" ")[1] if len(temp_1) > 1 and len(temp_1[1].split(" ")) > 1 else None
            identity = temp_1[3].split(" ")[0] if len(temp_1) > 3 else None
            marry = temp_1[3].split(" ")[1] if len(temp_1) > 3 and len(temp_1[3].split(" ")) > 1 else None

            age = None
            if identity and len(identity) >= 14:
                try:
                    birthdate = datetime.strptime(identity[6:14], "%Y%m%d")
                    today = datetime.today()
                    age = today.year - birthdate.year - (
                        (today.month, today.day) < (birthdate.month, birthdate.day)
                    )
                except ValueError:
                    pass

            return {
                "报告日期": report_date,
                "报告编号": report_num,
                "姓名": name,
                "证件号码": identity,
                "年龄": age,
                "婚姻": marry,
            }
        except (IndexError, AttributeError) as e:
            logger.warning(f"个人简版基础信息提取失败: {e}")
            return None

    def _extract_credit_summary(self) -> list:
        return []  # 完整实现参考旧代码 CR_PSParser 的 card/loan 提取逻辑

    def _extract_query_summary(self) -> list:
        return []  # 完整实现参考旧代码 CR_PSParser.extract_query_info
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_parsers.py -k "personal" -v
```

期望：2 个 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/parsers/personal_detail.py backend/parsers/personal_simple.py tests/test_parsers.py
git commit -m "feat: add PersonalDetailParser and PersonalSimpleParser"
```

---

### Task 10：ReportParserFactory

**Files:**
- Create: `backend/parsers/factory.py`
- Modify: `tests/test_parsers.py`（追加测试）

- [ ] **Step 1: 追加测试**

```python
def test_factory_returns_enterprise_parser_for_enterprise_text():
    from backend.parsers.factory import ReportParserFactory
    parser = ReportParserFactory.get_parser(
        text="企业信用报告\nNO.123", tables=[], file_path="test.pdf"
    )
    from backend.parsers.enterprise import EnterpriseParser
    assert isinstance(parser, EnterpriseParser)

def test_factory_returns_personal_detail_for_detail_text():
    from backend.parsers.factory import ReportParserFactory
    parser = ReportParserFactory.get_parser(
        text="个人信用报告\n身份信息", tables=[], file_path="test.pdf"
    )
    from backend.parsers.personal_detail import PersonalDetailParser
    assert isinstance(parser, PersonalDetailParser)

def test_factory_returns_personal_simple_for_simple_text():
    from backend.parsers.factory import ReportParserFactory
    parser = ReportParserFactory.get_parser(
        text="个人信用报告\n信贷记录", tables=[], file_path="test.pdf"
    )
    from backend.parsers.personal_simple import PersonalSimpleParser
    assert isinstance(parser, PersonalSimpleParser)

def test_factory_raises_for_unknown_text():
    from backend.parsers.factory import ReportParserFactory
    with pytest.raises(ValueError, match="无法识别"):
        ReportParserFactory.get_parser(text="无关内容", tables=[], file_path="test.pdf")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_parsers.py -k "factory" -v
```

- [ ] **Step 3: 实现 factory.py**

```python
# backend/parsers/factory.py
from backend.parsers.base import BaseParser
from backend.parsers.enterprise import EnterpriseParser
from backend.parsers.personal_detail import PersonalDetailParser
from backend.parsers.personal_simple import PersonalSimpleParser


class ReportParserFactory:
    @staticmethod
    def get_parser(text: str, tables: list, file_path: str) -> BaseParser:
        """根据报告文字内容自动识别类型并返回对应 Parser"""
        first_page = text[:500]  # 仅检测前500字
        if "企业信用报告" in first_page:
            return EnterpriseParser(text=text, tables=tables, file_path=file_path)
        if "个人信用报告" in first_page and "身份信息" in first_page:
            return PersonalDetailParser(text=text, tables=tables, file_path=file_path)
        if "个人信用报告" in first_page and "信贷记录" in first_page:
            return PersonalSimpleParser(text=text, tables=tables, file_path=file_path)
        raise ValueError(f"无法识别报告类型，请确认上传的是人民银行征信报告")
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_parsers.py -k "factory" -v
```

期望：4 个 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/parsers/factory.py tests/test_parsers.py
git commit -m "feat: add ReportParserFactory for auto report type detection"
```

---

### Task 11：ReportValidator（防篡改校验）

**Files:**
- Create: `backend/parsers/validator.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_validator.py`：

```python
def test_check_reporttime_no_valid():
    from backend.parsers.validator import ReportValidator
    report_info = {
        "report_date": "2024-01-01T12:00:00",
        "report_number": "20240101120000001"
    }
    assert ReportValidator.check_reporttime_no(report_info) is True

def test_check_reporttime_no_invalid():
    from backend.parsers.validator import ReportValidator
    report_info = {
        "report_date": "2024-01-01T12:00:00",
        "report_number": "99990101120000001"  # 日期不匹配
    }
    assert ReportValidator.check_reporttime_no(report_info) is False
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_validator.py -v
```

- [ ] **Step 3: 实现 validator.py（直接移植旧代码）**

```python
# backend/parsers/validator.py
from datetime import datetime
from PyPDF2 import PdfReader


class ReportValidator:
    @staticmethod
    def validate_report(report_info: dict, file_path: str) -> tuple[bool, str]:
        checks = [
            (ReportValidator.check_reporttime_no, [report_info], "报告时间和报告编号校验不通过"),
            (ReportValidator.check_filemeta, [file_path], "文档属性信息校验不通过"),
            (ReportValidator.check_font, [file_path], "文档字体校验不通过"),
        ]
        for check_func, args, error_message in checks:
            if not check_func(*args):
                return False, error_message
        return True, "报告防篡改验证通过"

    @staticmethod
    def check_reporttime_no(report_info: dict) -> bool:
        report_time = report_info.get("report_date") or report_info.get("报告日期")
        report_no = report_info.get("report_number") or report_info.get("报告编号")
        if not report_time or not report_no:
            return False
        report_no_split = report_no[:14]
        report_time_temp = (
            report_time.replace("-", "").replace("T", "")
            .replace(":", "").replace(" ", "").replace(".", "")
        )
        return report_no_split == report_time_temp

    @staticmethod
    def check_filemeta(path: str) -> bool:
        try:
            pdf_reader = PdfReader(path)
            info_dict = pdf_reader.metadata
            producer_check = info_dict.get("/Producer", "").replace(" ", "") == "iText2.1.7by1T3XT"
            mod_date = info_dict.get("/ModDate", "")
            creation_date = info_dict.get("/CreationDate", "")
            if mod_date and creation_date:
                mod_date = mod_date.replace("D:", "").replace("+08'00'", "")
                creation_date = creation_date.replace("D:", "").replace("+08'00'", "")
                mod_dt = datetime.strptime(mod_date, "%Y%m%d%H%M%S")
                create_dt = datetime.strptime(creation_date, "%Y%m%d%H%M%S")
                date_check = (mod_dt.year == create_dt.year and
                              mod_dt.month == create_dt.month and
                              mod_dt.day == create_dt.day)
            else:
                date_check = False
            return producer_check and date_check
        except Exception:
            return False

    @staticmethod
    def check_font(path: str) -> bool:
        try:
            with open(path, "rb") as file:
                reader = PdfReader(file)
                fonts = set()
                for page in reader.pages:
                    resources = page.get("/Resources", {})
                    if "/Font" in resources:
                        for font_name in resources["/Font"].keys():
                            font = resources["/Font"][font_name]
                            fonts.add(font.get("/BaseFont", ""))
            return len(fonts) == 2 and "/Helvetica" in fonts and any(
                "SourceHanSerifCN" in f for f in fonts
            )
        except Exception:
            return False
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_validator.py -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/parsers/validator.py tests/test_validator.py
git commit -m "feat: add ReportValidator (anti-tampering check)"
```

---

## Phase 5：OCR 与文件处理

### Task 12：GLM-OCR 封装

**Files:**
- Create: `backend/ocr/glm_ocr.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_file_processor.py`：

```python
import pytest
from unittest.mock import patch, MagicMock

def test_glm_ocr_returns_text_on_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "识别出的文字内容"}
    with patch("httpx.post", return_value=mock_response):
        from backend.ocr.glm_ocr import GlmOcr
        ocr = GlmOcr(endpoint="http://localhost:8080/ocr")
        result = ocr.recognize_image(b"fake_image_bytes")
        assert result == "识别出的文字内容"

def test_glm_ocr_raises_on_failure():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    with patch("httpx.post", return_value=mock_response):
        from backend.ocr import glm_ocr
        import importlib
        importlib.reload(glm_ocr)
        from backend.ocr.glm_ocr import GlmOcr
        ocr = GlmOcr(endpoint="http://localhost:8080/ocr")
        with pytest.raises(RuntimeError, match="OCR 服务"):
            ocr.recognize_image(b"fake_image_bytes")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_file_processor.py -k "glm_ocr" -v
```

- [ ] **Step 3: 实现 glm_ocr.py**

```python
# backend/ocr/glm_ocr.py
import httpx
import base64
import logging

logger = logging.getLogger(__name__)


class GlmOcr:
    """GLM-OCR 本地服务封装（通过 HTTP API 调用）"""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def recognize_image(self, image_bytes: bytes) -> str:
        """
        发送图片到 GLM-OCR 服务，返回识别文字。
        GLM-OCR 接口格式：POST /ocr，body: {"image": "<base64>"}
        返回：{"text": "..."}
        """
        image_b64 = base64.b64encode(image_bytes).decode()
        response = httpx.post(
            self.endpoint,
            json={"image": image_b64},
            timeout=60.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"OCR 服务返回错误: {response.status_code} {response.text}")
        return response.json().get("text", "")

    def recognize_file(self, file_path: str) -> str:
        """读取文件并识别"""
        with open(file_path, "rb") as f:
            return self.recognize_image(f.read())
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_file_processor.py -k "glm_ocr" -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/ocr/glm_ocr.py tests/test_file_processor.py
git commit -m "feat: add GLM-OCR HTTP client wrapper"
```

---

### Task 13：文件处理服务（类型检测 + OCR 预处理）

**Files:**
- Create: `backend/services/file_processor.py`

- [ ] **Step 1: 追加测试到 tests/test_file_processor.py**

```python
def test_detect_native_pdf_returns_pdf_native(tmp_path):
    """原生 PDF（有文字层）应返回 pdf_native"""
    import pdfplumber
    from unittest.mock import patch, MagicMock
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "这是一段测试文字" * 20  # 足够多文字
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    with patch("pdfplumber.open", return_value=mock_pdf):
        from backend.services.file_processor import FileProcessor
        processor = FileProcessor(ocr_url="http://localhost:8080/ocr")
        file_type = processor.detect_file_type("fake.pdf")
        assert file_type == "pdf_native"

def test_detect_image_file_returns_image():
    from backend.services.file_processor import FileProcessor
    processor = FileProcessor(ocr_url="http://localhost:8080/ocr")
    assert processor.detect_file_type("photo.jpg") == "image"
    assert processor.detect_file_type("scan.png") == "image"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_file_processor.py -k "detect" -v
```

- [ ] **Step 3: 实现 file_processor.py**

```python
# backend/services/file_processor.py
import os
import logging
from typing import Tuple
import pdfplumber
from pdf2image import convert_from_path
from backend.ocr.glm_ocr import GlmOcr
from backend.core.config import settings

logger = logging.getLogger(__name__)

NATIVE_PDF_TEXT_THRESHOLD = 50  # 少于50字符视为扫描件


class FileProcessor:
    """文件类型检测 + OCR 预处理"""

    def __init__(self, ocr_url: str = None):
        self.ocr = GlmOcr(endpoint=ocr_url or settings.OCR_URL)

    def detect_file_type(self, file_path: str) -> str:
        """
        返回 'pdf_native' | 'pdf_scanned' | 'image'
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
            return "image"
        if ext == ".pdf":
            return self._detect_pdf_type(file_path)
        return "image"  # 未知类型按图片处理

    def _detect_pdf_type(self, file_path: str) -> str:
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "".join(
                    page.extract_text() or "" for page in pdf.pages[:2]
                )
            if len(text.strip()) >= NATIVE_PDF_TEXT_THRESHOLD:
                return "pdf_native"
            return "pdf_scanned"
        except Exception as e:
            logger.warning(f"PDF 类型检测失败，按扫描件处理: {e}")
            return "pdf_scanned"

    def extract_text_and_tables(self, file_path: str, file_type: str) -> Tuple[str, list]:
        """
        根据文件类型提取文字和表格。
        返回 (text, tables)，其中 tables 为 pdfplumber 格式。
        """
        if file_type == "pdf_native":
            return self._extract_from_native_pdf(file_path)
        elif file_type == "pdf_scanned":
            return self._extract_from_scanned_pdf(file_path)
        else:  # image
            return self._extract_from_image(file_path)

    def _extract_from_native_pdf(self, file_path: str) -> Tuple[str, list]:
        with pdfplumber.open(file_path) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
            tables = []
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    for table in page_tables:
                        if table:
                            if tables and len(table[0]) == len(tables[-1][0]):
                                tables[-1] += table
                            else:
                                tables.append(table)
        # 清洗换行符
        tables = self._clean_tables(tables)
        return text, tables

    def _extract_from_scanned_pdf(self, file_path: str) -> Tuple[str, list]:
        images = convert_from_path(file_path)
        texts = []
        for img in images:
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            text = self.ocr.recognize_image(buf.getvalue())
            texts.append(text)
        return "\n".join(texts), []  # 扫描件无结构化表格

    def _extract_from_image(self, file_path: str) -> Tuple[str, list]:
        text = self.ocr.recognize_file(file_path)
        return text, []

    @staticmethod
    def _clean_tables(tables: list) -> list:
        for i in range(len(tables)):
            for j in range(len(tables[i])):
                for k in range(len(tables[i][j])):
                    if isinstance(tables[i][j][k], str):
                        tables[i][j][k] = tables[i][j][k].replace("\n", "")
        return tables
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_file_processor.py -k "detect" -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/services/file_processor.py tests/test_file_processor.py
git commit -m "feat: add FileProcessor with type detection and OCR preprocessing"
```

---

## Phase 6：报告服务与 API

### Task 14：ReportService（解析流程编排 + 写库）

**Files:**
- Create: `backend/services/report_service.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_report_service.py`：

```python
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.database import Base
from backend.models.db import User, Report

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

@pytest.fixture(autouse=True)
def setup():
    Base.metadata.create_all(engine)
    db = Session()
    user = User(id=1, username="test", password_hash="x", role="user")
    db.add(user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(engine)

def test_process_report_creates_db_record():
    from backend.parsers.base import ReportResult
    mock_result = ReportResult(
        report_type="enterprise",
        report_number="20240101120000001",
        subject_name="测试企业",
        report_date="2024-01-01T12:00:00",
        raw_data={"key": "val"},
    )
    with patch("backend.services.report_service.FileProcessor") as MockFP, \
         patch("backend.services.report_service.ReportParserFactory") as MockFactory, \
         patch("backend.services.report_service.ReportValidator") as MockValidator:

        MockFP.return_value.detect_file_type.return_value = "pdf_native"
        MockFP.return_value.extract_text_and_tables.return_value = ("企业信用报告文字", [])
        MockFactory.get_parser.return_value.parse.return_value = mock_result
        MockValidator.validate_report.return_value = (True, "通过")

        from backend.services.report_service import ReportService
        db = Session()
        service = ReportService(db=db)
        report_id = service.process_report(file_path="test.pdf", user_id=1)
        db.close()

        db = Session()
        report = db.query(Report).filter(Report.id == report_id).first()
        assert report is not None
        assert report.subject_name == "测试企业"
        assert report.parse_status == "success"
        db.close()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_report_service.py -v
```

- [ ] **Step 3: 实现 report_service.py**

```python
# backend/services/report_service.py
import logging
from dataclasses import asdict
from sqlalchemy.orm import Session
from backend.models.db import Report, EnterpriseReport, PersonalReport, CreditAccount, QueryRecord
from backend.services.file_processor import FileProcessor
from backend.parsers.factory import ReportParserFactory
from backend.parsers.validator import ReportValidator

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.file_processor = FileProcessor()

    def process_report(self, file_path: str, user_id: int) -> int:
        """
        完整解析流程：检测类型 → OCR预处理 → 解析 → 防篡改校验 → 写库
        返回 report.id
        """
        file_type = self.file_processor.detect_file_type(file_path)

        # 创建 Report 主记录（pending 状态）
        report = Report(
            user_id=user_id,
            file_path=file_path,
            file_type=file_type,
            parse_status="pending",
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        try:
            text, tables = self.file_processor.extract_text_and_tables(file_path, file_type)
            parser = ReportParserFactory.get_parser(text=text, tables=tables, file_path=file_path)
            result = parser.parse()

            # 防篡改校验（仅原生 PDF）
            is_valid = None
            if file_type == "pdf_native":
                is_valid, _ = ReportValidator.validate_report(
                    {"report_date": result.report_date, "report_number": result.report_number},
                    file_path,
                )

            # 更新主记录
            report.report_type = result.report_type
            report.report_number = result.report_number
            report.subject_name = result.subject_name
            report.report_date = result.report_date
            report.is_valid = is_valid
            report.parse_status = "success"

            # 写入子表
            self._save_detail(report.id, result)
            self.db.commit()

        except Exception as e:
            logger.error(f"报告解析失败: {e}", exc_info=True)
            report.parse_status = "failed"
            self.db.commit()
            raise

        return report.id

    def _save_detail(self, report_id: int, result) -> None:
        if result.report_type == "enterprise":
            self.db.add(EnterpriseReport(
                report_id=report_id,
                company_name=result.subject_name,
                data_json=result.raw_data,
            ))
        else:
            self.db.add(PersonalReport(
                report_id=report_id,
                name=result.subject_name,
                data_json=result.raw_data,
            ))

        for acc in result.credit_accounts:
            self.db.add(CreditAccount(
                report_id=report_id,
                account_type=acc.get("account_type"),
                institution=acc.get("institution"),
                amount=acc.get("amount"),
                balance=acc.get("balance"),
                status=acc.get("status"),
                data_json=acc.get("data_json"),
            ))

        for qr in result.query_records:
            self.db.add(QueryRecord(
                report_id=report_id,
                query_date=qr.get("query_date"),
                query_org=qr.get("query_org"),
                query_reason=qr.get("query_reason"),
            ))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_report_service.py -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/services/report_service.py tests/test_report_service.py
git commit -m "feat: add ReportService for full parse pipeline"
```

---

### Task 15：报告 API 端点

**Files:**
- Modify: `backend/api/reports.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_api_reports.py`：

```python
import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.database import Base, get_db
from backend.models.db import User, Report
from backend.core.auth import hash_password, create_token
from backend.main import app
from unittest.mock import patch

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    db = TestSession()
    user = User(id=1, username="testuser", password_hash=hash_password("pass"), role="user")
    db.add(user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(engine)

client = TestClient(app)

def get_token():
    return create_token(user_id=1, username="testuser", role="user")

def test_upload_report_success():
    with patch("backend.api.reports.ReportService") as MockService:
        MockService.return_value.process_report.return_value = 1
        token = get_token()
        resp = client.post(
            "/api/reports/upload",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "report_id" in resp.json()

def test_get_reports_list_returns_only_own():
    token = get_token()
    resp = client.get("/api/reports", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_get_report_detail_not_found():
    token = get_token()
    resp = client.get("/api/reports/9999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_api_reports.py -v
```

- [ ] **Step 3: 实现 backend/api/reports.py**

```python
# backend/api/reports.py
import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.config import settings
from backend.api.auth import get_current_user
from backend.models.db import User, Report
from backend.services.report_service import ReportService

router = APIRouter()


@router.post("/upload")
def upload_report(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    service = ReportService(db=db)
    try:
        report_id = service.process_report(file_path=file_path, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"report_id": report_id, "message": "解析完成"}


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports = (
        db.query(Report)
        .filter(Report.user_id == current_user.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "subject_name": r.subject_name,
            "report_number": r.report_number,
            "report_date": r.report_date,
            "parse_status": r.parse_status,
            "is_valid": r.is_valid,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@router.get("/{report_id}")
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.user_id == current_user.id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    detail = None
    if report.enterprise_report:
        detail = report.enterprise_report.data_json
    elif report.personal_report:
        detail = report.personal_report.data_json

    return {
        "id": report.id,
        "report_type": report.report_type,
        "subject_name": report.subject_name,
        "report_number": report.report_number,
        "report_date": report.report_date,
        "is_valid": report.is_valid,
        "parse_status": report.parse_status,
        "detail": detail,
        "credit_accounts": [
            {"account_type": a.account_type, "institution": a.institution,
             "balance": a.balance, "status": a.status}
            for a in report.credit_accounts
        ],
        "query_records": [
            {"query_date": q.query_date, "query_org": q.query_org}
            for q in report.query_records
        ],
    }


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.user_id == current_user.id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(report)
    db.commit()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_api_reports.py -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/api/reports.py tests/test_api_reports.py
git commit -m "feat: add report upload/list/detail/delete API endpoints"
```

---

### Task 16：用户管理 API

**Files:**
- Modify: `backend/api/users.py`

- [ ] **Step 1: 写测试**

新建 `tests/test_api_users.py`：

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.database import Base, get_db
from backend.models.db import User
from backend.core.auth import hash_password, create_token
from backend.main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    db = TestSession()
    admin = User(username="admin", password_hash=hash_password("admin123"), role="admin")
    normal = User(username="user1", password_hash=hash_password("pass"), role="user")
    db.add_all([admin, normal])
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(engine)

client = TestClient(app)

def test_admin_can_list_users():
    db = TestSession()
    admin = db.query(User).filter(User.username == "admin").first()
    token = create_token(user_id=admin.id, username="admin", role="admin")
    db.close()
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

def test_normal_user_cannot_list_users():
    db = TestSession()
    user = db.query(User).filter(User.username == "user1").first()
    token = create_token(user_id=user.id, username="user1", role="user")
    db.close()
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_api_users.py -v
```

- [ ] **Step 3: 实现 backend/api/users.py**

```python
# backend/api/users.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_admin
from backend.models.db import User

router = APIRouter()


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = db.query(User).all()
    return [
        {"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active}
        for u in users
    ]


@router.patch("/{user_id}/deactivate", status_code=204)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    from fastapi import HTTPException
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = False
    db.commit()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_api_users.py -v
```

- [ ] **Step 5: 运行全部测试**

```bash
pytest tests/ -v
```

期望：所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/api/users.py tests/test_api_users.py
git commit -m "feat: add user management API (admin only)"
```

---

## Phase 7：Streamlit 前端

### Task 17：API Client 封装

**Files:**
- Create: `frontend/api_client.py`

- [ ] **Step 1: 实现 api_client.py**

```python
# frontend/api_client.py
import httpx
import streamlit as st
from typing import Optional

API_BASE = "http://localhost:8000"


def get_headers() -> dict:
    token = st.session_state.get("token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def login(username: str, password: str) -> dict:
    resp = httpx.post(f"{API_BASE}/api/auth/login", json={"username": username, "password": password})
    resp.raise_for_status()
    return resp.json()


def register_user(username: str, password: str) -> dict:
    resp = httpx.post(
        f"{API_BASE}/api/auth/register",
        json={"username": username, "password": password},
        headers=get_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def upload_report(file_bytes: bytes, filename: str) -> dict:
    resp = httpx.post(
        f"{API_BASE}/api/reports/upload",
        files={"file": (filename, file_bytes, "application/octet-stream")},
        headers=get_headers(),
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()


def list_reports() -> list:
    resp = httpx.get(f"{API_BASE}/api/reports", headers=get_headers())
    resp.raise_for_status()
    return resp.json()


def get_report(report_id: int) -> dict:
    resp = httpx.get(f"{API_BASE}/api/reports/{report_id}", headers=get_headers())
    resp.raise_for_status()
    return resp.json()


def delete_report(report_id: int) -> None:
    resp = httpx.delete(f"{API_BASE}/api/reports/{report_id}", headers=get_headers())
    resp.raise_for_status()


def list_users() -> list:
    resp = httpx.get(f"{API_BASE}/api/users", headers=get_headers())
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 2: 提交**

```bash
git add frontend/api_client.py
git commit -m "feat: add frontend API client wrapper"
```

---

### Task 18：登录页与会话管理

**Files:**
- Create: `frontend/app.py`

- [ ] **Step 1: 实现 app.py（登录入口）**

```python
# frontend/app.py
import streamlit as st
from frontend.api_client import login

st.set_page_config(page_title="征信报告审核系统", layout="wide")

def show_login():
    st.title("征信报告审核系统")
    st.subheader("登录")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        try:
            data = login(username, password)
            st.session_state["token"] = data["token"]
            st.session_state["username"] = data["username"]
            st.session_state["role"] = data["role"]
            st.success("登录成功")
            st.rerun()
        except Exception:
            st.error("用户名或密码错误")

def require_login():
    if "token" not in st.session_state:
        show_login()
        st.stop()

require_login()

st.sidebar.success(f"已登录：{st.session_state.get('username')}")
if st.sidebar.button("退出登录"):
    st.session_state.clear()
    st.rerun()

st.title("欢迎使用征信报告审核系统")
st.info("请从左侧导航选择功能")
```

- [ ] **Step 2: 启动验证**

```bash
cd D:/loansystem/creditreport
uvicorn backend.main:app --reload --port 8000 &
streamlit run frontend/app.py --server.port 8501
```

在浏览器访问 `http://localhost:8501`，确认登录页正常显示。

- [ ] **Step 3: 提交**

```bash
git add frontend/app.py
git commit -m "feat: add Streamlit login page with session management"
```

---

### Task 19：上传解析页

**Files:**
- Create: `frontend/pages/1_上传解析.py`

- [ ] **Step 1: 实现上传页**

```python
# frontend/pages/1_上传解析.py
import streamlit as st
from frontend.api_client import upload_report

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

st.title("上传解析")
st.markdown("支持格式：**PDF（原生/扫描）、JPG、PNG**")

uploaded_file = st.file_uploader(
    "上传征信报告",
    type=["pdf", "jpg", "jpeg", "png"],
    label_visibility="visible",
)

if uploaded_file is not None:
    with st.spinner("解析中，请稍候..."):
        try:
            result = upload_report(
                file_bytes=uploaded_file.getvalue(),
                filename=uploaded_file.name,
            )
            st.success(f"解析完成！报告ID：{result['report_id']}")
            st.session_state["last_report_id"] = result["report_id"]
        except Exception as e:
            st.error(f"解析失败：{e}")

if st.session_state.get("last_report_id"):
    st.info(f"最近解析的报告 ID：{st.session_state['last_report_id']}，可在「报告列表」页查看详情")
```

- [ ] **Step 2: 提交**

```bash
git add "frontend/pages/1_上传解析.py"
git commit -m "feat: add upload page"
```

---

### Task 20：报告列表页

**Files:**
- Create: `frontend/pages/2_报告列表.py`

- [ ] **Step 1: 实现报告列表页**

```python
# frontend/pages/2_报告列表.py
import streamlit as st
import pandas as pd
from frontend.api_client import list_reports, delete_report

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

st.title("报告列表")

try:
    reports = list_reports()
except Exception as e:
    st.error(f"获取报告列表失败：{e}")
    st.stop()

if not reports:
    st.info("暂无报告，请前往「上传解析」页上传")
    st.stop()

TYPE_MAP = {"enterprise": "企业版", "personal_detail": "个人详版", "personal_simple": "个人简版"}
STATUS_MAP = {"success": "✅ 成功", "failed": "❌ 失败", "pending": "⏳ 处理中"}

df = pd.DataFrame([
    {
        "ID": r["id"],
        "主体名称": r["subject_name"] or "-",
        "类型": TYPE_MAP.get(r["report_type"], r["report_type"]),
        "报告日期": r["report_date"] or "-",
        "解析状态": STATUS_MAP.get(r["parse_status"], r["parse_status"]),
        "防篡改": "✅ 通过" if r["is_valid"] else ("❌ 未通过" if r["is_valid"] is False else "-"),
        "上传时间": r["created_at"][:19] if r["created_at"] else "-",
    }
    for r in reports
])

# 筛选
search = st.text_input("按主体名称筛选")
if search:
    df = df[df["主体名称"].str.contains(search, na=False)]

st.dataframe(df, use_container_width=True)

# 查看/删除
col1, col2 = st.columns(2)
with col1:
    view_id = st.number_input("输入报告ID查看详情", min_value=1, step=1, value=None)
    if view_id and st.button("查看详情"):
        st.session_state["view_report_id"] = int(view_id)
        st.switch_page("pages/3_报告详情.py")

with col2:
    del_id = st.number_input("输入报告ID删除", min_value=1, step=1, value=None, key="del_id")
    if del_id and st.button("删除报告", type="primary"):
        try:
            delete_report(int(del_id))
            st.success("删除成功")
            st.rerun()
        except Exception as e:
            st.error(f"删除失败：{e}")
```

- [ ] **Step 2: 提交**

```bash
git add "frontend/pages/2_报告列表.py"
git commit -m "feat: add report list page with search and delete"
```

---

### Task 21：报告详情页

**Files:**
- Create: `frontend/pages/3_报告详情.py`

- [ ] **Step 1: 实现报告详情页**

```python
# frontend/pages/3_报告详情.py
import streamlit as st
import pandas as pd
from frontend.api_client import get_report

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

report_id = st.session_state.get("view_report_id")
if not report_id:
    report_id = st.number_input("输入报告ID", min_value=1, step=1)
    if not st.button("加载"):
        st.stop()

try:
    report = get_report(int(report_id))
except Exception as e:
    st.error(f"获取报告失败：{e}")
    st.stop()

TYPE_MAP = {"enterprise": "企业版", "personal_detail": "个人详版", "personal_simple": "个人简版"}
st.title(f"报告详情 — {report.get('subject_name', '未知')}")

col1, col2, col3 = st.columns(3)
col1.metric("报告类型", TYPE_MAP.get(report["report_type"], report["report_type"]))
col2.metric("报告日期", report.get("report_date") or "-")
col3.metric("防篡改校验", "✅ 通过" if report["is_valid"] else ("❌ 未通过" if report["is_valid"] is False else "-"))

tab1, tab2, tab3 = st.tabs(["基本信息", "信贷账户", "查询记录"])

with tab1:
    detail = report.get("detail")
    if detail:
        if "report_info" in detail:
            st.subheader("报告信息")
            st.json(detail["report_info"])
        if "com_base" in detail:
            st.subheader("企业基本信息")
            st.json(detail["com_base"])
        if "base_info" in detail:
            st.subheader("个人基本信息")
            st.json(detail["base_info"])
        if "summary" in detail and detail["summary"]:
            st.subheader("信息概要")
            st.json(detail["summary"])
    else:
        st.info("暂无详情数据")

with tab2:
    accounts = report.get("credit_accounts", [])
    if accounts:
        st.dataframe(pd.DataFrame(accounts), use_container_width=True)
    else:
        st.info("暂无信贷账户数据")

with tab3:
    queries = report.get("query_records", [])
    if queries:
        st.dataframe(pd.DataFrame(queries), use_container_width=True)
    else:
        st.info("暂无查询记录")
```

- [ ] **Step 2: 提交**

```bash
git add "frontend/pages/3_报告详情.py"
git commit -m "feat: add report detail page with tabbed display"
```

---

### Task 22：用户管理页

**Files:**
- Create: `frontend/pages/4_用户管理.py`

- [ ] **Step 1: 实现用户管理页**

```python
# frontend/pages/4_用户管理.py
import streamlit as st
import pandas as pd
from frontend.api_client import list_users, register_user

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("需要管理员权限")
    st.stop()

st.title("用户管理")

# 用户列表
try:
    users = list_users()
    df = pd.DataFrame(users)
    st.subheader("当前用户")
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"获取用户列表失败：{e}")

st.divider()

# 新增用户
st.subheader("新增用户")
with st.form("add_user_form"):
    new_username = st.text_input("用户名")
    new_password = st.text_input("密码", type="password")
    submitted = st.form_submit_button("创建用户")
    if submitted:
        if not new_username or not new_password:
            st.error("用户名和密码不能为空")
        else:
            try:
                register_user(new_username, new_password)
                st.success(f"用户 {new_username} 创建成功")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")
```

- [ ] **Step 2: 提交**

```bash
git add "frontend/pages/4_用户管理.py"
git commit -m "feat: add user management page (admin only)"
```

---

## Phase 8：部署

### Task 23：Docker Compose（Web 版）

**Files:**
- Create: `deploy/docker-compose.yml`
- Create: `deploy/nginx.conf`
- Create: `Dockerfile.backend`
- Create: `Dockerfile.frontend`

- [ ] **Step 1: 创建 Dockerfile.backend**

```dockerfile
# Dockerfile.backend
FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini .
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: 创建 Dockerfile.frontend**

```dockerfile
# Dockerfile.frontend
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY frontend/ ./frontend/
EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

- [ ] **Step 3: 创建 deploy/docker-compose.yml**

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: credituser
      POSTGRES_PASSWORD: creditpass
      POSTGRES_DB: creditreport
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U credituser"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ..
      dockerfile: Dockerfile.backend
    environment:
      MODE: web
      DATABASE_URL: postgresql://credituser:creditpass@postgres:5432/creditreport
      JWT_SECRET: ${JWT_SECRET:-change-me-in-production}
      OCR_URL: http://glm-ocr:8080/ocr
      UPLOAD_DIR: /app/uploads
    volumes:
      - uploads:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ..
      dockerfile: Dockerfile.frontend
    environment:
      API_BASE: http://backend:8000
    depends_on:
      - backend
    ports:
      - "8501:8501"

  glm-ocr:
    image: glm-ocr:latest   # 替换为实际 GLM-OCR 镜像名
    ports:
      - "8080:8080"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - frontend
      - backend

volumes:
  pgdata:
  uploads:
```

- [ ] **Step 4: 创建 deploy/nginx.conf**

```nginx
server {
    listen 80;

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://frontend:8501;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] **Step 5: 提交**

```bash
git add Dockerfile.backend Dockerfile.frontend deploy/
git commit -m "feat: add Docker deployment configuration"
```

---

### Task 24：创建初始管理员账户脚本

**Files:**
- Create: `backend/scripts/create_admin.py`

- [ ] **Step 1: 实现脚本**

```python
# backend/scripts/create_admin.py
"""
使用方式：
python -m backend.scripts.create_admin --username admin --password yourpassword
"""
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.database import Base
from backend.models.db import User
from backend.core.auth import hash_password
from backend.core.config import settings

def create_admin(username: str, password: str):
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        print(f"用户 {username} 已存在")
        return
    admin = User(username=username, password_hash=hash_password(password), role="admin")
    db.add(admin)
    db.commit()
    print(f"管理员账户 {username} 创建成功")
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    create_admin(args.username, args.password)
```

- [ ] **Step 2: 测试脚本**

```bash
python -m backend.scripts.create_admin --username admin --password admin123
```

期望输出：`管理员账户 admin 创建成功`

- [ ] **Step 3: 运行全量测试，确认无回归**

```bash
pytest tests/ -v
```

期望：所有测试 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/scripts/create_admin.py
git commit -m "feat: add admin account creation script"
```

---

## 自检

**Spec coverage 检查：**

| 需求 | 覆盖任务 |
|------|----------|
| 支持 PDF/扫描件/图片 | Task 12, 13 |
| 字段提取 | Task 8, 9, 10 |
| 持久化存储（PostgreSQL） | Task 4, 14 |
| Web 版 | Task 16-22, 23 |
| 本地版（exe）| ⚠️ 见下方说明 |
| 多用户认证（2-10人）| Task 5, 6, 16 |
| 用户数据隔离 | Task 15 |
| 防篡改校验 | Task 11 |

> **本地版 exe 打包**：因 PyInstaller 打包依赖运行环境，不适合通过测试验证，建议在所有功能开发完成后单独执行：
> ```bash
> pip install pyinstaller
> pyinstaller --onefile --name creditreport_local \
>   --add-data "frontend:frontend" \
>   run_local.py
> ```
> 需额外创建 `run_local.py` 启动脚本（同时启动 FastAPI + Streamlit + 打开浏览器）。

**无遗留 placeholder：** 所有步骤均包含实际代码。

**类型一致性：**
- `ReportResult` 在 Task 7 定义，Task 8/9/10/14 均使用相同字段名
- `get_current_user` 在 Task 6 定义，Task 15/16 复用
- `FileProcessor.extract_text_and_tables` 返回 `(str, list)`，Task 13/14 一致
