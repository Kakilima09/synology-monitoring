import pytest
from flask import url_for
from app import db
from app.models import User

def test_login_page(client):
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Login' in response.data

def test_login_valid_user(client, app):
    with app.app_context():
        user = User(username='testuser', email='test@example.com', role='VIEWER')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
    response = client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'password'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Dashboard' in response.data

def test_dashboard_requires_login(client):
    response = client.get('/')
    assert response.status_code == 302  # redirect to login

def test_synology_index_requires_login(client):
    response = client.get('/synology/')
    assert response.status_code == 302

def test_sync_command_route(app):
    # We can test that the command exists
    runner = app.test_cli_runner()
    result = runner.invoke(args=['sync-backup', '--help'])
    assert result.exit_code == 0