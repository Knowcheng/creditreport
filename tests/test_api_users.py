import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.core.database import Base, get_db
from backend.models.db import User
from backend.core.auth import hash_password, create_token
from backend.main import app

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
