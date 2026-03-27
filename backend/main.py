from fastapi import FastAPI
from backend.api import auth, reports, users

app = FastAPI(title="征信报告审核系统", version="1.0.0")

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(reports.router, prefix="/api/reports", tags=["报告"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
