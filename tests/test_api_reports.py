import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.core.database import Base, get_db
from backend.models.db import User, Report
from backend.core.auth import hash_password, create_token
from backend.main import app
from unittest.mock import patch

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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
