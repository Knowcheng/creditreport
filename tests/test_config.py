import os
import pytest


def test_web_mode_reads_postgres_url(monkeypatch):
    monkeypatch.setenv("MODE", "web")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET", "secret")
    monkeypatch.setenv("OCR_URL", "http://localhost:8080/ocr")
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
