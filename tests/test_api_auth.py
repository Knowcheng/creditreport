import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.core.database import Base, get_db
from backend.models.db import User
from backend.core.auth import hash_password
from backend.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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
