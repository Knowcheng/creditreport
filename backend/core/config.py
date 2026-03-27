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

    def __init__(self):
        if self.MODE == "web" and self.JWT_SECRET == "dev-secret-change-in-prod":
            raise ValueError("生产环境必须设置 JWT_SECRET 环境变量")

    @property
    def DATABASE_URL(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        if self.MODE == "local":
            return "sqlite:///./creditreport.db"
        raise ValueError("DATABASE_URL 环境变量未设置（web 模式必须提供）")


settings = Settings()
