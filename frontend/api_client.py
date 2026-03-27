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
