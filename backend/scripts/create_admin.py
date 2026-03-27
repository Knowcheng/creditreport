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
