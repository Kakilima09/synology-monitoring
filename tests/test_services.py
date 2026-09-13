import pytest
from app.services.synology_service import MockSynologyService
from app.services.backup_sync_service import BackupSyncService
from app.models import SynologyDevice
from app.extensions import db

def test_mock_service(app):
    with app.app_context():
        device = SynologyDevice(name='test', host='localhost', port=5000, username='admin', password='pass')
        service = MockSynologyService(device)
        assert service.test_connection()['success'] is True
        tasks = service.get_backup_tasks()
        assert len(tasks) > 0

def test_sync_service_mock(app):
    with app.app_context():
        device = SynologyDevice(name='test', host='localhost', port=5000, username='admin', password='pass')
        db.session.add(device)
        db.session.commit()
        service = BackupSyncService(use_mock=True)
        result = service.sync_device(device)
        assert result['status'] == 'SUCCESS'