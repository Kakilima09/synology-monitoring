import pytest
from app.services.synology_service import MockSynologyService
from app.services.backup_sync_service import BackupSyncService
from app.models import SynologyDevice

def test_mock_service():
    device = SynologyDevice(name='test', host='localhost', port=5000, username='admin', password='pass')
    service = MockSynologyService(device)
    assert service.test_connection()['success'] is True
    tasks = service.get_backup_tasks()
    assert len(tasks) > 0

def test_sync_service_mock():
    device = SynologyDevice(name='test', host='localhost', port=5000, username='admin', password='pass')
    # We need to add to session for saving
    # In a real test, we'd use a test database
    service = BackupSyncService(use_mock=True)
    result = service.sync_device(device)
    assert result['status'] == 'SUCCESS'