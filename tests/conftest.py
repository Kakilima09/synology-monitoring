import os

# Wajib di-set SEBELUM mengimpor app/config, karena Config
# membaca DATABASE_URL saat class Config didefinisikan.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from app import create_app
from app.extensions import db as _db

@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///:memory:"), \
            "Tests must never touch the production DB!"
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()