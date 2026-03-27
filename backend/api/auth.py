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
