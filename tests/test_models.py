import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

def test_all_tables_created():
    import importlib
    import backend.core.database
    importlib.reload(backend.core.database)
    import backend.models.db
    importlib.reload(backend.models.db)
    engine = create_engine("sqlite:///:memory:")
    from backend.core.database import Base
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "users" in tables
    assert "reports" in tables
    assert "enterprise_reports" in tables
    assert "personal_reports" in tables
    assert "credit_accounts" in tables
    assert "query_records" in tables

def test_user_model_fields():
    import importlib
    import backend.core.database
    importlib.reload(backend.core.database)
    import backend.models.db
    importlib.reload(backend.models.db)
    engine = create_engine("sqlite:///:memory:")
    from backend.core.database import Base
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("users")]
    assert "id" in cols
    assert "username" in cols
    assert "password_hash" in cols
    assert "role" in cols
