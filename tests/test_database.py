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
